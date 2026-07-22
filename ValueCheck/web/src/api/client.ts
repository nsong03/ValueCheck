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
export type NoteIn = components["schemas"]["NoteIn"];
export type NoteUpdate = components["schemas"]["NoteUpdate"];
export type NoteOut = components["schemas"]["NoteOut"];
export type TagsOut = components["schemas"]["TagsOut"];

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
  if (resp.status === 204) return undefined as T; // no content (delete)
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

  listNotes: (ticker: string) =>
    request<NoteOut[]>(`/companies/${encodeURIComponent(ticker)}/notes`),

  createNote: (note: NoteIn) =>
    request<NoteOut>("/notes", { method: "POST", body: JSON.stringify(note) }),

  updateNote: (id: number, note: NoteUpdate) =>
    request<NoteOut>(`/notes/${id}`, { method: "PUT", body: JSON.stringify(note) }),

  deleteNote: (id: number) => request<void>(`/notes/${id}`, { method: "DELETE" }),

  listTags: () => request<TagsOut>("/tags"),
};
