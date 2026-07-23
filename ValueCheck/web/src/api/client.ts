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
export type NoteLinkIn = components["schemas"]["NoteLinkIn"];
export type NoteLinkOut = components["schemas"]["NoteLinkOut"];
export type NoteIn = components["schemas"]["NoteIn"];
export type NoteUpdate = components["schemas"]["NoteUpdate"];
export type NoteOut = components["schemas"]["NoteOut"];
export type TagsOut = components["schemas"]["TagsOut"];
export type SearchResultOut = components["schemas"]["SearchResultOut"];
export type SearchHitOut = components["schemas"]["SearchHitOut"];
export type GraphOut = components["schemas"]["GraphOut"];
export type GraphNodeOut = components["schemas"]["GraphNodeOut"];
export type GraphEdgeOut = components["schemas"]["GraphEdgeOut"];

export type AttributeDefinitionOut = components["schemas"]["AttributeDefinitionOut"];
export type ValueType = AttributeDefinitionOut["value_type"];
export type AttributeDefinitionPatch = components["schemas"]["AttributeDefinitionPatch"];
export type AttributeValueIn = components["schemas"]["AttributeValueIn"];
export type AttributeValueOut = components["schemas"]["AttributeValueOut"];
export type AttributeHistoryOut = components["schemas"]["AttributeHistoryOut"];

export type ScreenerOut = components["schemas"]["ScreenerOut"];
export type ScreenerRowOut = components["schemas"]["ScreenerRowOut"];
export type ScreenerColumnsOut = components["schemas"]["ScreenerColumnsOut"];
export type ScreenerValuationOut = components["schemas"]["ScreenerValuationOut"];

export type ReferenceIn = components["schemas"]["ReferenceIn"];
export type ReferenceOut = components["schemas"]["ReferenceOut"];
export type ReferenceUpdate = components["schemas"]["ReferenceUpdate"];
export type ReferenceScanOut = components["schemas"]["ReferenceScanOut"];

export type AnalysisIn = components["schemas"]["AnalysisIn"];
export type AnalysisOut = components["schemas"]["AnalysisOut"];
export type AnalysisUpdate = components["schemas"]["AnalysisUpdate"];
export type AnalysisCompaniesOut = components["schemas"]["AnalysisCompaniesOut"];
export type AnalysisReferencesOut = components["schemas"]["AnalysisReferencesOut"];
export type AnalysisLinksOut = components["schemas"]["AnalysisLinksOut"];

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

  // -- notes (attach to a company, a reference, or an analysis) -------------
  listNotes: (ticker: string) =>
    request<NoteOut[]>(`/companies/${encodeURIComponent(ticker)}/notes`),

  listNotesForReference: (referenceId: number) =>
    request<NoteOut[]>(`/references/${referenceId}/notes`),

  listNotesForAnalysis: (analysisId: number) =>
    request<NoteOut[]>(`/analyses/${analysisId}/notes`),

  createNote: (note: NoteIn) =>
    request<NoteOut>("/notes", { method: "POST", body: JSON.stringify(note) }),

  updateNote: (id: number, note: NoteUpdate) =>
    request<NoteOut>(`/notes/${id}`, { method: "PUT", body: JSON.stringify(note) }),

  deleteNote: (id: number) => request<void>(`/notes/${id}`, { method: "DELETE" }),

  listTags: () => request<TagsOut>("/tags"),

  search: (q: string) => request<SearchResultOut>(`/search?q=${encodeURIComponent(q)}`),

  graph: (filters: { sector?: string; tickers?: string[]; collection?: string } = {}) => {
    const params = new URLSearchParams();
    if (filters.sector) params.set("sector", filters.sector);
    if (filters.collection) params.set("collection", filters.collection);
    for (const t of filters.tickers ?? []) params.append("tickers", t);
    const qs = params.toString();
    return request<GraphOut>(`/graph${qs ? `?${qs}` : ""}`);
  },

  // -- attributes (typed, namespaced company facts, with history) -----------
  listAttributeDefinitions: () =>
    request<AttributeDefinitionOut[]>("/attributes/definitions"),

  updateAttributeDefinition: (key: string, patch: AttributeDefinitionPatch) =>
    request<AttributeDefinitionOut>(`/attributes/definitions/${encodeURIComponent(key)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  setAttribute: (ticker: string, value: AttributeValueIn) =>
    request<AttributeValueOut>(`/companies/${encodeURIComponent(ticker)}/attributes`, {
      method: "POST",
      body: JSON.stringify(value),
    }),

  currentAttributes: (ticker: string) =>
    request<Record<string, AttributeValueOut>>(
      `/companies/${encodeURIComponent(ticker)}/attributes`,
    ),

  attributeHistory: (ticker: string, key: string) =>
    request<AttributeHistoryOut>(
      `/companies/${encodeURIComponent(ticker)}/attributes/${encodeURIComponent(key)}/history`,
    ),

  // -- screener ---------------------------------------------------------------
  screenerRows: () => request<ScreenerOut>("/screener/rows"),

  screenerColumns: () => request<ScreenerColumnsOut>("/screener/columns"),

  // -- references (the knowledge library) ------------------------------------
  listReferences: () => request<ReferenceOut[]>("/references"),

  getReference: (id: number) => request<ReferenceOut>(`/references/${id}`),

  createReference: (ref: ReferenceIn) =>
    request<ReferenceOut>("/references", { method: "POST", body: JSON.stringify(ref) }),

  updateReference: (id: number, patch: ReferenceUpdate) =>
    request<ReferenceOut>(`/references/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  deleteReference: (id: number) => request<void>(`/references/${id}`, { method: "DELETE" }),

  scanReferences: () =>
    request<ReferenceScanOut>("/references/scan", { method: "POST", body: "{}" }),

  /** Not fetched as JSON — use directly as a link/iframe target. */
  referenceFileUrl: (id: number) => `${BASE}/references/${id}/file`,

  // -- analyses (the balcony) -------------------------------------------------
  listAnalyses: () => request<AnalysisOut[]>("/analyses"),

  getAnalysis: (id: number) => request<AnalysisOut>(`/analyses/${id}`),

  createAnalysis: (a: AnalysisIn) =>
    request<AnalysisOut>("/analyses", { method: "POST", body: JSON.stringify(a) }),

  updateAnalysis: (id: number, patch: AnalysisUpdate) =>
    request<AnalysisOut>(`/analyses/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  deleteAnalysis: (id: number) => request<void>(`/analyses/${id}`, { method: "DELETE" }),

  analysisCompanies: (id: number) =>
    request<AnalysisCompaniesOut>(`/analyses/${id}/companies`),

  addAnalysisCompany: (id: number, ticker: string) =>
    request<void>(`/analyses/${id}/companies`, {
      method: "POST",
      body: JSON.stringify({ ticker }),
    }),

  removeAnalysisCompany: (id: number, ticker: string) =>
    request<void>(`/analyses/${id}/companies/${encodeURIComponent(ticker)}`, {
      method: "DELETE",
    }),

  analysesForCompany: (ticker: string) =>
    request<AnalysisOut[]>(`/analyses/for-company/${encodeURIComponent(ticker)}`),

  analysisReferences: (id: number) =>
    request<AnalysisReferencesOut>(`/analyses/${id}/references`),

  addAnalysisReference: (id: number, referenceId: number) =>
    request<void>(`/analyses/${id}/references`, {
      method: "POST",
      body: JSON.stringify({ reference_id: referenceId }),
    }),

  removeAnalysisReference: (id: number, referenceId: number) =>
    request<void>(`/analyses/${id}/references/${referenceId}`, { method: "DELETE" }),

  analysesForReference: (referenceId: number) =>
    request<AnalysisOut[]>(`/analyses/for-reference/${referenceId}`),

  analysisLinks: (id: number) => request<AnalysisLinksOut>(`/analyses/${id}/links`),

  addAnalysisLink: (id: number, linkedAnalysisId: number) =>
    request<void>(`/analyses/${id}/links`, {
      method: "POST",
      body: JSON.stringify({ linked_analysis_id: linkedAnalysisId }),
    }),

  removeAnalysisLink: (id: number, linkedAnalysisId: number) =>
    request<void>(`/analyses/${id}/links/${linkedAnalysisId}`, { method: "DELETE" }),
};
