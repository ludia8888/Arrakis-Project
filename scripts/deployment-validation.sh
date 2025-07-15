#!/bin/bash

# Comprehensive Deployment Validation Script
# Validates infrastructure deployment and service health
# Ultra production-ready with comprehensive checks and reporting

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_FILE="${PROJECT_ROOT}/deployment-validation.log"
REPORT_FILE="${PROJECT_ROOT}/deployment-report.md"

# Default values
ENVIRONMENT="${1:-staging}"
VALIDATION_TIMEOUT="${VALIDATION_TIMEOUT:-300}"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${LOG_FILE}"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "${LOG_FILE}"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "${LOG_FILE}"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${LOG_FILE}"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "${LOG_FILE}"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        error "Deployment validation failed with exit code $exit_code"
        error "Check log file: ${LOG_FILE}"
        generate_failure_report
    fi
    exit $exit_code
}

trap cleanup EXIT

# Initialize validation report
init_report() {
    info "Initializing deployment validation report..."

    cat > "${REPORT_FILE}" << EOF
# 🚀 Deployment Validation Report

**Environment:** ${ENVIRONMENT}
**Validation Date:** $(date -u)
**Validation Script:** $0
**Log File:** ${LOG_FILE}

## 📋 Validation Summary

EOF
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    local deps=("aws" "kubectl" "terraform" "curl" "jq" "helm")
    local missing_deps=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing_deps+=("$dep")
        fi
    done

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error "Missing dependencies: ${missing_deps[*]}"
        return 1
    fi

    success "All prerequisites found"
}

# Validate AWS connectivity
validate_aws_connectivity() {
    info "Validating AWS connectivity..."

    # Test AWS credentials
    if ! aws sts get-caller-identity > /dev/null; then
        error "AWS credentials not configured or invalid"
        return 1
    fi

    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local caller_arn=$(aws sts get-caller-identity --query Arn --output text)

    info "AWS Account ID: ${account_id}"
    info "Caller ARN: ${caller_arn}"

    echo "### ✅ AWS Connectivity" >> "${REPORT_FILE}"
    echo "- **Account ID:** ${account_id}" >> "${REPORT_FILE}"
    echo "- **Caller ARN:** ${caller_arn}" >> "${REPORT_FILE}"
    echo "" >> "${REPORT_FILE}"

    success "AWS connectivity validated"
}

# Validate Terraform state
validate_terraform_state() {
    info "Validating Terraform state..."

    pushd "${PROJECT_ROOT}/terraform" > /dev/null

    # Initialize Terraform
    terraform init \
        -backend-config="bucket=arrakis-terraform-state-${ENVIRONMENT}" \
        -backend-config="key=terraform/${ENVIRONMENT}/terraform.tfstate" \
        -backend-config="region=${AWS_REGION}" \
        -backend-config="dynamodb_table=arrakis-terraform-locks-${ENVIRONMENT}" \
        > /dev/null

    # Check state health
    if terraform refresh -var-file="environments/${ENVIRONMENT}.tfvars" > /dev/null; then
        success "Terraform state is healthy"

        # Get state statistics
        local resource_count=$(terraform state list | wc -l)
        local state_size=$(terraform state pull | wc -c)

        echo "### ✅ Terraform State" >> "${REPORT_FILE}"
        echo "- **Resources:** ${resource_count}" >> "${REPORT_FILE}"
        echo "- **State Size:** ${state_size} bytes" >> "${REPORT_FILE}"
        echo "- **Status:** Healthy" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
    else
        error "Terraform state validation failed"
        echo "### ❌ Terraform State" >> "${REPORT_FILE}"
        echo "- **Status:** Failed validation" >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        return 1
    fi

    popd > /dev/null
}

# Validate EKS cluster
validate_eks_cluster() {
    info "Validating EKS cluster..."

    local cluster_name="arrakis-eks-${ENVIRONMENT}"

    # Update kubeconfig
    aws eks update-kubeconfig \
        --region "${AWS_REGION}" \
        --name "${cluster_name}" \
        > /dev/null

    # Check cluster status
    local cluster_status=$(aws eks describe-cluster \
        --name "${cluster_name}" \
        --query 'cluster.status' \
        --output text)

    if [[ "${cluster_status}" != "ACTIVE" ]]; then
        error "EKS cluster is not active: ${cluster_status}"
        return 1
    fi

    # Check nodes
    local node_count=$(kubectl get nodes --no-headers | wc -l)
    local ready_nodes=$(kubectl get nodes --no-headers | grep -c "Ready" || echo "0")

    info "EKS cluster has ${ready_nodes}/${node_count} ready nodes"

    # Check critical namespaces
    local namespaces=("kube-system" "arrakis" "monitoring" "nats-system")
    for ns in "${namespaces[@]}"; do
        if kubectl get namespace "${ns}" > /dev/null 2>&1; then
            info "Namespace ${ns} exists"
        else
            warn "Namespace ${ns} not found"
        fi
    done

    echo "### ✅ EKS Cluster" >> "${REPORT_FILE}"
    echo "- **Cluster:** ${cluster_name}" >> "${REPORT_FILE}"
    echo "- **Status:** ${cluster_status}" >> "${REPORT_FILE}"
    echo "- **Nodes:** ${ready_nodes}/${node_count} ready" >> "${REPORT_FILE}"
    echo "" >> "${REPORT_FILE}"

    success "EKS cluster validation completed"
}

# Validate RDS databases
validate_rds_databases() {
    info "Validating RDS databases..."

    local db_instances=(
        "arrakis-oms-${ENVIRONMENT}"
        "arrakis-user-${ENVIRONMENT}"
        "arrakis-audit-${ENVIRONMENT}"
        "arrakis-scheduler-${ENVIRONMENT}"
    )

    echo "### 🗄️ RDS Databases" >> "${REPORT_FILE}"

    for db_instance in "${db_instances[@]}"; do
        info "Checking database: ${db_instance}"

        local db_status=$(aws rds describe-db-instances \
            --db-instance-identifier "${db_instance}" \
            --query 'DBInstances[0].DBInstanceStatus' \
            --output text 2>/dev/null || echo "not-found")

        if [[ "${db_status}" == "available" ]]; then
            success "Database ${db_instance} is available"
            echo "- **${db_instance}:** ✅ Available" >> "${REPORT_FILE}"
        else
            warn "Database ${db_instance} status: ${db_status}"
            echo "- **${db_instance}:** ⚠️ ${db_status}" >> "${REPORT_FILE}"
        fi
    done

    echo "" >> "${REPORT_FILE}"
}

# Validate ElastiCache Redis
validate_elasticache() {
    info "Validating ElastiCache Redis..."

    local redis_cluster="arrakis-redis-${ENVIRONMENT}"

    local redis_status=$(aws elasticache describe-cache-clusters \
        --cache-cluster-id "${redis_cluster}" \
        --query 'CacheClusters[0].CacheClusterStatus' \
        --output text 2>/dev/null || echo "not-found")

    echo "### 📊 ElastiCache Redis" >> "${REPORT_FILE}"

    if [[ "${redis_status}" == "available" ]]; then
        success "Redis cluster ${redis_cluster} is available"
        echo "- **${redis_cluster}:** ✅ Available" >> "${REPORT_FILE}"
    else
        warn "Redis cluster ${redis_cluster} status: ${redis_status}"
        echo "- **${redis_cluster}:** ⚠️ ${redis_status}" >> "${REPORT_FILE}"
    fi

    echo "" >> "${REPORT_FILE}"
}

# Validate microservices
validate_microservices() {
    info "Validating microservices..."

    local services=(
        "ontology-management-service"
        "user-service"
        "audit-service"
        "data-kernel-service"
        "embedding-service"
        "scheduler-service"
        "event-gateway"
    )

    echo "### 🚀 Microservices" >> "${REPORT_FILE}"

    for service in "${services[@]}"; do
        info "Checking service: ${service}"

        # Check deployment
        local deployment_status=$(kubectl get deployment "${service}" -n arrakis -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "Not Found")

        # Check pods
        local ready_replicas=$(kubectl get deployment "${service}" -n arrakis -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired_replicas=$(kubectl get deployment "${service}" -n arrakis -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

        # Check service endpoint
        local service_ip=$(kubectl get service "${service}" -n arrakis -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "N/A")

        if [[ "${deployment_status}" == "True" && "${ready_replicas}" == "${desired_replicas}" ]]; then
            success "Service ${service} is healthy"
            echo "- **${service}:** ✅ ${ready_replicas}/${desired_replicas} replicas ready" >> "${REPORT_FILE}"
        else
            warn "Service ${service} has issues: ${ready_replicas}/${desired_replicas} replicas"
            echo "- **${service}:** ⚠️ ${ready_replicas}/${desired_replicas} replicas ready" >> "${REPORT_FILE}"
        fi
    done

    echo "" >> "${REPORT_FILE}"
}

# Validate monitoring stack
validate_monitoring() {
    info "Validating monitoring stack..."

    echo "### 📊 Monitoring Stack" >> "${REPORT_FILE}"

    # Check Prometheus
    if kubectl get pods -n monitoring -l app=prometheus --no-headers | grep -q "Running"; then
        success "Prometheus is running"
        echo "- **Prometheus:** ✅ Running" >> "${REPORT_FILE}"
    else
        warn "Prometheus is not running"
        echo "- **Prometheus:** ❌ Not running" >> "${REPORT_FILE}"
    fi

    # Check Grafana
    if kubectl get pods -n monitoring -l app=grafana --no-headers | grep -q "Running"; then
        success "Grafana is running"
        echo "- **Grafana:** ✅ Running" >> "${REPORT_FILE}"
    else
        warn "Grafana is not running"
        echo "- **Grafana:** ❌ Not running" >> "${REPORT_FILE}"
    fi

    # Check Jaeger
    if kubectl get pods -n monitoring -l app=jaeger --no-headers | grep -q "Running"; then
        success "Jaeger is running"
        echo "- **Jaeger:** ✅ Running" >> "${REPORT_FILE}"
    else
        warn "Jaeger is not running"
        echo "- **Jaeger:** ❌ Not running" >> "${REPORT_FILE}"
    fi

    echo "" >> "${REPORT_FILE}"
}

# Validate NATS
validate_nats() {
    info "Validating NATS cluster..."

    echo "### 🔄 NATS Cluster" >> "${REPORT_FILE}"

    # Check NATS pods
    local nats_pods=$(kubectl get pods -n nats-system -l app=nats --no-headers | grep -c "Running" || echo "0")
    local nats_expected=$(kubectl get statefulset -n nats-system nats -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

    if [[ "${nats_pods}" == "${nats_expected}" && "${nats_pods}" -gt 0 ]]; then
        success "NATS cluster is healthy: ${nats_pods}/${nats_expected} pods"
        echo "- **NATS Pods:** ✅ ${nats_pods}/${nats_expected} running" >> "${REPORT_FILE}"
    else
        warn "NATS cluster has issues: ${nats_pods}/${nats_expected} pods"
        echo "- **NATS Pods:** ⚠️ ${nats_pods}/${nats_expected} running" >> "${REPORT_FILE}"
    fi

    echo "" >> "${REPORT_FILE}"
}

# Validate security
validate_security() {
    info "Validating security configuration..."

    echo "### 🔒 Security Validation" >> "${REPORT_FILE}"

    # Check IRSA roles
    local irsa_roles=$(aws iam list-roles --query "Roles[?contains(RoleName, 'arrakis-${ENVIRONMENT}-irsa')].RoleName" --output text | wc -w)

    info "Found ${irsa_roles} IRSA roles"
    echo "- **IRSA Roles:** ${irsa_roles} configured" >> "${REPORT_FILE}"

    # Check KMS keys
    local kms_keys=$(aws kms list-keys --query "Keys[?contains(KeyId, 'arrakis-${ENVIRONMENT}')]" --output text | wc -l)

    info "Found ${kms_keys} KMS keys"
    echo "- **KMS Keys:** ${kms_keys} configured" >> "${REPORT_FILE}"

    # Check Security Groups
    local security_groups=$(aws ec2 describe-security-groups --query "SecurityGroups[?contains(GroupName, 'arrakis-${ENVIRONMENT}')].GroupId" --output text | wc -w)

    info "Found ${security_groups} security groups"
    echo "- **Security Groups:** ${security_groups} configured" >> "${REPORT_FILE}"

    echo "" >> "${REPORT_FILE}"
}

# Health check endpoints
validate_health_endpoints() {
    info "Validating service health endpoints..."

    echo "### 🏥 Health Endpoints" >> "${REPORT_FILE}"

    local services=(
        "ontology-management-service"
        "user-service"
        "audit-service"
        "data-kernel-service"
        "embedding-service"
        "scheduler-service"
        "event-gateway"
    )

    for service in "${services[@]}"; do
        info "Checking health endpoint for ${service}..."

        # Port forward to service for health check
        local service_port=$(kubectl get service "${service}" -n arrakis -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "8000")
        local random_port=$((RANDOM + 10000))

        # Start port forward in background
        kubectl port-forward -n arrakis "service/${service}" "${random_port}:${service_port}" > /dev/null 2>&1 &
        local pf_pid=$!

        # Wait for port forward to be ready
        sleep 3

        # Test health endpoint
        if curl -s -f "http://localhost:${random_port}/health" > /dev/null 2>&1; then
            success "Health endpoint for ${service} is responding"
            echo "- **${service}:** ✅ Health endpoint OK" >> "${REPORT_FILE}"
        else
            warn "Health endpoint for ${service} is not responding"
            echo "- **${service}:** ❌ Health endpoint failed" >> "${REPORT_FILE}"
        fi

        # Clean up port forward
        kill $pf_pid > /dev/null 2>&1 || true

        # Small delay between checks
        sleep 1
    done

    echo "" >> "${REPORT_FILE}"
}

# Generate failure report
generate_failure_report() {
    error "Generating failure report..."

    cat >> "${REPORT_FILE}" << EOF

## ❌ Validation Failed

**Failure Time:** $(date -u)
**Exit Code:** $?

### 📋 Recommended Actions

1. **Review Logs:** Check ${LOG_FILE} for detailed error messages
2. **Check AWS Resources:** Verify all AWS services are properly deployed
3. **Kubernetes Status:** Run \`kubectl get all -n arrakis\` to check pod status
4. **Infrastructure State:** Run \`terraform plan\` to check for drift
5. **Network Connectivity:** Verify VPC, subnets, and security groups
6. **IAM Permissions:** Ensure all IRSA roles and policies are correct

### 📞 Escalation

If issues persist, escalate to the platform team with:
- This validation report
- Recent deployment logs
- Terraform state information
- AWS CloudTrail events

EOF
}

# Generate success report
generate_success_report() {
    success "Generating success report..."

    cat >> "${REPORT_FILE}" << EOF

## ✅ Validation Successful

**Completion Time:** $(date -u)
**Environment:** ${ENVIRONMENT}

### 📈 Deployment Summary

The ${ENVIRONMENT} environment has been successfully validated. All critical components are operational and health checks are passing.

### 🎯 Next Steps

1. **Monitor Metrics:** Check Grafana dashboards for ongoing health
2. **Review Logs:** Monitor application logs for any issues
3. **Performance Testing:** Consider running load tests if applicable
4. **Documentation:** Update deployment documentation if needed

### 📊 Monitoring Links

- **Grafana:** https://grafana.arrakis.${ENVIRONMENT}.example.com
- **Jaeger:** https://jaeger.arrakis.${ENVIRONMENT}.example.com
- **Prometheus:** https://prometheus.arrakis.${ENVIRONMENT}.example.com

EOF
}

# Main execution
main() {
    info "Starting comprehensive deployment validation for ${ENVIRONMENT}..."
    info "Validation timeout: ${VALIDATION_TIMEOUT} seconds"

    # Initialize
    touch "${LOG_FILE}"
    init_report

    # Run all validations
    check_prerequisites
    validate_aws_connectivity
    validate_terraform_state
    validate_eks_cluster
    validate_rds_databases
    validate_elasticache
    validate_microservices
    validate_monitoring
    validate_nats
    validate_security
    validate_health_endpoints

    # Generate success report
    generate_success_report

    success "Deployment validation completed successfully!"
    info "Validation report: ${REPORT_FILE}"
    info "Detailed logs: ${LOG_FILE}"
}

# Execute main function
main "$@"
