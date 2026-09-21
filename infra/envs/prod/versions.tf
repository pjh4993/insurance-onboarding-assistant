terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70, < 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }

  # Partial configuration: the bucket name contains the account ID, so it is
  # passed at init time:
  #   terraform init -backend-config="bucket=<state bucket from infra/bootstrap>"
  backend "s3" {
    key            = "envs/prod/terraform.tfstate"
    region         = "ap-northeast-2"
    dynamodb_table = "onboarding-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "bolttech-onboarding-assistant"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
