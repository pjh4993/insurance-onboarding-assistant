import { CustomerChat } from "@/components/customer/CustomerChat";

// The token in the URL is moved into an httpOnly cookie by proxy.ts before this renders;
// the page itself never reads it, so client code never holds the session secret.
export const dynamic = "force-dynamic";

export default function CustomerSessionPage() {
  return <CustomerChat />;
}
