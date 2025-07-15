# DNS Module Providers Configuration
# Required providers for DNS and SSL certificate management

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}
