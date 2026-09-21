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
