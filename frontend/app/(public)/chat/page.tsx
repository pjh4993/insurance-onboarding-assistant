import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { CustomerChat } from "@/components/customer/CustomerChat";
import { SESSION_COOKIE } from "@/lib/server/config";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { referrer: "no-referrer", robots: { index: false } };

// A session started on / (or opened from a link earlier): the same cookie-based chat as /s/{token}.
// Without the cookie there is nothing to show, so go back to the landing page to start one.
export default async function ChatPage() {
  if (!(await cookies()).get(SESSION_COOKIE)?.value) redirect("/");
  return <CustomerChat />;
}
