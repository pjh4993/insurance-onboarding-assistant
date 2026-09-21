output "alb_arn" {
  value = aws_lb.this.arn
}

output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "frontend_target_group_arn" {
  value = aws_lb_target_group.frontend.arn
}

output "docs_target_group_arn" {
  value = aws_lb_target_group.docs.arn
}

output "base_url" {
  description = "URL the smoke test calls."
  value       = local.https_enabled ? "https://${var.domain_name}" : "http://${aws_lb.this.dns_name}"
}

output "https_enabled" {
  value = local.https_enabled
}
