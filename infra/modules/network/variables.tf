variable "name" {
  description = "Name prefix for every resource, e.g. onboarding-develop."
  type        = string
}

variable "region" {
  description = "AWS region, used to build VPC endpoint service names."
  type        = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones, in the same order as the subnet CIDR lists."
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "public_subnet_cidrs" {
  description = "Public tier (ALB, NAT), one per AZ."
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "app_subnet_cidrs" {
  description = "Private app tier (ECS tasks), one per AZ."
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "data_subnet_cidrs" {
  description = "Private data tier (RDS subnet group), one per AZ. No route to the internet."
  type        = list(string)
  default     = ["10.0.20.0/24", "10.0.21.0/24"]
}

variable "single_nat_gateway" {
  description = "true: one NAT in the first AZ shared by every app subnet (develop). false: one NAT per AZ (prod)."
  type        = bool
  default     = true
}

variable "interface_endpoint_azs" {
  description = "AZs that get an ENI for each interface endpoint. develop uses only 2a to halve the hourly cost."
  type        = list(string)
  default     = ["ap-northeast-2a"]

  validation {
    condition     = length(var.interface_endpoint_azs) > 0
    error_message = "At least one AZ must host the interface endpoints."
  }
}

variable "interface_endpoint_services" {
  description = "Interface endpoint service suffixes (com.amazonaws.<region>.<suffix>)."
  type        = list(string)
  default     = ["bedrock-runtime", "secretsmanager", "ecr.api", "ecr.dkr", "logs"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
