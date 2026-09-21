// The seed customers the mock recognises by name (contracts/seed-customers.json, docs/guides/demo.md).
import data from "../../contracts/seed-customers.json" with { type: "json" };

export type Market = "KR" | "US";
export type SeedKey = "A" | "B" | "C" | "D";
export type Seed = {
  key: SeedKey;
  market: Market;
  full_name: string;
  email: string;
  phone: string;
  id_document_type: string;
  id_document_number: string;
  needs_text: string;
};

const SEEDS = Object.fromEntries((data.customers as Seed[]).map((c) => [c.key, c])) as Record<SeedKey, Seed>;

export const seed = (key: SeedKey): Seed => SEEDS[key];

/** Any OTP works for B; the mock fails every code for C and D. */
export const OTP = "000000";
