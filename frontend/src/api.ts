// Thin API client. In dev, Vite proxies /api -> :8080; in prod the SPA is served
// by the same FastAPI container, so relative URLs work everywhere.

export type DecisionCode =
  | "PREF" | "STD" | "R25" | "R50" | "R100" | "RATED"
  | "FE" | "EXCL" | "POST" | "DECL" | "REFER";

export interface UploadRow {
  row: number;
  ok: boolean;
  id?: string;
  decision?: Decision;
  error?: string;
}
export interface UploadResult {
  total: number;
  succeeded: number;
  failed: number;
  results: UploadRow[];
}

export interface Finding {
  factor: string;
  assessment: string;
  decision_code: DecisionCode;
  rating_pct: number;
  flat_extra_per_mille: number;
  exclusion: string | null;
  article: string;
  source: string;
  requires_referral: boolean;
  referral_reason: string | null;
}

export interface Decision {
  applicant: string;
  product: string;
  sum_assured: number;
  overall_decision: DecisionCode;
  total_rating_pct: number;
  flat_extra_per_mille: number;
  exclusions: string[];
  requires_referral: boolean;
  referral_reasons: string[];
  evidence_required: string[];
  findings: Finding[];
  explanation: string;
  llm_used: boolean;
}

export interface CaseSummary {
  id: string;
  created_at: string;
  applicant: string;
  applicant_type: string;
  product: string;
  sum_assured: number;
  decision: DecisionCode;
  rating_pct: number;
  requires_referral: number;
  llm_used: number;
}

export interface Stats {
  total_cases: number;
  by_decision: Record<string, number>;
  avg_rating_pct: number;
  total_sum_assured: number;
  referrals: number;
  acceptance_rate: number;
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export const api = {
  login: (username: string, password: string) =>
    fetch("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password }),
    }).then((r) => j<{ ok: boolean; user: string; token: string }>(r)),
  health: () => fetch("/api/health").then((r) => j<any>(r)),
  stats: () => fetch("/api/stats").then((r) => j<Stats>(r)),
  cases: () => fetch("/api/cases").then((r) => j<CaseSummary[]>(r)),
  case: (id: string) => fetch(`/api/cases/${id}`).then((r) => j<any>(r)),
  underwrite: (body: unknown) =>
    fetch("/api/underwrite", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => j<{ id: string; created_at: string; decision: Decision }>(r)),
  uploadExcel: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/upload", { method: "POST", body: fd }).then((r) => j<UploadResult>(r));
  },
};
