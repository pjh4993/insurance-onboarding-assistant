import { resolveOperator } from "@/lib/server/operatorAuth";

export const dynamic = "force-dynamic";

// Frontend-only: who the signed-in operator is.
export async function GET(req: Request) {
  const operator = await resolveOperator(req.headers);
  if (!operator) return Response.json({ error: "Operator sign-in required" }, { status: 401 });
  return Response.json({ operator_id: operator.id });
}
