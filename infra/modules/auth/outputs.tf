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
