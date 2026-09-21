# Security-group chain: alb -> (frontend -> backend -> (rds, mock), docs).
# Rules are separate resources so SGs can reference each other without cycles.

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "Public ALB"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-alb" })
}

resource "aws_security_group" "frontend" {
  name        = "${var.name}-frontend"
  description = "Frontend (Next.js) tasks"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-frontend" })
}

resource "aws_security_group" "backend" {
  name        = "${var.name}-backend"
  description = "Backend (FastAPI + LangGraph) tasks"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-backend" })
}

resource "aws_security_group" "mock" {
  count = var.enable_mocks ? 1 : 0

  name        = "${var.name}-mock"
  description = "Mock external systems (develop only)"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-mock" })
}

resource "aws_security_group" "docs" {
  name        = "${var.name}-docs"
  description = "Docs site (static, nginx) tasks"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-docs" })
}

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds"
  description = "RDS PostgreSQL"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-rds" })
}

# --- ALB --------------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  for_each = toset(var.alb_ingress_cidrs)

  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from the internet"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = each.value
}

# Port 80: redirects to 443 once a domain exists; serves the app until then.
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  for_each = toset(var.alb_ingress_cidrs)

  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the internet (redirect to HTTPS, or HTTP-only until the domain is ready)"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_egress_rule" "alb_to_frontend" {
  security_group_id            = aws_security_group.alb.id
  description                  = "ALB to frontend targets"
  ip_protocol                  = "tcp"
  from_port                    = var.frontend_port
  to_port                      = var.frontend_port
  referenced_security_group_id = aws_security_group.frontend.id
}

# The ALB's authenticate-cognito action calls the Cognito token and userinfo endpoints itself.
resource "aws_vpc_security_group_egress_rule" "alb_to_idp" {
  security_group_id = aws_security_group.alb.id
  description       = "ALB to the Cognito IdP endpoints"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# --- Frontend ---------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "frontend_from_alb" {
  security_group_id            = aws_security_group.frontend.id
  description                  = "From ALB"
  ip_protocol                  = "tcp"
  from_port                    = var.frontend_port
  to_port                      = var.frontend_port
  referenced_security_group_id = aws_security_group.alb.id
}

# --- Backend ----------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "backend_from_frontend" {
  security_group_id            = aws_security_group.backend.id
  description                  = "From frontend (Service Connect)"
  ip_protocol                  = "tcp"
  from_port                    = var.backend_port
  to_port                      = var.backend_port
  referenced_security_group_id = aws_security_group.frontend.id
}

# --- Docs -------------------------------------------------------------------

resource "aws_vpc_security_group_egress_rule" "alb_to_docs" {
  security_group_id            = aws_security_group.alb.id
  description                  = "ALB to docs targets"
  ip_protocol                  = "tcp"
  from_port                    = var.docs_port
  to_port                      = var.docs_port
  referenced_security_group_id = aws_security_group.docs.id
}

resource "aws_vpc_security_group_ingress_rule" "docs_from_alb" {
  security_group_id            = aws_security_group.docs.id
  description                  = "From ALB"
  ip_protocol                  = "tcp"
  from_port                    = var.docs_port
  to_port                      = var.docs_port
  referenced_security_group_id = aws_security_group.alb.id
}

# --- Mock -------------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "mock_from_backend" {
  count = var.enable_mocks ? 1 : 0

  security_group_id            = aws_security_group.mock[0].id
  description                  = "From backend (Service Connect)"
  ip_protocol                  = "tcp"
  from_port                    = var.mock_port
  to_port                      = var.mock_port
  referenced_security_group_id = aws_security_group.backend.id
}

# --- RDS --------------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "rds_from_backend" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from backend only"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.backend.id
}

# --- Task egress ------------------------------------------------------------
# Tasks reach AWS APIs through the VPC endpoints and the internet through NAT
# (Cognito/ALB signing keys, prod external systems), so egress stays open.

locals {
  task_security_group_ids = merge(
    {
      frontend = aws_security_group.frontend.id
      backend  = aws_security_group.backend.id
      docs     = aws_security_group.docs.id
    },
    var.enable_mocks ? { mock = aws_security_group.mock[0].id } : {},
  )
}

resource "aws_vpc_security_group_egress_rule" "task_all" {
  for_each = local.task_security_group_ids

  security_group_id = each.value
  description       = "All egress (VPC endpoints, NAT)"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# --- Interface endpoints: 443 from every task SG ----------------------------

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_tasks" {
  for_each = local.task_security_group_ids

  security_group_id            = var.endpoints_security_group_id
  description                  = "HTTPS from ${each.key} tasks"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = each.value
}

# ---------------------------------------------------------------------------
# KMS customer-managed key: RDS storage, RDS-managed master secret, app secrets
# ---------------------------------------------------------------------------

resource "aws_kms_key" "this" {
  description             = "${var.name}: RDS storage and Secrets Manager secrets"
  enable_key_rotation     = true
  deletion_window_in_days = var.kms_deletion_window_days
  tags                    = var.tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name}"
  target_key_id = aws_kms_key.this.key_id
}
