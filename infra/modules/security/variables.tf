variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "endpoints_security_group_id" {
  description = "SG of the interface endpoints (owned by the network module); this module adds its ingress rules."
  type        = string
}

variable "enable_mocks" {
  description = "Create sg-mock (develop only)."
  type        = bool
  default     = false
}

variable "alb_ingress_cidrs" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "frontend_port" {
  type    = number
  default = 3000
}

variable "backend_port" {
  type    = number
  default = 8000
}

variable "mock_port" {
  type    = number
  default = 8080
}

variable "kms_deletion_window_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
