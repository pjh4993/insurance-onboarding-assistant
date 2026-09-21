import { forwardCustomer } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export function GET(req: Request) {
  return forwardCustomer(req, "/api/customer/session");
}
