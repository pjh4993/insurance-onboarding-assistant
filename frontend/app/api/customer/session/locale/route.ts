import { forwardCustomer } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export function PUT(req: Request) {
  return forwardCustomer(req, "/api/customer/session/locale");
}
