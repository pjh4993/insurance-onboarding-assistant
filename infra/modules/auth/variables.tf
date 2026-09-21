variable "name" {
  type = string
}

variable "domain_name" {
  description = "Public hostname of the app; the ALB's Cognito callback is https://<domain_name>/oauth2/idpresponse."
  type        = string
}

variable "cognito_domain_prefix" {
  description = "Hosted UI prefix (<prefix>.auth.<region>.amazoncognito.com). Must be globally unique."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "operator_domain_name" {
  description = "The operator console's host; empty: no operator console."
  type        = string
  default     = ""
}

variable "accounts" {
  description = "Predefined accounts by email: their groups (e.g. [\"operators\"]; none: a support agent) and what they are for."
  type = map(object({
    groups      = optional(list(string), [])
    description = optional(string, "")
  }))
  default = {}

  validation {
    condition     = alltrue([for a in values(var.accounts) : alltrue([for g in a.groups : contains(["operators"], g)])])
    error_message = "The pool has one group, \"operators\"."
  }
}
