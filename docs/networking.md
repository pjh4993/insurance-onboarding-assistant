# Networking design

Network topology, how traffic flows between the browser and each service, the security boundaries, and
authentication.

## 1. Topology

One VPC in ap-northeast-2, two availability zones (2a and 2c), three subnet tiers per zone.

```mermaid
flowchart TB
    igw["Internet gateway"]
    subgraph vpc["VPC 10.0.0.0/16"]
        subgraph pub["Public tier"]
            pa["10.0.0.0/24 (2a)<br/>ALB, NAT"]
            pc["10.0.1.0/24 (2c)<br/>ALB, NAT (prod)"]
        end
        subgraph app["Private app tier"]
            aa["10.0.10.0/24 (2a)<br/>ECS tasks, interface endpoints"]
            ac["10.0.11.0/24 (2c)<br/>ECS tasks, interface endpoints (prod)"]
        end
        subgraph data["Private data tier"]
            da["10.0.20.0/24 (2a)<br/>RDS"]
            dc["10.0.21.0/24 (2c)<br/>RDS standby (prod)"]
        end
    end
    igw <--> pub
    app -- "outbound via NAT" --> pub
    app --> data
```

| Tier | CIDR (2a, 2c) | Contains | Internet |
|---|---|---|---|
| Public | `10.0.0.0/24`, `10.0.1.0/24` | ALB, NAT gateway | In and out |
| Private app | `10.0.10.0/24`, `10.0.11.0/24` | ECS tasks: frontend, backend, mock | Outbound only, through NAT |
| Private data | `10.0.20.0/24`, `10.0.21.0/24` | RDS subnet group | None |

### VPC endpoints

AWS services are reached through VPC endpoints, not through NAT.

| Endpoint | Type | Used by |
|---|---|---|
| `s3` | Gateway (free) | ECR image layers |
| `bedrock-runtime` | Interface | Backend LLM calls |
| `secretsmanager` | Interface | Frontend and backend secrets |
| `ecr.api`, `ecr.dkr` | Interface | Image pulls |
| `logs` | Interface | CloudWatch Logs |

A Bedrock request carries customer conversation, so it never goes over the internet.

**Develop puts interface endpoints in one AZ only (2a).** Interface endpoints are billed per hour per AZ and
are the biggest item in the develop bill. Develop tasks in 2c cross to the 2a endpoints. Prod places them in both
AZs.

### NAT

NAT is only for calls to the public internet: the frontend fetching ALB signing keys and Cognito keys, and, in
prod, the real partner, identity and contract admin systems once they exist. Develop has one NAT gateway; prod
has one per AZ.

## 2. Traffic flows

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as ALB
    participant F as Frontend (Next.js)
    participant K as Backend (FastAPI)
    participant M as Mock (develop)
    participant D as RDS
    participant R as Bedrock (VPC endpoint)
    B->>A: HTTPS 443
    A->>F: HTTP 3000
    F->>K: HTTP 8000 via Service Connect (http://backend:8000)
    K->>D: PostgreSQL 5432, TLS
    K->>M: HTTP 8080 via Service Connect (http://mock:8080)
    K->>R: HTTPS 443
    K-->>F: SSE stream
    F-->>B: SSE stream (passed through)
```

| Segment | Protocol | Port |
|---|---|---|
| Browser → ALB | HTTPS. HTTP redirects to HTTPS | 443 |
| ALB → Frontend | HTTP, target group | 3000 |
| Frontend → Backend | HTTP over ECS Service Connect, `http://backend:8000` | 8000 |
| Backend → Mock (develop) | HTTP over ECS Service Connect, `http://mock:8080` | 8080 |
| Backend → RDS | PostgreSQL, TLS required | 5432 |
| Backend → Bedrock, Secrets Manager | Interface endpoints | 443 |

### Frontend-to-backend: the frontend relays

The browser can only reach the ALB and the frontend. It never calls the backend. The frontend's route handlers
under `/api/*` forward each request to `BACKEND_URL`:

- The backend is never exposed to the internet and accepts traffic only from the frontend's security group.
- Login is checked in one place, the frontend, which forwards the caller's identity to the backend
  (`X-Agent-Id` for agents, `X-Session-Token` for customers).
- Chat updates are **server-sent events**. The backend streams them; the frontend passes the stream through
  unchanged. The ALB idle timeout is raised from 60 s to **300 s**, and the backend sends a `: ping` comment every
  15 s so idle streams stay open.

Locally the same relay runs in Docker Compose: `frontend` calls `http://backend:8000` on the Compose network.

### Service-to-service: ECS Service Connect

Each ECS service registers a short name in a Service Connect namespace (`backend`, `mock`). Callers use
`http://backend:8000` and `http://mock:8080`, which are the same names as in Docker Compose, so configuration
does not change between local and AWS. Traffic inside the VPC is plain HTTP; see
[tradeoffs.md](tradeoffs.md).

## 3. Security groups

Each group admits traffic only from the group in front of it.

| Security group | Inbound | Attached to |
|---|---|---|
| `sg-alb` | 443 from `0.0.0.0/0` | ALB |
| `sg-frontend` | 3000 from `sg-alb` | Frontend tasks |
| `sg-backend` | 8000 from `sg-frontend` | Backend tasks |
| `sg-mock` | 8080 from `sg-backend` | Mock tasks (develop) |
| `sg-rds` | 5432 from `sg-backend` | RDS |
| `sg-endpoints` | 443 from `sg-frontend`, `sg-backend`, `sg-mock` | Interface endpoints |

Only the backend reaches the database. The frontend does not know about the database, the mock or Bedrock.

## 4. Security boundaries

```mermaid
flowchart LR
    subgraph internet["Internet"]
        b(["Browser"])
    end
    subgraph edgez["Edge boundary"]
        alb["ALB + Cognito (agents)"]
    end
    subgraph appz["App boundary (private subnets)"]
        fe["Frontend<br/>checks login"]
        be["Backend<br/>only reachable from frontend"]
    end
    subgraph dataz["Data boundary (no internet)"]
        rds[("RDS<br/>only reachable from backend")]
    end
    b --> alb --> fe --> be --> rds
```

| Boundary | What protects it |
|---|---|
| Internet → edge | Only the ALB is public. HTTPS only. `/agent/*` requires a Cognito login at the ALB |
| Edge → app | Tasks are in private subnets with no public IPs. The frontend only accepts traffic from the ALB |
| Frontend → backend | Backend only accepts traffic from the frontend's security group. The frontend validates the agent's signed header or the customer's session cookie before relaying |
| App → data | RDS is in subnets with no route to the internet and only accepts the backend. TLS required. KMS encryption at rest |
| Checkpoint contents | Compressed and AES-encrypted by the backend. Only the backend role can read the key |
| App → AWS APIs | VPC endpoints; each task role allows only what that service needs |

## 5. Authentication

### Agents: Cognito through the ALB

1. The ALB listener rule for `/agent/*` has a Cognito `authenticate` action.
2. After login, the ALB adds a signed user-claims header (`x-amzn-oidc-data`) to each request it forwards.
3. The frontend verifies the signature (with the ALB public key, fetched through NAT) and relays to the backend
   with `X-Agent-Id: <agent id>`. The backend treats the caller as `actor = AGENT`.

Cognito and ALB HTTPS need a domain and certificate, which do not exist yet. Until then the frontend runs with
`AGENT_DEV_AUTH=true` and sends `X-Agent-Id: agent-demo`. The Terraform for the certificate and Cognito rule is
switched on by a domain variable. See [future-improvements.md](future-improvements.md).

### Customers: session links

Customers have no account.

1. An agent clicks "New session" in the console (`POST /api/sessions {market}`). The backend creates the session
   and a random token and returns `customer_path: /s/{token}`.
2. The backend stores only the token's HMAC (`SESSION_HMAC_KEY`), never the token itself.
3. The customer opens `/s/{token}`. The frontend checks the token once and replaces it with an httpOnly cookie,
   then sends it to the backend as `X-Session-Token`.
4. One token reaches exactly one thread. Who the customer actually is gets decided by the graph's identity stage,
   not by the link.
