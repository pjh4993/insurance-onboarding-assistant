# Read-only role for the Grafana Cloud CloudWatch data source ("Grafana Assume Role").
# Both values come from the data source's Settings tab; the role is skipped until they are set.

variable "grafana_aws_account_id" {
  description = "Grafana Cloud's AWS account id, shown on the CloudWatch data source Settings tab."
  type        = string
  default     = null
}

variable "grafana_external_id" {
  description = "External ID for this Grafana stack, shown on the CloudWatch data source Settings tab."
  type        = string
  default     = null
}

locals {
  grafana_enabled = var.grafana_aws_account_id != null && var.grafana_external_id != null
}

data "aws_iam_policy_document" "grafana_assume" {
  count = local.grafana_enabled ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.grafana_aws_account_id}:root"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.grafana_external_id]
    }
  }
}

data "aws_iam_policy_document" "grafana_read" {
  statement {
    sid = "Metrics"
    actions = [
      "cloudwatch:DescribeAlarms",
      "cloudwatch:DescribeAlarmsForMetric",
      "cloudwatch:DescribeAlarmHistory",
      "cloudwatch:GetInsightRuleReport",
      "cloudwatch:GetMetricData",
      "cloudwatch:ListMetrics",
      "ec2:DescribeRegions",
      "tag:GetResources",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ListLogGroups"
    actions = [
      "logs:DescribeLogGroups",
      "logs:GetQueryResults",
      "logs:StopQuery",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ReadProjectLogs"
    actions = [
      "logs:GetLogEvents",
      "logs:GetLogGroupFields",
      "logs:StartQuery",
    ]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/onboarding-*",
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/onboarding-*:*",
    ]
  }
}

resource "aws_iam_role" "grafana" {
  count = local.grafana_enabled ? 1 : 0

  name               = "onboarding-grafana-cloudwatch"
  assume_role_policy = data.aws_iam_policy_document.grafana_assume[0].json
}

resource "aws_iam_role_policy" "grafana" {
  count = local.grafana_enabled ? 1 : 0

  name   = "cloudwatch-read"
  role   = aws_iam_role.grafana[0].id
  policy = data.aws_iam_policy_document.grafana_read.json
}

output "grafana_role_arn" {
  description = "Paste into the CloudWatch data source as the Assume Role ARN."
  value       = local.grafana_enabled ? aws_iam_role.grafana[0].arn : null
}
