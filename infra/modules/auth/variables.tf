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
