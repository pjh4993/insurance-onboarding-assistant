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
  otp: { valid_code: string | null } | null; // null: the partner match verifies, no OTP is asked
};

const SEEDS = Object.fromEntries((data.customers as Seed[]).map((c) => [c.key, c])) as Record<SeedKey, Seed>;

export const seed = (key: SeedKey): Seed => SEEDS[key];

/** The identity mock accepts every OTP code but one, so a seed whose OTP should fail (C, D) types that one. */
export const OTP = "123456";
export const REJECTED_OTP = "000000";
export const otpFor = (s: Seed): string => (s.otp?.valid_code ? OTP : REJECTED_OTP);
