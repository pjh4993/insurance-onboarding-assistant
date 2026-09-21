# Observability

The backend and the frontend send traces and logs to Grafana Cloud over OTLP. Logs also go to stdout, which ECS
ships to CloudWatch Logs (`/ecs/onboarding-<env>-{backend,frontend,mock}`), so they stay readable when OTLP export
is off or failing.

## 1. What is sent

| | Backend (FastAPI) | Frontend (Next.js server) |
|---|---|---|
| Traces | One span per request, httpx calls to partner, identity and contract admin, botocore calls to Bedrock | One span per route and render, and each `fetch` to the backend |
| Logs | Every record at `LOG_LEVEL` (default INFO) and above from the app; library loggers at WARNING | `lib/server/log.ts` and Next's unhandled request errors (`onRequestError`) |
| Setup | `backend/app/telemetry.py` | `frontend/instrumentation.ts` |

The frontend passes `traceparent` to the backend, so a relayed call and the API call it causes are one trace.
Logs written inside a span carry its trace id (in the OTLP record, and as `trace=` in the stdout line).

## 2. Keeping it small

| Control | Where | Effect |
|---|---|---|
| `LOG_MAX_CHARS` (default 2000) | Both services | A log message is cut to this many characters from the head, and a traceback or stack to this many from the tail, where the error is. The cut is marked `…[+N chars]`. The same cap applies to span attribute values |
| Quiet paths | Both services | `/healthz` and the SSE `/stream` endpoints produce no spans. A stream is one long connection, so its span would say nothing per event. Health-check access logs are dropped |
| Sub-spans | Backend | The ASGI `receive`/`send` spans are not recorded |
| Library loggers | Backend | `httpx`, `botocore`, `psycopg`, `langchain`, `langgraph` and similar log at WARNING only |

Traces are not sampled: after the quiet paths are removed, a demo's traffic is small. `OTEL_TRACES_SAMPLER` can
change that without code.

## 3. Turning it on

Terraform leaves export off until `otlp_endpoint` is set in the environment's `terraform.tfvars`.

1. In Grafana Cloud, open the stack, then **Connections → OpenTelemetry (OTLP)**. Generate a token there. The page
   shows the endpoint (`https://otlp-gateway-<region>.grafana.net/otlp`) and a ready-made
   `OTEL_EXPORTER_OTLP_HEADERS` value (`Authorization=Basic <base64(instance_id:token)>`).
2. Set `otlp_endpoint` in `infra/envs/<env>/terraform.tfvars` and apply. This creates the secret
   `onboarding-<env>/otlp-headers` with a placeholder and wires both services to it.
3. Put the real header into the secret yourself (the token never goes into Terraform, git or chat), then restart
   the tasks so ECS injects it:

   ```bash
   aws secretsmanager put-secret-value --secret-id onboarding-develop/otlp-headers \
     --secret-string 'Authorization=Basic <value from step 1>'
   aws ecs update-service --cluster onboarding-develop --service onboarding-develop-backend --force-new-deployment
   aws ecs update-service --cluster onboarding-develop --service onboarding-develop-frontend --force-new-deployment
   ```

Locally, export stays off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set in the environment.

## 4. CloudWatch in Grafana

The same stack can read CloudWatch metrics (ALB, ECS, RDS) and the log groups through the CloudWatch data source,
using **Grafana Assume Role**. `infra/envs/develop/grafana.tf` creates a read-only role for it once
`grafana_aws_account_id` and `grafana_external_id` are set. Both values are shown on the data source's Settings tab.
The role can read metrics and list log groups, but can query only the `/ecs/onboarding-*` log groups.
