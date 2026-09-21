environment = "develop"

# Cost-trimmed network: one NAT, interface endpoints only in 2a.
single_nat_gateway     = true
interface_endpoint_azs = ["ap-northeast-2a"]

enable_mocks  = true
desired_count = 1

db_multi_az            = false
db_deletion_protection = false

# Registered in Route 53; the registration created the public hosted zone.
domain_name = "onboardassist.click"

create_shared_ci_resources = true
github_oidc_subjects       = ["ref:refs/heads/develop"]

# Replace <ACCOUNT_ID>; must match -backend-config="bucket=...".
state_bucket_name = "onboarding-tfstate-<ACCOUNT_ID>"

# Grafana Cloud stack pjh4993 (region prod-ap-northeast-0). The auth header is set by hand in
# the secret onboarding-develop/otlp-headers; see docs/design/05-observability.md.
otlp_endpoint = "https://otlp-gateway-prod-ap-northeast-0.grafana.net/otlp"
