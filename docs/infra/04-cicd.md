# CI/CD design

GitHub Actions builds, tests and deploys. No AWS credentials are stored in GitHub: each deploy workflow assumes
an environment-specific deploy role through **OIDC**.

## 1. Pipeline

```mermaid
flowchart LR
    pr["Pull request<br/>or push to main"] --> checks["ci.yml<br/>lint, test, build,<br/>terraform fmt/validate,<br/>docker build"]
    push["Push to main"] --> dd["deploy-develop.yml<br/>push images (tag = SHA)<br/>terraform apply develop<br/>wait for ECS<br/>smoke test"]
    dd --> promote["Manual run with a SHA<br/>+ approval (Environment: prod)"]
    promote --> dp["deploy-prod.yml<br/>same image SHA<br/>terraform apply prod<br/>wait for ECS<br/>smoke test"]
```

| Workflow | Trigger | Steps |
|---|---|---|
| `ci.yml` | Pull request; push to `main` | **backend**: `uv sync`, `ruff check`, `pytest` against a Postgres 16 service container (graph tests use in-process fakes built from the seed customers). **mock**: `ruff check`, `pytest`. **frontend**: `pnpm install`, `pnpm lint`, `tsc --noEmit`, `pnpm build`. **terraform** (1.5.7): `fmt -recursive -check`, then `init -backend=false` and `validate` for `envs/develop`, `envs/prod` and `bootstrap`. **docker**: build all three images (no push). **docs**: `make docs-build`, the strict mkdocs build that fails on a broken link |
| `deploy-develop.yml` | Push to `main`; manual run | Runs only when the repository variable `AWS_DEPLOY_ROLE_ARN_DEVELOP` is set. **images**: assume the develop role, build and push `onboarding/{backend,mock,frontend}:<sha>` to ECR. **deploy**: `terraform init` with the state bucket, `terraform apply` on `envs/develop` with `image_tag=<sha>`, `.github/scripts/wait-for-rollout.sh`, then the smoke test |
| `deploy-prod.yml` | Manual (`workflow_dispatch`) with a full 40-character SHA | Runs in the `prod` GitHub Environment, so its required reviewers must approve. Checks out that SHA, assumes the prod role, checks that the backend and frontend images for that SHA exist in ECR (no rebuild), `terraform apply` on `envs/prod`, waits for ECS, smoke test |

Not built: a `terraform plan` posted on the PR, and running the frontend unit tests (`pnpm test`) in CI; both run
locally (see the README).

## 2. OIDC and roles

- The `ci` Terraform module in each environment creates that environment's deploy role. The GitHub OIDC
  identity provider is account-wide: develop creates it, prod looks it up.
- Each role's trust policy is limited to this repository (`pjh4993/bolttech-onboarding-assistant`) and one
  subject: the develop role to `ref:refs/heads/main`, the prod role to `environment:prod`.
  The repository sends GitHub's immutable subject, which carries the owner and repository ids
  (`repo:pjh4993@12472082/bolttech-onboarding-assistant@1379320933:…`), so a repository recreated under the same
  name gets no access. `modules/ci` variable `github_repository` holds that prefix.
- The role has `PowerUserAccess` (it applies the whole environment), plus IAM limited to `onboarding-*` roles and
  policies and the OIDC provider, read/write on the Terraform state bucket and lock table, and ECR push.
- Workflows request `id-token: write` and use `aws-actions/configure-aws-credentials` to assume the role.
  Credentials are short-lived.

## 3. Promotion by image SHA

Images are tagged with the git commit SHA, ECR tags are immutable, and prod never rebuilds. What runs in prod is
byte-for-byte the image that passed develop. `deploy-prod.yml` also checks out the same SHA, so the Terraform code
matches the images. Rolling back means deploying an earlier SHA.

## 4. Deployment safety

- **ECS deployment circuit breaker** with rollback: if new tasks fail to become healthy, ECS returns to the
  previous task definition. The workflow then fails at `wait-for-rollout.sh`.
- The workflow waits until each service's new tasks are serving and no old task is still running, not for the old
  tasks to be fully torn down (`aws ecs wait services-stable` waits about two minutes longer, after traffic has
  already moved). Containers get 10 s after SIGTERM (`stopTimeout`), and uvicorn gives open SSE streams 5 s; browsers
  reconnect to the new tasks.
- Rolling deploys keep 100% of tasks healthy and allow up to 200% during the switch.
- The ALB checks the frontend at `/api/healthz`. The images carry their own health checks (frontend `/api/healthz`, backend
  `/healthz`).
- There is no separate migration step. The backend creates missing tables and upserts the catalog seed when it
  starts, under a Postgres advisory lock. This does not alter existing tables; schema changes to them would need
  migrations (see [future-improvements.md](../decisions/future-improvements.md)).
- Deploy workflows use a concurrency group, so two deploys to one environment never overlap.

## 5. Smoke test

The design: after a develop deploy, check the health endpoint, then run one full onboarding with seed customer A
(partner match → profiling → recommendation → application → submission reference) against the develop mock.

Built: `<base_url>/healthz`, retried for up to 5 minutes. That URL reaches the frontend, which relays to the
backend's `/healthz`, so it proves the ALB, the frontend and the frontend-to-backend hop. The full seed-A run is
covered by the backend's scenario tests in CI (`test_customer_a_partner_match_to_submission`).

## 6. One-time setup

The deploy role is created by the environment it deploys, so the first apply is done by an admin, and GitHub
needs a few settings. The full ordered list is in [terraform.md](03-terraform.md#one-time-setup). The GitHub side:

| Setting | Value | Used by |
|---|---|---|
| Repository variable `AWS_DEPLOY_ROLE_ARN_DEVELOP` | `terraform output deploy_role_arn` in `envs/develop` | `deploy-develop.yml`; its jobs are skipped while it is empty |
| Repository variable `TF_STATE_BUCKET` | `state_bucket_name` output of `infra/bootstrap` | Both deploy workflows |
| Environment `prod` with required reviewers | — | `deploy-prod.yml` approval |
| Environment `prod` variable `AWS_DEPLOY_ROLE_ARN_PROD` | `terraform output deploy_role_arn` in `envs/prod` | `deploy-prod.yml` |

## 7. Scope for this submission

| Part | Status |
|---|---|
| CI checks | Built and running |
| Develop deploy workflow (OIDC → ECR → Terraform → ECS → smoke test) | Built. Runs once the develop deploy role variable is set |
| Prod promotion workflow | Built; not run, since the prod apply is deferred |
