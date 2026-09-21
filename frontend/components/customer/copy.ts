import type { Market } from "@/lib/types";

export type ProductIcon = "phone" | "laptop" | "appliance" | "plane";
export type ProductKey = "travel" | "phone" | "laptop" | "appliance";

export type LandingProduct = { key: ProductKey; icon: ProductIcon; badge?: "BEST" | "NEW" };

// One card per product in backend/app/domain/catalog_seed.py for the market. Name, blurb and the
// first-answer pre-fill ("ask") are in messages under products.<market>.<key>, in both languages.
const PRODUCTS: Record<Market, LandingProduct[]> = {
  KR: [
    { key: "travel", icon: "plane", badge: "BEST" },
    { key: "phone", icon: "phone", badge: "NEW" },
    { key: "laptop", icon: "laptop" },
    { key: "appliance", icon: "appliance" },
  ],
  US: [
    { key: "travel", icon: "plane", badge: "BEST" },
    { key: "phone", icon: "phone", badge: "NEW" },
    { key: "laptop", icon: "laptop" },
    { key: "appliance", icon: "appliance" },
  ],
};

export const landingProducts = (market: Market): LandingProduct[] => PRODUCTS[market];
