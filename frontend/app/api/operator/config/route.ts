import { forwardOperator } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export function GET(req: Request) {
  return forwardOperator(req, "/api/operator/config");
}
