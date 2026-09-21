// The deployed develop hosts (infra/envs/develop/terraform.tfvars). Override to point the dev projects elsewhere.
const trim = (u: string) => u.replace(/\/+$/, "");

export const DEV = {
  app: trim(process.env.DEV_APP_URL ?? "https://dev.app.onboardassist.click"),
  agent: trim(process.env.DEV_AGENT_URL ?? "https://dev.agent.onboardassist.click"),
  docs: trim(process.env.DEV_DOCS_URL ?? "https://dev.docs.onboardassist.click"),
};
