output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "frontend_security_group_id" {
  value = aws_security_group.frontend.id
}

output "backend_security_group_id" {
  value = aws_security_group.backend.id
}

output "mock_security_group_id" {
  value = var.enable_mocks ? aws_security_group.mock[0].id : null
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}

output "kms_key_arn" {
  value = aws_kms_key.this.arn
}
