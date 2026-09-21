variable "name" {
  description = "Environment name prefix, e.g. onboarding-develop."
  type        = string
}

variable "project" {
  description = "Project prefix shared by both environments; IAM permissions of the deploy role are scoped to it."
  type        = string
  default     = "onboarding"
}

variable "github_repository" {
  type    = string
  default = "pjh4993/bolttech-onboarding-assistant"
}

variable "oidc_subjects" {
  description = "Allowed token 'sub' claims, relative to repo:<github_repository>:. develop: ref:refs/heads/main. prod: environment:prod."
  type        = list(string)
}

variable "create_shared_resources" {
  description = "Create the account-wide GitHub OIDC provider and the ECR repositories. true in exactly one env (develop); the other looks them up."
  type        = bool
  default     = false
}

variable "ecr_repository_names" {
  description = "Service key => ECR repository name. Images are shared by both envs so prod promotes the exact SHA develop tested."
  type        = map(string)
  default = {
    backend  = "onboarding/backend"
    frontend = "onboarding/frontend"
    mock     = "onboarding/mock"
  }
}

variable "state_bucket_name" {
  description = "Terraform state bucket (from infra/bootstrap)."
  type        = string
}

variable "lock_table_name" {
  description = "Terraform lock table (from infra/bootstrap)."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
