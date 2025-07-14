#!/bin/bash

# EKS Node Bootstrap Script
# This script bootstraps EKS worker nodes with the cluster configuration

set -o xtrace

# Update system packages
yum update -y

# Install additional packages
yum install -y \
    awscli \
    jq \
    wget \
    htop \
    iotop \
    vim \
    git \
    curl \
    unzip

# Configure AWS CLI region
aws configure set default.region $(curl -s http://169.254.169.254/latest/meta-data/placement/region)

# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
rpm -U ./amazon-cloudwatch-agent.rpm

# Install Systems Manager agent
yum install -y amazon-ssm-agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# Install Container Insights
curl -O https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/cwagent/cwagent-daemonset.yaml

# Configure Docker daemon
mkdir -p /etc/docker
cat <<EOF > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ]
}
EOF

# Restart Docker service
systemctl restart docker

# Set up kubelet configuration
mkdir -p /etc/kubernetes/kubelet
cat <<EOF > /etc/kubernetes/kubelet/kubelet-config.json
{
  "kind": "KubeletConfiguration",
  "apiVersion": "kubelet.config.k8s.io/v1beta1",
  "address": "0.0.0.0",
  "port": 10250,
  "readOnlyPort": 0,
  "cgroupDriver": "systemd",
  "hairpinMode": "hairpin-veth",
  "serializeImagePulls": false,
  "featureGates": {
    "RotateKubeletServerCertificate": true
  },
  "clusterDNS": ["169.254.20.10"],
  "clusterDomain": "cluster.local",
  "runtimeRequestTimeout": "10m",
  "kubeReserved": {
    "cpu": "100m",
    "memory": "100Mi",
    "ephemeral-storage": "1Gi"
  },
  "systemReserved": {
    "cpu": "100m",
    "memory": "100Mi",
    "ephemeral-storage": "1Gi"
  },
  "evictionHard": {
    "memory.available": "100Mi",
    "nodefs.available": "10%",
    "nodefs.inodesFree": "5%"
  },
  "maxPods": 110
}
EOF

# Set up logging for kubelet
mkdir -p /etc/systemd/system/kubelet.service.d
cat <<EOF > /etc/systemd/system/kubelet.service.d/20-logging.conf
[Service]
Environment="KUBELET_LOG_LEVEL=2"
EOF

# Enable and start kubelet logging
systemctl daemon-reload

# Install kubectl for debugging
curl -o kubectl https://amazon-eks.s3.us-west-2.amazonaws.com/1.28.3/2023-11-14/bin/linux/amd64/kubectl
chmod +x ./kubectl
mv ./kubectl /usr/local/bin/kubectl

# Install Helm for package management
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# Configure node labels and taints (applied via user data)
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
INSTANCE_TYPE=$(curl -s http://169.254.169.254/latest/meta-data/instance-type)
AVAILABILITY_ZONE=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)

# Set up node problem detector
cat <<EOF > /etc/systemd/system/node-problem-detector.service
[Unit]
Description=Node Problem Detector
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/node-problem-detector --v=2 --logtostderr --config.system-log-monitor=/config/kernel-monitor.json,/config/docker-monitor.json --config.system-stats-monitor=/config/system-stats-monitor.json --config.custom-plugin-monitor=/config/custom-plugin-monitor.json
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure log rotation
cat <<EOF > /etc/logrotate.d/kubernetes
/var/log/pods/*/*.log {
    daily
    missingok
    rotate 5
    compress
    notifempty
    create 0644 root root
}
EOF

# Set up disk space monitoring
cat <<EOF > /usr/local/bin/disk-space-monitor.sh
#!/bin/bash
THRESHOLD=80
CURRENT=\$(df /var/lib/docker | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{ print \$5 }' | head -1 | cut -d'%' -f1)
if [ "\$CURRENT" -gt "\$THRESHOLD" ]; then
    echo "Disk space usage is above \$THRESHOLD%: \$CURRENT%"
    docker system prune -f
fi
EOF

chmod +x /usr/local/bin/disk-space-monitor.sh

# Add cron job for disk space monitoring
echo "0 */6 * * * /usr/local/bin/disk-space-monitor.sh" | crontab -

# Configure network settings for high performance
cat <<EOF >> /etc/sysctl.conf
# Network performance tuning
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 16384 16777216
net.ipv4.tcp_congestion_control = bbr
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_slow_start_after_idle = 0
EOF

sysctl -p

# Set up file descriptor limits
cat <<EOF >> /etc/security/limits.conf
* soft nofile 65536
* hard nofile 65536
root soft nofile 65536
root hard nofile 65536
EOF

# Configure swap (disable for Kubernetes)
swapoff -a
sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# Bootstrap the node with EKS
/etc/eks/bootstrap.sh ${cluster_name} ${bootstrap_arguments}

# Configure CloudWatch agent
cat <<EOF > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "metrics": {
    "namespace": "EKS/Node",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_user",
          "cpu_usage_system"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ],
        "totalcpu": false
      },
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "diskio": {
        "measurement": [
          "io_time"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "*"
        ]
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      },
      "netstat": {
        "measurement": [
          "tcp_established",
          "tcp_time_wait"
        ],
        "metrics_collection_interval": 60
      },
      "swap": {
        "measurement": [
          "swap_used_percent"
        ],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/messages",
            "log_group_name": "/aws/eks/node/${cluster_name}",
            "log_stream_name": "{instance_id}/messages"
          },
          {
            "file_path": "/var/log/docker",
            "log_group_name": "/aws/eks/node/${cluster_name}",
            "log_stream_name": "{instance_id}/docker"
          }
        ]
      }
    }
  }
}
EOF

# Start CloudWatch agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

# Final system configuration
systemctl enable docker
systemctl enable kubelet
systemctl enable amazon-cloudwatch-agent

# Log completion
echo "EKS node bootstrap completed successfully at $(date)" >> /var/log/bootstrap.log

# Set up health check script
cat <<EOF > /usr/local/bin/node-health-check.sh
#!/bin/bash
# Basic health check for EKS node
if ! systemctl is-active --quiet kubelet; then
    echo "kubelet is not running"
    exit 1
fi

if ! systemctl is-active --quiet docker; then
    echo "docker is not running"
    exit 1
fi

# Check disk space
DISK_USAGE=\$(df /var/lib/docker | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{ print \$5 }' | head -1 | cut -d'%' -f1)
if [ "\$DISK_USAGE" -gt 90 ]; then
    echo "Disk usage is critical: \$DISK_USAGE%"
    exit 1
fi

echo "Node health check passed"
EOF

chmod +x /usr/local/bin/node-health-check.sh

# Add health check to cron
echo "*/5 * * * * /usr/local/bin/node-health-check.sh >> /var/log/health-check.log 2>&1" | crontab -

# Final reboot to ensure all configurations are applied
# Note: This is commented out for production use
# reboot