variable "name" {
  description = "Full service name, e.g. onboarding-develop-backend."
  type        = string
}

variable "container_name" {
  description = "Short name; also the Service Connect port name and, for servers, the discovery name (backend, mock)."
  type        = string
}

variable "region" {
  type = string
}

variable "cluster_arn" {
  type = string
}

variable "image" {
  description = "Full image reference, <repo-url>:<tag>."
  type        = string
}

variable "container_port" {
  type = number
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_group_ids" {
  type = list(string)
}

variable "environment" {
  description = "Plain environment variables."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Env var name => Secrets Manager ARN (optionally with :json-key:: suffix). Injected by ECS at start."
  type        = map(string)
  default     = {}
}

variable "secret_arns" {
  description = "Secret ARNs (without JSON-key suffix) the execution role may read to inject var.secrets."
  type        = list(string)
  default     = []
}

variable "kms_key_arns" {
  description = "KMS keys the execution role may use to decrypt var.secret_arns."
  type        = list(string)
  default     = []
}

variable "task_role_policy_json" {
  description = "Inline policy for the task role (what the app itself may call). Used when attach_task_role_policy is true."
  type        = string
  default     = null
}

# A plain bool, because the policy JSON is unknown at plan time and cannot drive count.
variable "attach_task_role_policy" {
  type    = bool
  default = false
}

variable "service_connect_namespace_arn" {
  type = string
}

variable "service_connect_server" {
  description = "true: publish this service as <container_name>:<container_port> in Service Connect. false: client only."
  type        = bool
  default     = false
}

variable "target_group_arn" {
  description = "ALB target group to register with (frontend only)."
  type        = string
  default     = null
}

variable "health_check_grace_period_seconds" {
  type    = number
  default = 60
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "enable_execute_command" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
