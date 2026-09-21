# Agent login. Customers never have accounts (they use session links).

resource "aws_cognito_user_pool" "agents" {
  name = "${var.name}-agents"

  # Agents are staff: an admin creates each account, nobody signs up.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  deletion_protection = "ACTIVE"
  tags                = var.tags
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.agents.id
}

# App client used by the ALB authenticate-cognito action.
resource "aws_cognito_user_pool_client" "alb" {
  name         = "${var.name}-alb"
  user_pool_id = aws_cognito_user_pool.agents.id

  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = ["https://${var.domain_name}/oauth2/idpresponse"]
  logout_urls                          = ["https://${var.domain_name}/"]
  prevent_user_existence_errors        = "ENABLED"
}
