import Link from "next/link";

export default function Home() {
  return (
    <main className="home">
      <div className="notice">
        <h1>Cover Assistant</h1>
        <p>
          Customers open a session link (<code>/s/…</code>). Agents work in the console.
        </p>
        <Link className="btn btn--primary" href="/agent">
          Open the agent console
        </Link>
      </div>
    </main>
  );
}
