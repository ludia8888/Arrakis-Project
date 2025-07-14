# Backup Module Providers Configuration
# Required providers for cross-region backup functionality

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
      configuration_aliases = [aws.replica]
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# Note: The main aws provider is inherited from the root module
# The aws.replica provider alias must be configured at the root level for cross-region backup functionality