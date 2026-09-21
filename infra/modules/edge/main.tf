locals {
  https_enabled = var.domain_name != ""
  docs_enabled  = local.https_enabled && var.docs_domain_name != ""
  agent_enabled = local.https_enabled && var.agent_domain_name != ""
  # The operator host needs its own Cognito client (its callback names that host). Gated on the host alone:
  # the client's id is unknown until the client exists, and count/for_each must be known at plan time.
  operator_enabled = local.https_enabled && var.operator_domain_name != ""
  hostnames = compact([
    var.domain_name,
    local.docs_enabled ? var.docs_domain_name : "",
    local.agent_enabled ? var.agent_domain_name : "",
    local.operator_enabled ? var.operator_domain_name : "",
  ])
  zone_name = var.route53_zone_name != "" ? var.route53_zone_name : var.domain_name
}

resource "aws_lb" "this" {
  name               = "${var.name}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_security_group_id]

  idle_timeout               = var.idle_timeout
  drop_invalid_header_fields = true
  enable_deletion_protection = var.deletion_protection

  tags = var.tags
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.name}-fe"
  port        = var.frontend_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  deregistration_delay = 30

  health_check {
    path                = var.health_check_path
    matcher             = "200-399"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

resource "aws_lb_target_group" "docs" {
  name        = "${var.name}-docs"
  port        = var.docs_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  deregistration_delay = 5 # static files: nothing in flight worth waiting for

  health_check {
    path                = "/"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# HTTP-only mode (no domain yet): port 80 forwards to the frontend.
# HTTPS mode: port 80 redirects to 443.
# ---------------------------------------------------------------------------

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  dynamic "default_action" {
    for_each = local.https_enabled ? [] : [1]
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.frontend.arn
    }
  }

  dynamic "default_action" {
    for_each = local.https_enabled ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# HTTPS: ACM certificate (DNS-validated in Route 53), listener, Cognito rule
# ---------------------------------------------------------------------------

data "aws_route53_zone" "this" {
  count = local.https_enabled ? 1 : 0

  name         = local.zone_name
  private_zone = false
}

resource "aws_acm_certificate" "this" {
  count = local.https_enabled ? 1 : 0

  domain_name               = var.domain_name
  subject_alternative_names = [for h in local.hostnames : h if h != var.domain_name]
  validation_method         = "DNS"
  tags                      = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = local.https_enabled ? {
    for o in aws_acm_certificate.this[0].domain_validation_options : o.domain_name => o
  } : {}

  zone_id         = data.aws_route53_zone.this[0].zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  count = local.https_enabled ? 1 : 0

  certificate_arn         = aws_acm_certificate.this[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

resource "aws_route53_record" "alias" {
  for_each = local.https_enabled ? toset(local.hostnames) : toset([])

  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = each.value
  type    = "A"

  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}

resource "aws_lb_listener" "https" {
  count = local.https_enabled ? 1 : 0

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = var.ssl_policy
  certificate_arn   = aws_acm_certificate_validation.this[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  tags = var.tags
}

# Agents log in with Cognito at the ALB, which then forwards with the signed x-amzn-oidc-data header the
# frontend verifies. With an agent host, every path on it needs the login (the frontend serves the console
# at its root); without one, only the agent paths on the app host do.
resource "aws_lb_listener_rule" "agent_cognito" {
  count = local.https_enabled ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 10

  action {
    type = "authenticate-cognito"

    authenticate_cognito {
      user_pool_arn              = var.cognito.user_pool_arn
      user_pool_client_id        = var.cognito.user_pool_client_id
      user_pool_domain           = var.cognito.user_pool_domain
      on_unauthenticated_request = "authenticate"
      scope                      = "openid email profile"
      session_timeout            = 28800
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  dynamic "condition" {
    for_each = local.agent_enabled ? [] : [1]
    content {
      path_pattern {
        values = var.agent_path_patterns
      }
    }
  }

  # One host only: the Cognito app client's callback URL names it, and the docs host shares the listener.
  condition {
    host_header {
      values = [local.agent_enabled ? var.agent_domain_name : var.domain_name]
    }
  }

  lifecycle {
    precondition {
      condition     = var.cognito != null
      error_message = "cognito must be set when domain_name is set."
    }
  }
}

# With an agent host, the app host is for customers. Its agent API answers 404 here, so no agent data is
# reachable without the login; /agent pages reach the frontend, which redirects them to the agent host (an ALB
# redirect action would write ":443" into the URL).
resource "aws_lb_listener_rule" "agent_api_off_app_host" {
  count = local.agent_enabled ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 15

  action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      message_body = "{\"error\":\"not_found\"}"
      status_code  = "404"
    }
  }

  condition {
    path_pattern {
      values = ["/api/agent/*"]
    }
  }

  condition {
    host_header {
      values = [var.domain_name]
    }
  }
}

# Same rule and priority as the redirect it replaces.
moved {
  from = aws_lb_listener_rule.agent_paths_to_agent_host[0]
  to   = aws_lb_listener_rule.agent_api_off_app_host[0]
}

# ---------------------------------------------------------------------------
# Docs host: the design docs site on its own hostname, public (no login).
# ---------------------------------------------------------------------------

resource "aws_lb_listener_rule" "docs" {
  count = local.docs_enabled ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.docs.arn
  }

  condition {
    host_header {
      values = [var.docs_domain_name]
    }
  }
}

# The rule first authenticated, then matched /docs on the app host; keep the same rule (and its priority)
# rather than recreate it.
moved {
  from = aws_lb_listener_rule.docs_cognito[0]
  to   = aws_lb_listener_rule.docs
}

moved {
  from = aws_lb_listener_rule.docs
  to   = aws_lb_listener_rule.docs[0]
}


# ---------------------------------------------------------------------------
# Operator console: its own host, login through its own Cognito client
# ---------------------------------------------------------------------------

# The operator API answers 404 anywhere but the operator host, before the agent host's catch-all login rule.
resource "aws_lb_listener_rule" "operator_api_off_other_hosts" {
  count = local.operator_enabled ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 5

  action {
    type = "fixed-response"

    fixed_response {
      content_type = "application/json"
      message_body = "{\"error\":\"not_found\"}"
      status_code  = "404"
    }
  }

  condition {
    path_pattern {
      values = ["/api/operator/*"]
    }
  }

  condition {
    host_header {
      values = compact([var.domain_name, local.agent_enabled ? var.agent_domain_name : ""])
    }
  }
}

# Every path on the operator host needs the login; the frontend serves the console at its root and verifies
# the forwarded access token (the operator client, the operators group) before relaying to the backend.
resource "aws_lb_listener_rule" "operator_cognito" {
  count = local.operator_enabled ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 11

  action {
    type = "authenticate-cognito"

    authenticate_cognito {
      user_pool_arn              = var.cognito.user_pool_arn
      user_pool_client_id        = var.operator_client_id
      user_pool_domain           = var.cognito.user_pool_domain
      on_unauthenticated_request = "authenticate"
      scope                      = "openid email profile"
      session_timeout            = 28800
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  condition {
    host_header {
      values = [var.operator_domain_name]
    }
  }
}
