variable "name" {
  type = string
}

variable "data_subnet_ids" {
  type = list(string)
}

variable "rds_security_group_id" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  type    = number
  default = 100
}

variable "multi_az" {
  description = "false in develop, true in prod."
  type        = bool
  default     = false
}

variable "engine_version" {
  description = "PostgreSQL major version (RDS picks the latest minor)."
  type        = string
  default     = "16"
}

variable "db_name" {
  type    = string
  default = "onboarding"
}

variable "master_username" {
  type    = string
  default = "onboarding"
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "skip_final_snapshot" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
