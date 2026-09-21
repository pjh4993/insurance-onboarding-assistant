import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import type { Locale } from "./locales";

// Both bundles are small, so the customer app ships both and switches without a reload.
export const MESSAGES = { en, ko } satisfies Record<Locale, typeof en>;
