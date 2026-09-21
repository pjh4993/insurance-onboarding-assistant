variable "name" {
  description = "Name prefix, e.g. onboarding-develop."
  type        = string
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
