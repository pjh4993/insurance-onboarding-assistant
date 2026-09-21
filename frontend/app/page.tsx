import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function Home() {
  const t = await getTranslations();
  return (
    <main className="home">
      <div className="notice">
        <h1>{t("common.appName")}</h1>
        <p>{t.rich("home.body", { code: (chunks) => <code>{chunks}</code> })}</p>
        <Link className="btn btn--primary" href="/agent">
          {t("home.openConsole")}
        </Link>
      </div>
    </main>
  );
}
