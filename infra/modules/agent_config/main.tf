# The agent's config bundles (models, prompts, copy), one directory per semver under `prefix`. The backend
# loads one at startup. New versions are published straight to the bucket with
# `python -m onboarding_agent.config publish`, which never overwrites a version; Terraform seeds only the
# baseline versions shipped with the agent, so a fresh environment has a bundle before the backend starts.

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "this" {
  bucket = "${var.name}-agent-config-${data.aws_caller_identity.current.account_id}"
}

# Object versions keep the history of every write, including a publish made outside Terraform.
resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket     = aws_s3_bucket.this.id
  policy     = data.aws_iam_policy_document.tls_only.json
  depends_on = [aws_s3_bucket_public_access_block.this]
}

locals {
  baseline_files = fileset(var.baseline_dir, "*/**")
  # A version counts as published once its config.json exists, so config.json goes after the rest.
  config_files = toset([for f in local.baseline_files : f if basename(f) == "config.json"])
  other_files  = toset([for f in local.baseline_files : f if basename(f) != "config.json"])
}

resource "aws_s3_object" "baseline" {
  for_each     = local.other_files
  bucket       = aws_s3_bucket.this.id
  key          = "${var.prefix}/${each.value}"
  source       = "${var.baseline_dir}/${each.value}"
  source_hash  = filemd5("${var.baseline_dir}/${each.value}")
  content_type = "application/json"

  depends_on = [aws_s3_bucket_server_side_encryption_configuration.this]
}

resource "aws_s3_object" "baseline_config" {
  for_each     = local.config_files
  bucket       = aws_s3_bucket.this.id
  key          = "${var.prefix}/${each.value}"
  source       = "${var.baseline_dir}/${each.value}"
  source_hash  = filemd5("${var.baseline_dir}/${each.value}")
  content_type = "application/json"

  depends_on = [aws_s3_object.baseline]
}

# ------------------------------------------------------------------------------------------ operator role
# The operator maintains the agent's prompts, copy and models: pulls a bundle, edits it, publishes it as a new
# version and restarts the backend. That is all this role can do. Publishing is create-only: the role may
# write an object only with If-None-Match: *, so S3 refuses to replace one, and it may not delete.

locals {
  operator_trust_account = length(var.operator_principal_arns) == 0
}

data "aws_iam_policy_document" "operator_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = local.operator_trust_account ? ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"] : var.operator_principal_arns
    }
    dynamic "condition" {
      for_each = local.operator_trust_account ? [1] : []
      content {
        test     = "Bool"
        variable = "aws:MultiFactorAuthPresent"
        values   = ["true"]
      }
    }
  }
}

resource "aws_iam_role" "operator" {
  name                 = "${var.name}-agent-config-operator"
  description          = "Publishes agent config bundle versions (prompts, copy, models) and restarts the backend to load them"
  assume_role_policy   = data.aws_iam_policy_document.operator_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "operator" {
  statement {
    sid       = "ListBundleVersions"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.this.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.prefix}/", "${var.prefix}/*"]
    }
  }

  statement {
    sid       = "ReadAndPublishBundles"
    actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
    resources = ["${aws_s3_bucket.this.arn}/${var.prefix}/*"]
  }

  # A published version is immutable: refuse any write that could replace an existing object.
  statement {
    sid       = "CreateOnly"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.this.arn}/*"]
    condition {
      test     = "StringNotEquals"
      variable = "s3:if-none-match"
      values   = ["*"]
    }
  }

  statement {
    sid       = "EncryptThroughS3Only"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [var.kms_key_arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["s3.${var.region}.amazonaws.com"]
    }
  }

  # The backend reads the bundle once, at startup: a new version takes effect when its tasks restart.
  statement {
    sid       = "RestartBackend"
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = [var.backend_service_arn]
  }

  statement {
    sid       = "WatchRestart"
    actions   = ["ecs:ListTasks", "ecs:DescribeTasks"]
    resources = ["*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.backend_cluster_arn]
    }
  }
}

resource "aws_iam_role_policy" "operator" {
  name   = "agent-config-operator"
  role   = aws_iam_role.operator.id
  policy = data.aws_iam_policy_document.operator.json
}
