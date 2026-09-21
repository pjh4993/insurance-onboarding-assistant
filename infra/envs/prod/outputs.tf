output "base_url" {
  description = "Public URL; the deploy workflow smoke-tests <base_url>/healthz."
  value       = module.edge.base_url
}

output "alb_dns_name" {
  value = module.edge.alb_dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_names" {
  description = "Space-separated, for `aws ecs wait services-stable --services`."
  value = join(" ", compact([
    module.frontend.service_name,
    module.backend.service_name,
    var.enable_mocks ? module.mock[0].service_name : "",
    module.docs.service_name,
  ]))
}

output "ecr_repository_urls" {
  value = module.ci.ecr_repository_urls
}

output "deploy_role_arn" {
  value = module.ci.deploy_role_arn
}

output "db_address" {
  value = module.data.db_address
}

output "nat_public_ips" {
  description = "Egress IPs, for allow-listing at real external systems."
  value       = module.network.nat_public_ips
}

output "agent_config_uri" {
  description = "Where agent config bundles are published: python -m onboarding_agent.config publish <bundle-dir> <this>"
  value       = module.agent_config.uri
}

output "agent_config_operator_role_arn" {
  description = "The operator role: publishes agent config bundles and restarts the backend"
  value       = module.agent_config.operator_role_arn
}
