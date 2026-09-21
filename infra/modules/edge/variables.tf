variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "frontend_port" {
  type    = number
  default = 3000
}

variable "health_check_path" {
  description = "Target-group health check on the frontend. Kept independent of the backend so a backend outage does not cycle frontend tasks."
  type        = string
  default     = "/api/healthz"
}

variable "idle_timeout" {
  description = "Seconds. Longer than the 60 s default so SSE streams survive."
  type        = number
  default     = 300
}

variable "domain_name" {
  description = "Public hostname. Empty = HTTP listener only, no certificate, no Cognito rule (the domain is still being registered)."
  type        = string
  default     = ""
}

variable "agent_domain_name" {
  description = "Hostname of the agent console, in the same zone as domain_name. Every path on it requires the Cognito login, and the app host's agent paths redirect to it. Empty = the console stays on domain_name under the agent paths."
  type        = string
  default     = ""
}

variable "docs_domain_name" {
  description = "Hostname of the docs site, in the same zone as domain_name. Empty, or no domain_name = no docs host."
  type        = string
  default     = ""
}

variable "route53_zone_name" {
  description = "Hosted zone that holds domain_name. Defaults to domain_name itself."
  type        = string
  default     = ""
}

variable "cognito" {
  description = "Cognito settings for the /agent/* authenticate rule. Required when domain_name is set."
  type = object({
    user_pool_arn       = string
    user_pool_client_id = string
    user_pool_domain    = string
  })
  default = null
}

variable "agent_path_patterns" {
  description = "Paths that require Cognito login. The agent API is included so the ALB session cookie covers the console's own calls."
  type        = list(string)
  default     = ["/agent", "/agent/*", "/api/agent/*"]
}

variable "ssl_policy" {
  type    = string
  default = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "docs_port" {
  type    = number
  default = 8080
}

variable "operator_domain_name" {
  description = "The operator console's host (e.g. dev.operator.example.com); empty: none."
  type        = string
  default     = ""
}

variable "operator_client_id" {
  description = "The Cognito app client the operator host logs in with; required when operator_domain_name is set."
  type        = string
  default     = ""
}
