variable "name" {
  description = "Name prefix, e.g. onboarding-develop."
  type        = string
}

variable "region" {
  type = string
}

variable "kms_key_arn" {
  description = "KMS key the bundle objects are encrypted with; the backend task can already decrypt with it."
  type        = string
}

variable "prefix" {
  description = "Key prefix holding one directory per bundle version (<prefix>/<semver>/config.json)."
  type        = string
  default     = "agent-config"
}

variable "baseline_dir" {
  description = "Local directory of baseline bundle versions to seed (the ones shipped in the agent package)."
  type        = string
}

variable "operator_principal_arns" {
  description = "IAM principals (users, or IAM Identity Center permission-set roles) that may assume the operator role. Empty: any principal of this account that signed in with MFA."
  type        = list(string)
  default     = []
}

variable "backend_service_arn" {
  description = "The backend ECS service; the operator may restart it (force a new deployment) so it loads a newly published bundle."
  type        = string
}

variable "backend_cluster_arn" {
  description = "The ECS cluster of the backend service."
  type        = string
}
