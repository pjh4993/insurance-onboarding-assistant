variable "environment" {
  description = "develop | prod"
  type        = string
}

variable "project" {
  type    = string
  default = "onboarding"
}

variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "image_tag" {
  description = "Image tag (commit SHA) for all three services. Set by CI."
  type        = string
}

# --- network ----------------------------------------------------------------

variable "azs" {
  type    = list(string)
  default = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "single_nat_gateway" {
  type = bool
}

variable "interface_endpoint_azs" {
  type = list(string)
}

# --- services ---------------------------------------------------------------

variable "enable_mocks" {
  description = "Run the mock ECS service and point PARTNER/IDENTITY/CONTRACT at it. develop only."
  type        = bool
  default     = false
}

variable "desired_count" {
  description = "Tasks per service (spread across AZs)."
  type        = number
}

variable "frontend_cpu" {
  type    = number
  default = 512
}

variable "frontend_memory" {
  type    = number
  default = 1024
}

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

variable "agent_dev_auth" {
  description = "Frontend AGENT_DEV_AUTH. Stays true until the frontend verifies the ALB's x-amzn-oidc-data header; the ALB Cognito rule still gates /agent/* when a domain is set."
  type        = bool
  default     = true
}

variable "bedrock_model_id" {
  type    = string
  default = "global.anthropic.claude-sonnet-4-6"
}

variable "bedrock_foundation_models" {
  description = "Foundation model IDs the backend may invoke, each through its global cross-region inference profile (global.<id>)."
  type        = list(string)
  default = [
    "anthropic.claude-sonnet-4-6",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
  ]
}

variable "partner_api_url" {
  description = "Real partner API base URL. Ignored when enable_mocks = true."
  type        = string
  default     = ""
}

variable "identity_api_url" {
  description = "Real identity-verification API base URL. Ignored when enable_mocks = true."
  type        = string
  default     = ""
}

variable "contract_api_url" {
  description = "Real contract-management API base URL. Ignored when enable_mocks = true."
  type        = string
  default     = ""
}

# --- data -------------------------------------------------------------------

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_multi_az" {
  type = bool
}

variable "db_deletion_protection" {
  type = bool
}

# --- edge / auth ------------------------------------------------------------

variable "domain_name" {
  description = "Public hostname. Empty = HTTP-only ALB, no ACM certificate, no Cognito rule."
  type        = string
  default     = ""
}

variable "docs_domain_name" {
  description = "Hostname of the docs site, in route53_zone_name. Empty = no docs host."
  type        = string
  default     = ""
}

variable "route53_zone_name" {
  description = "Existing public hosted zone that holds domain_name (created by Route 53 domain registration). Empty = domain_name."
  type        = string
  default     = ""
}

# --- ci ---------------------------------------------------------------------

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. false when the AWS account already has one."
  type        = bool
  default     = false
}

variable "create_shared_ci_resources" {
  description = "Create the GitHub OIDC provider and ECR repositories. true in develop only."
  type        = bool
}

variable "github_oidc_subjects" {
  type = list(string)
}

variable "state_bucket_name" {
  description = "Must match the bucket passed with -backend-config."
  type        = string
}

variable "lock_table_name" {
  type    = string
  default = "onboarding-terraform-locks"
}
