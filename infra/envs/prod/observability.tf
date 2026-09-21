# OTLP export of traces and logs (Grafana Cloud). Identical in envs/develop and envs/prod.
# Off until otlp_endpoint is set. The auth header lives in Secrets Manager and is set by hand
# (see docs/design/05-observability.md), never in tfvars.

variable "otlp_endpoint" {
  description = "OTLP/HTTP base URL, e.g. https://otlp-gateway-prod-ap-northeast-0.grafana.net/otlp. null = no export."
  type        = string
  default     = null
}

variable "log_max_chars" {
  description = "Cap on one log line (message, and separately a traceback's tail) and on span attribute values."
  type        = number
  default     = 2000
}

locals {
  otel_enabled = var.otlp_endpoint != null

  otel_common_env = merge(
    {
      LOG_MAX_CHARS = tostring(var.log_max_chars)
    },
    local.otel_enabled ? {
      OTEL_EXPORTER_OTLP_ENDPOINT = var.otlp_endpoint
      OTEL_EXPORTER_OTLP_PROTOCOL = "http/protobuf"
      OTEL_RESOURCE_ATTRIBUTES    = "deployment.environment=${var.environment}"
    } : {},
  )

  otel_secrets     = local.otel_enabled ? { OTEL_EXPORTER_OTLP_HEADERS = aws_secretsmanager_secret.otlp_headers[0].arn } : {}
  otel_secret_arns = local.otel_enabled ? [aws_secretsmanager_secret.otlp_headers[0].arn] : []
}

resource "aws_secretsmanager_secret" "otlp_headers" {
  count = local.otel_enabled ? 1 : 0

  name        = "${local.name}/otlp-headers"
  description = "OTEL_EXPORTER_OTLP_HEADERS for Grafana Cloud: Authorization=Basic <base64(instance_id:token)>"
  kms_key_id  = module.security.kms_key_arn
}

# ECS cannot start a task whose secret has no value, so seed a placeholder; the real value is set
# outside Terraform and left alone here.
resource "aws_secretsmanager_secret_version" "otlp_headers" {
  count = local.otel_enabled ? 1 : 0

  secret_id     = aws_secretsmanager_secret.otlp_headers[0].id
  secret_string = "Authorization=Basic unset"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

output "otlp_headers_secret_arn" {
  value = local.otel_enabled ? aws_secretsmanager_secret.otlp_headers[0].arn : null
}
