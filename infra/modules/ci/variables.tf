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
  # The repo sends immutable subjects (owner and repo ids), so a recreated repo of the same name gets no access.
  description = "Repository part of the OIDC 'sub' claim: <owner>@<owner_id>/<repo>@<repo_id> (GET repos/{repo}/actions/oidc/customization/sub)."
  type        = string
  default     = "pjh4993@12472082/bolttech-onboarding-assistant@1379320933"
}

variable "oidc_subjects" {
  description = "Allowed token 'sub' claims, relative to repo:<github_repository>:. develop: ref:refs/heads/main. prod: environment:prod."
  type        = list(string)
}

variable "create_shared_resources" {
  description = "Create the ECR repositories. true in exactly one env (develop); the other looks them up."
  type        = bool
  default     = false
}

variable "create_github_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider. false when the account already has one (only one per URL is allowed); it is then looked up."
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
