import type { Market } from "@/lib/types";

export type ProductIcon = "phone" | "laptop" | "appliance" | "plane";

export type LandingProduct = {
  icon: ProductIcon;
  name: string;
  blurb: string;
  badge?: string;
  /** Pre-fills the customer's first profiling answer when they pick this card. */
  ask: string;
};

// Product names and blurbs follow backend/app/domain/catalog_seed.py for each market.
const PRODUCTS: Record<Market, LandingProduct[]> = {
  KR: [
    {
      icon: "plane",
      name: "해외여행 보험",
      blurb: "해외 의료비부터 휴대품, 항공기 지연까지",
      badge: "BEST",
      ask: "해외여행 보험이 궁금해요.",
    },
    {
      icon: "phone",
      name: "폰교체 패스",
      blurb: "새 폰 샀다면? 파손·고장 나도 교체까지",
      badge: "NEW",
      ask: "새로 산 휴대폰을 보장받고 싶어요.",
    },
    {
      icon: "laptop",
      name: "노트북·태블릿 파손 보장",
      blurb: "떨어뜨려도 수리비 걱정 없이",
      ask: "노트북이나 태블릿 파손 보장이 궁금해요.",
    },
    {
      icon: "appliance",
      name: "가전 연장 보증",
      blurb: "제조사 보증이 끝난 뒤의 고장까지",
      ask: "가전제품 연장 보증이 궁금해요.",
    },
  ],
  US: [
    {
      icon: "plane",
      name: "Single Trip Protection",
      blurb: "Cancellation, medical and baggage, one trip at a time",
      badge: "BEST",
      ask: "I'd like cover for an upcoming trip.",
    },
    {
      icon: "phone",
      name: "Mobile Handset Protection",
      blurb: "Just got a new phone? Repair or replace it",
      badge: "NEW",
      ask: "I want to protect my new phone.",
    },
    {
      icon: "laptop",
      name: "2-Year Laptop Protection",
      blurb: "Drops, spills and cracked screens",
      ask: "I'm looking for laptop protection.",
    },
    {
      icon: "appliance",
      name: "3-Year TV Protection",
      blurb: "Failures and wear after the maker's warranty",
      ask: "I'd like an extended warranty for my TV.",
    },
  ],
};

const COPY = {
  KR: {
    lang: "ko",
    eyebrow: "AI 보험 가입 상담",
    headline: ["보험도", "대화로 쉽게"],
    lede: "궁금한 걸 말씀해 주시면, 확인부터 추천과 가입까지 한 대화로 도와드려요.",
    placeholder: "무엇을 보장받고 싶으세요? 예) 다음 달 일본 여행",
    start: "시작하기",
    startPlain: "상품을 정하지 않고 시작하기",
    go: "상담 시작",
    stepsTitle: "이렇게 진행돼요",
    steps: [
      { title: "본인 확인", body: "이름과 연락처, 신분증으로 확인해요" },
      { title: "맞춤 질문", body: "필요한 것만 몇 가지 여쭤봐요" },
      { title: "상품 추천", body: "가입할 수 있는 상품과 보험료를 비교해요" },
      { title: "가입 신청", body: "내용을 확인하고 바로 신청해요" },
    ],
    duration: "보통 5분 안에 끝나요",
    privacy: "입력하신 정보는 가입 상담에만 쓰이고, 상담원이 필요하면 언제든 이어받아요.",
    sub: (market: Market) => `보험 가입 상담 · ${market === "KR" ? "한국" : "미국"}`,
    reconnecting: "다시 연결 중…",
    errorTitle: "문제가 생겼어요",
    expired: "링크가 만료되었거나 올바르지 않아요. 상담원에게 새 링크를 요청해 주세요.",
    loadFailed: "상담을 불러오지 못했어요. 페이지를 새로고침해 주세요.",
  },
  US: {
    lang: "en",
    eyebrow: "AI insurance onboarding",
    headline: ["Insurance,", "just a conversation"],
    lede: "Tell us what you want to protect. We'll verify you, recommend cover and apply, all in one chat.",
    placeholder: "What would you like to protect? e.g. a trip to Tokyo next month",
    start: "Start",
    startPlain: "Start without picking a product",
    go: "Get started",
    stepsTitle: "How it works",
    steps: [
      { title: "Verify", body: "Your name, contact details and an ID" },
      { title: "A few questions", body: "Only what we need to know" },
      { title: "Recommendation", body: "Compare the cover you qualify for" },
      { title: "Apply", body: "Review the details and submit" },
    ],
    duration: "Usually takes under 5 minutes",
    privacy: "What you share is used only for this application, and a human agent can step in at any time.",
    sub: (market: Market) => `Insurance onboarding · ${market}`,
    reconnecting: "Reconnecting…",
    errorTitle: "Something went wrong",
    expired: "This link has expired or is not valid. Please ask for a new link.",
    loadFailed: "We could not load your session. Please refresh the page.",
  },
} satisfies Record<Market, unknown>;

export type CustomerCopy = (typeof COPY)[Market];

export const customerCopy = (market: Market): CustomerCopy => COPY[market];
export const landingProducts = (market: Market): LandingProduct[] => PRODUCTS[market];
