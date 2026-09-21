output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}

output "ecr_repository_urls" {
  description = "Service key => repository URL."
  value       = local.repo_urls
}
