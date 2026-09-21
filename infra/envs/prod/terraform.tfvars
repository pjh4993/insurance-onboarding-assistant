environment = "prod"

# Full HA: NAT and interface endpoints in both AZs.
single_nat_gateway     = false
interface_endpoint_azs = ["ap-northeast-2a", "ap-northeast-2c"]

enable_mocks  = false
desired_count = 2

db_instance_class      = "db.t4g.small"
db_multi_az            = true
db_deletion_protection = true

# The real partner / identity / contract systems do not exist yet.
# Placeholders on the reserved .invalid TLD until they do.
partner_api_url  = "https://partner.invalid"
identity_api_url = "https://identity.invalid"
contract_api_url = "https://contract.invalid"

# Hosts in the zone develop's domain registration created (develop: dev.app., dev.agent., dev.docs.).
domain_name          = "app.onboardassist.click"
agent_domain_name    = "agent.onboardassist.click"
docs_domain_name     = "docs.onboardassist.click"
operator_domain_name = "operator.onboardassist.click"
route53_zone_name    = "onboardassist.click"

# develop owns the OIDC provider and ECR repositories; prod looks them up.
create_shared_ci_resources = false
github_oidc_subjects       = ["environment:prod"]

state_bucket_name = "onboarding-tfstate-<ACCOUNT_ID>"
