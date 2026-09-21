# Shared by envs/develop and envs/prod (the files are identical);
# the environments differ only in terraform.tfvars and the state key.

data "aws_caller_identity" "current" {}

locals {
  name       = "${var.project}-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id

  mock_base = "http://mock:8080"

  external_urls = var.enable_mocks ? {
    PARTNER_API_URL  = "${local.mock_base}/partner"
    IDENTITY_API_URL = "${local.mock_base}/identity"
    CONTRACT_API_URL = "${local.mock_base}/contract"
    } : {
    PARTNER_API_URL  = var.partner_api_url
    IDENTITY_API_URL = var.identity_api_url
    CONTRACT_API_URL = var.contract_api_url
  }

  # Bedrock: the global inference profile plus the foundation models it routes
  # to (region-less ARN and the Seoul ARN), per infrastructure.md section 3.
  bedrock_resources = flatten([
    for m in var.bedrock_foundation_models : [
      "arn:aws:bedrock:${var.region}:${local.account_id}:inference-profile/global.${m}",
      "arn:aws:bedrock:::foundation-model/${m}",
      "arn:aws:bedrock:${var.region}::foundation-model/${m}",
    ]
  ])
}

# ---------------------------------------------------------------------------
# Network, security, data
# ---------------------------------------------------------------------------

module "network" {
  source = "../../modules/network"

  name                   = local.name
  region                 = var.region
  azs                    = var.azs
  single_nat_gateway     = var.single_nat_gateway
  interface_endpoint_azs = var.interface_endpoint_azs
}

module "security" {
  source = "../../modules/security"

  name                        = local.name
  vpc_id                      = module.network.vpc_id
  endpoints_security_group_id = module.network.endpoints_security_group_id
  enable_mocks                = var.enable_mocks
}

module "data" {
  source = "../../modules/data"

  name                  = local.name
  data_subnet_ids       = module.network.data_subnet_ids
  rds_security_group_id = module.security.rds_security_group_id
  kms_key_arn           = module.security.kms_key_arn
  instance_class        = var.db_instance_class
  multi_az              = var.db_multi_az
  deletion_protection   = var.db_deletion_protection
  skip_final_snapshot   = !var.db_deletion_protection
}

# ---------------------------------------------------------------------------
# Auth (Cognito) and edge (ALB) — HTTPS + Cognito only once a domain exists
# ---------------------------------------------------------------------------

module "auth" {
  source = "../../modules/auth"
  count  = var.domain_name == "" ? 0 : 1

  name                  = local.name
  domain_name           = var.domain_name
  cognito_domain_prefix = "${local.name}-${local.account_id}"
}

module "edge" {
  source = "../../modules/edge"

  name                  = local.name
  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  alb_security_group_id = module.security.alb_security_group_id
  domain_name           = var.domain_name
  route53_zone_name     = var.route53_zone_name
  deletion_protection   = var.environment == "prod"

  cognito = var.domain_name == "" ? null : {
    user_pool_arn       = module.auth[0].user_pool_arn
    user_pool_client_id = module.auth[0].user_pool_client_id
    user_pool_domain    = module.auth[0].user_pool_domain
  }
}

# ---------------------------------------------------------------------------
# CI: GitHub OIDC deploy role, ECR repositories
# ---------------------------------------------------------------------------

module "ci" {
  source = "../../modules/ci"

  name                        = local.name
  project                     = var.project
  oidc_subjects               = var.github_oidc_subjects
  create_shared_resources     = var.create_shared_ci_resources
  create_github_oidc_provider = var.create_github_oidc_provider
  state_bucket_name           = var.state_bucket_name
  lock_table_name             = var.lock_table_name
}

# ---------------------------------------------------------------------------
# ECS cluster and Service Connect namespace
# ---------------------------------------------------------------------------

resource "aws_service_discovery_http_namespace" "this" {
  name        = local.name
  description = "Service Connect namespace: backend:8000, mock:8080"
}

resource "aws_ecs_cluster" "this" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  service_connect_defaults {
    namespace = aws_service_discovery_http_namespace.this.arn
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE"]
}

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "backend_task" {
  statement {
    sid       = "InvokeClaude"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = local.bedrock_resources
  }

  statement {
    sid = "ReadAppSecrets"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      module.data.checkpoint_aes_key_secret_arn,
      module.data.session_hmac_key_secret_arn,
      module.data.db_master_secret_arn,
    ]
  }

  statement {
    sid       = "DecryptAppSecrets"
    actions   = ["kms:Decrypt"]
    resources = [module.security.kms_key_arn]
  }
}

module "backend" {
  source = "../../modules/service"

  name           = "${local.name}-backend"
  container_name = "backend"
  region         = var.region
  cluster_arn    = aws_ecs_cluster.this.arn
  image          = "${module.ci.ecr_repository_urls["backend"]}:${var.image_tag}"
  container_port = 8000
  cpu            = var.backend_cpu
  memory         = var.backend_memory
  desired_count  = var.desired_count

  subnet_ids         = module.network.app_subnet_ids
  security_group_ids = [module.security.backend_security_group_id]

  service_connect_namespace_arn = aws_service_discovery_http_namespace.this.arn
  service_connect_server        = true

  # BEDROCK_ENDPOINT_URL is deliberately unset: the SDK uses the regional
  # endpoint (reached through the bedrock-runtime VPC endpoint), even in develop.
  environment = merge(local.external_urls, {
    # No password in the URL: libpq reads PGPASSWORD (injected below).
    DATABASE_URL     = "postgresql+psycopg://${module.data.db_username}@${module.data.db_address}:${module.data.db_port}/${module.data.db_name}?sslmode=require"
    BEDROCK_MODEL_ID = var.bedrock_model_id
    AWS_REGION       = var.region
  })

  secrets = {
    PGPASSWORD         = "${module.data.db_master_secret_arn}:password::"
    CHECKPOINT_AES_KEY = module.data.checkpoint_aes_key_secret_arn
    SESSION_HMAC_KEY   = module.data.session_hmac_key_secret_arn
  }
  secret_arns = [
    module.data.db_master_secret_arn,
    module.data.checkpoint_aes_key_secret_arn,
    module.data.session_hmac_key_secret_arn,
  ]
  kms_key_arns = [module.security.kms_key_arn]

  task_role_policy_json   = data.aws_iam_policy_document.backend_task.json
  attach_task_role_policy = true
}

module "frontend" {
  source = "../../modules/service"

  name           = "${local.name}-frontend"
  container_name = "frontend"
  region         = var.region
  cluster_arn    = aws_ecs_cluster.this.arn
  image          = "${module.ci.ecr_repository_urls["frontend"]}:${var.image_tag}"
  container_port = 3000
  cpu            = var.frontend_cpu
  memory         = var.frontend_memory
  desired_count  = var.desired_count

  subnet_ids         = module.network.app_subnet_ids
  security_group_ids = [module.security.frontend_security_group_id]

  service_connect_namespace_arn = aws_service_discovery_http_namespace.this.arn
  service_connect_server        = false # client only: calls backend:8000
  target_group_arn              = module.edge.frontend_target_group_arn

  environment = {
    BACKEND_URL    = "http://backend:8000"
    AGENT_DEV_AUTH = tostring(var.agent_dev_auth)
    AWS_REGION     = var.region
  }

  depends_on = [module.edge]
}

module "mock" {
  source = "../../modules/service"
  count  = var.enable_mocks ? 1 : 0

  name           = "${local.name}-mock"
  container_name = "mock"
  region         = var.region
  cluster_arn    = aws_ecs_cluster.this.arn
  image          = "${module.ci.ecr_repository_urls["mock"]}:${var.image_tag}"
  container_port = 8080
  desired_count  = 1

  subnet_ids         = module.network.app_subnet_ids
  security_group_ids = [module.security.mock_security_group_id]

  service_connect_namespace_arn = aws_service_discovery_http_namespace.this.arn
  service_connect_server        = true
}
