output "user_pool_arn" {
  value = aws_cognito_user_pool.agents.arn
}

output "user_pool_id" {
  value = aws_cognito_user_pool.agents.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.alb.id
}

output "user_pool_domain" {
  value = aws_cognito_user_pool_domain.this.domain
}

output "operator_client_id" {
  description = "The operator console's ALB app client; empty without an operator host."
  value       = one(aws_cognito_user_pool_client.operator_alb[*].id) == null ? "" : one(aws_cognito_user_pool_client.operator_alb[*].id)
}

output "operators_group" {
  value = aws_cognito_user_group.operators.name
}
