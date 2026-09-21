// Shared types copied from CONTRACTS.md §3 (backend HTTP API). Keep in sync with the contract.

export type Market = "KR" | "US";

/** The session's language: the customer UI, fixed copy and LLM replies. */
export type Locale = "ko" | "en";

export type Stage =
  | "IDENTITY"
  | "PROFILING"
  | "RECOMMENDATION"
  | "APPLICATION"
  | "SUBMITTED"
  | "HANDOFF"
  | "DECLINED"
  | "WITHDRAWN";

export type WaitingFor =
  | "IDENTITY_INFO"
  | "OTP_CODE"
  | "NEEDS"
  | "DECISION"
  | "PARTIES"
  | "ANSWERS"
  | "CONFIRM"
  | "AGENT"
  | null;

export type SessionStatus = "ACTIVE" | "SUBMITTED" | "DECLINED" | "WITHDRAWN" | "HANDOFF" | "EXPIRED";

export type SessionSummary = {
  session_id: string;
  display_name: string; // "Unverified #1a2b" until identity is verified
  market: Market;
  /** Missing from backends older than the locale change; use i18n/locales sessionLocale(). */
  locale?: Locale;
  status: SessionStatus;
  stage: Stage;
  waiting_for: WaitingFor;
  mode: "AUTO" | "ASSIST";
  assigned_agent_id: string | null;
  last_activity_at: string;
};

export type Message = {
  id: string;
  role: "customer" | "assistant" | "agent" | "system";
  text: string;
  created_at: string;
};

export type BillingPeriod = "MONTHLY" | "ONE_TIME" | "PER_TRIP";

export type Quote = {
  quote_id: string;
  premium_minor: number;
  currency: string;
  billing_period: BillingPeriod;
  term_start_date: string;
  term_end_date: string;
  valid_until: string;
};

export type RecommendationCard = {
  recommendation_id: string;
  product_code: string;
  marketing_name: string;
  product_type: string;
  rank: number;
  eligibility_result: "ELIGIBLE" | "INELIGIBLE";
  failed_reasons: string[];
  rationale: string | null;
  status: "PROPOSED" | "ACCEPTED" | "DECLINED" | "EXPIRED";
  quote: Quote | null;
};

export type Prompt = {
  waiting_for: WaitingFor;
  message: string;
  options?: RecommendationCard[];
  summary?: string;
};

export type SessionView = { session: SessionSummary; messages: Message[]; prompt: Prompt | null };

export type Application = {
  application_id: string;
  status: string;
  answers: Record<string, unknown>;
  missing_fields: string[];
  summary: string | null;
  submission_ref: string | null;
};

export type SessionDetail = SessionView & {
  current_node: string | null;
  entities: {
    party: Record<string, unknown> | null; // PII masked: id_document_number never returned
    needs_assessment: Record<string, unknown> | null;
    insurable_objects: Record<string, unknown>[];
    recommendations: RecommendationCard[];
    application: Application | null;
    application_parties: { role: string; full_name: string }[];
  };
};

export type InputType = Exclude<WaitingFor, null>;

/** `data` shape per `type` (CONTRACTS.md §3, "InputBody.data by type"). */
export type InputDataMap = {
  IDENTITY_INFO: {
    full_name: string;
    email: string;
    phone: string;
    id_document_type: string;
    id_document_number: string;
    third_party_consent: boolean;
  };
  OTP_CODE: { code: string };
  NEEDS: { text: string };
  DECISION: { decision: "ACCEPT" | "DECLINE" | "CHANGE"; recommendation_id?: string; text?: string };
  PARTIES: { text: string };
  ANSWERS: { text: string };
  CONFIRM: { confirmed: boolean; text?: string };
  AGENT: { resolution: "VERIFIED" | "CONTINUE" | "END"; note?: string };
};

export type InputBody = { [K in InputType]: { type: K; data: InputDataMap[K] } }[InputType];

export type CreateSessionResponse = { session_id: string; token: string; customer_path: string };

// ---- SSE events (CONTRACTS.md §3, "SSE")
export type SessionUpdatedEvent = { session: SessionSummary };
export type MessageAppendedEvent = { session_id: string; message: Message };
export type PromptUpdatedEvent = { session_id: string; prompt: Prompt | null };
export type EntityUpdatedEvent = { session_id: string; entity_type: string; entity_id: string };

export type StreamEventMap = {
  "session.updated": SessionUpdatedEvent;
  "message.appended": MessageAppendedEvent;
  "prompt.updated": PromptUpdatedEvent;
  "entity.updated": EntityUpdatedEvent;
};
