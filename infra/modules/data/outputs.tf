output "db_address" {
  value = aws_db_instance.this.address
}

output "db_port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "db_username" {
  value = aws_db_instance.this.username
}

output "db_master_secret_arn" {
  description = "RDS-managed secret holding {username, password}."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "checkpoint_aes_key_secret_arn" {
  value = aws_secretsmanager_secret.checkpoint_aes_key.arn
}

output "session_hmac_key_secret_arn" {
  value = aws_secretsmanager_secret.session_hmac_key.arn
}
