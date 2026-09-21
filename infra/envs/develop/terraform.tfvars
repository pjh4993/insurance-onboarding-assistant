environment = "develop"

# Cost-trimmed network: one NAT, interface endpoints only in 2a.
single_nat_gateway     = true
interface_endpoint_azs = ["ap-northeast-2a"]

enable_mocks  = true
desired_count = 1

db_multi_az            = false
db_deletion_protection = false

# onboardassist.click is registered in Route 53, which created the public hosted
# zone. Each environment gets a customer host, an agent host and a docs host in it
# (develop: dev.app., dev.agent., dev.docs.; prod: app., agent., docs.); the apex
# itself serves nothing.
domain_name          = "dev.app.onboardassist.click"
agent_domain_name    = "dev.agent.onboardassist.click"
docs_domain_name     = "dev.docs.onboardassist.click"
operator_domain_name = "dev.operator.onboardassist.click"
route53_zone_name    = "onboardassist.click"

# Predefined logins for demos and tests; passwords in the secret onboarding-develop/demo-accounts
# (docs/infra/03-terraform.md). Prod has none: its staff are created by hand.
cognito_accounts = {
  "demo-agent-1@onboardassist.click" = {
    description = "Support agent: takes handed-off sessions on the agent host"
  }
  "demo-agent-2@onboardassist.click" = {
    description = "Second support agent, for claiming and reassigning handoffs"
  }
  "demo-operator@onboardassist.click" = {
    groups      = ["operators"]
    description = "Operator: publishes agent config versions on the operator host (and can log in as an agent)"
  }
}

create_shared_ci_resources = true
github_oidc_subjects       = ["ref:refs/heads/develop"]

# Replace <ACCOUNT_ID>; must match -backend-config="bucket=...".
state_bucket_name = "onboarding-tfstate-<ACCOUNT_ID>"

# Grafana Cloud stack pjh4993 (region prod-ap-northeast-0). The auth header is set by hand in
# the secret onboarding-develop/otlp-headers; see docs/design/05-observability.md.
otlp_endpoint = "https://otlp-gateway-prod-ap-northeast-0.grafana.net/otlp"
