// Shapes of the backend's /api/operator/* responses (CONTRACTS.md §3, operator).

export type Release = {
  version?: string;
  published_by?: string;
  published_at?: string;
  via?: string;
  based_on?: string | null;
  notes?: string;
};

export type VersionItem = { version: string; release: Release; live: boolean; latest: boolean };

export type ModelInfo = { name: string; provider: string; model_id: string; args: Record<string, unknown> };

export type Summary = {
  languages: { code: string; name: string }[];
  default_language: string;
  models: ModelInfo[];
  nodes: Record<string, string>;
  copy_keys: number;
};

export type VersionDetail = {
  version: string;
  release: Release;
  live: boolean;
  files: Record<string, string>;
  /** null when this agent's code cannot load the version (written for older code); `problems` says why */
  summary: Summary | null;
  problems: string[];
};

export type ConfigStatus = {
  live: { version: string; source: string };
  version_spec: string;
  next: string | null;
  restart_needed: boolean;
  publishable: boolean;
  restartable: boolean;
  base: string;
};

export type ValidateResult = { ok: boolean; problems: string[]; summary: Summary | null; version?: string };

export type PublishResult = { version: string; release: Release };

export type Bump = "patch" | "minor";
