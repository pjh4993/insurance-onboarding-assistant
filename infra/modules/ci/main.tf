data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  partition   = data.aws_partition.current.partition
  oidc_host   = "token.actions.githubusercontent.com"
  oidc_arn    = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
  repo_urls   = var.create_shared_resources ? { for k, r in aws_ecr_repository.this : k => r.repository_url } : { for k, r in data.aws_ecr_repository.this : k => r.repository_url }
  repo_arns   = var.create_shared_resources ? [for r in aws_ecr_repository.this : r.arn] : [for r in data.aws_ecr_repository.this : r.arn]
  subject_ids = [for s in var.oidc_subjects : "repo:${var.github_repository}:${s}"]
}

# ---------------------------------------------------------------------------
# GitHub OIDC provider (account-wide, created once; an account holds only one
# provider per URL, so reuse it when another project already created it)
# ---------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
  # AWS no longer checks the thumbprint for this provider, but the API still accepts one.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
  tags            = var.tags
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://${local.oidc_host}"
}

# ---------------------------------------------------------------------------
# ECR repositories (shared by develop and prod)
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "this" {
  for_each = var.create_shared_resources ? var.ecr_repository_names : {}

  name                 = each.value
  image_tag_mutability = "IMMUTABLE" # a SHA tag always means the same image

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the newest 50 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 50
      }
      action = { type = "expire" }
    }]
  })
}

data "aws_ecr_repository" "this" {
  for_each = var.create_shared_resources ? {} : var.ecr_repository_names
  name     = each.value
}

# ---------------------------------------------------------------------------
# Deploy role assumed by GitHub Actions
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = local.subject_ids
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

# The deploy role runs `terraform apply` for the whole env, so it needs broad
# rights on the services the stack uses. PowerUserAccess covers everything but
# IAM; IAM is granted below only on resources carrying the project prefix.
resource "aws_iam_role_policy_attachment" "power_user" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/PowerUserAccess"
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid = "TerraformState"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:${local.partition}:s3:::${var.state_bucket_name}",
      "arn:${local.partition}:s3:::${var.state_bucket_name}/*",
    ]
  }

  statement {
    sid       = "TerraformLock"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:DescribeTable"]
    resources = ["arn:${local.partition}:dynamodb:*:${local.account_id}:table/${var.lock_table_name}"]
  }

  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = local.repo_arns
  }

  statement {
    sid     = "ManageProjectIam"
    actions = ["iam:*"]
    resources = [
      "arn:${local.partition}:iam::${local.account_id}:role/${var.project}-*",
      "arn:${local.partition}:iam::${local.account_id}:policy/${var.project}-*",
      "arn:${local.partition}:iam::${local.account_id}:oidc-provider/${local.oidc_host}",
    ]
  }

  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:${local.partition}:iam::${local.account_id}:role/aws-service-role/*"]
  }

  statement {
    sid       = "ReadIam"
    actions   = ["iam:Get*", "iam:List*"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
