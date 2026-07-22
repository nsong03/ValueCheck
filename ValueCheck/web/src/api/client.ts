/**
 * Typed API client. Every request/response type comes from the GENERATED
 * OpenAPI schema (src/api/generated/schema.d.ts) — no hand-written API shapes.
 * Regenerate with `npm run generate:api` after backend contract changes.
 */
import type { components } from "./generated/schema";

export type CompanyDetail = components["schemas"]["CompanyDetail"];
export type CompanyListOut = components["schemas"]["CompanyListOut"];
export type HistoricalsRow = components["schemas"]["HistoricalsRow"];
export type AssumptionsIn = components["schemas"]["AssumptionsIn"];
export type AssumptionsOut = components["schemas"]["AssumptionsOut"];
export type ProjectionRow = components["schemas"]["ProjectionRow"];
export type SensitivityOut = components["schemas"]["SensitivityOut"];
export type SourceLinkOut = components["schemas"]["SourceLinkOut"];
export type ValuationResponse = components["schemas"]["ValuationResponse"];
export type ValuationRecordSummary = components["schemas"]["ValuationRecordSummary"];

const BASE: string = import.meta.env.VITE_API_BASE ?? "/api";

/** Backend error envelope: {"error": {code, message, details?}}. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let code = "internal_error";
    let message = `${resp.status} ${resp.statusText}`;
    try {
      const body = (await resp.json()) as { error?: { code?: string; message?: string } };
      if (body.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // non-JSON error body: keep the HTTP status text
    }
    throw new ApiError(code, message, resp.status);
  }
  return (await resp.json()) as T;
}

export const api = {
  listCompanies: () => request<CompanyListOut>("/companies"),

  getCompany: (ticker: string, refresh = false) =>
    request<CompanyDetail>(
      `/companies/${encodeURIComponent(ticker)}${refresh ? "?refresh=true" : ""}`,
    ),

  runValuation: (ticker: string, overrides: AssumptionsIn, refresh = false) =>
    request<ValuationResponse>(
      `/companies/${encodeURIComponent(ticker)}/valuation${refresh ? "?refresh=true" : ""}`,
      { method: "POST", body: JSON.stringify(overrides) },
    ),

  valuationHistory: (ticker: string) =>
    request<ValuationRecordSummary[]>(`/companies/${encodeURIComponent(ticker)}/valuations`),
};
