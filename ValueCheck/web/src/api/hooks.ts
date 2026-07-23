/** TanStack Query hooks over the typed client. */
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  api,
  type AnalysisIn,
  type AnalysisUpdate,
  type AssumptionsIn,
  type AttributeDefinitionPatch,
  type AttributeValueIn,
  type NoteIn,
  type NoteUpdate,
  type ReferenceIn,
  type ReferenceUpdate,
} from "./client";

export function useCompany(ticker: string | null) {
  return useQuery({
    queryKey: ["company", ticker],
    queryFn: () => api.getCompany(ticker as string),
    enabled: ticker !== null,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/**
 * Runs (and re-runs) a valuation. The overrides are part of the query key, so
 * editing an assumption re-values automatically; previous data is kept while
 * the new run is in flight to avoid layout flicker.
 */
export function useValuation(ticker: string | null, overrides: AssumptionsIn) {
  return useQuery({
    queryKey: ["valuation", ticker, overrides],
    queryFn: () => api.runValuation(ticker as string, overrides),
    enabled: ticker !== null,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

// ---- notes: attach to a company, a reference, or an analysis --------------

/** The one thing a note is about — same shared tag vocabulary regardless. */
export type NoteSubject =
  | { kind: "company"; ticker: string }
  | { kind: "reference"; id: number }
  | { kind: "analysis"; id: number };

function noteSubjectKey(subject: NoteSubject): readonly unknown[] {
  return subject.kind === "company"
    ? (["notes", "company", subject.ticker] as const)
    : (["notes", subject.kind, subject.id] as const);
}

function fetchNotesFor(subject: NoteSubject) {
  switch (subject.kind) {
    case "company":
      return api.listNotes(subject.ticker);
    case "reference":
      return api.listNotesForReference(subject.id);
    case "analysis":
      return api.listNotesForAnalysis(subject.id);
  }
}

export function useNotesFor(subject: NoteSubject) {
  return useQuery({
    queryKey: noteSubjectKey(subject),
    queryFn: () => fetchNotesFor(subject),
    retry: false,
  });
}

/** Canonical tag vocabulary; feeds the client-side fuzzy suggest. */
export function useTags() {
  return useQuery({
    queryKey: ["tags"],
    queryFn: () => api.listTags(),
    staleTime: 60_000,
    retry: false,
  });
}

export function useSaveNoteFor(subject: NoteSubject) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number | null; note: NoteUpdate }) => {
      if (input.id !== null) return api.updateNote(input.id, input.note);
      const noteIn: NoteIn =
        subject.kind === "company"
          ? { ...input.note, ticker: subject.ticker }
          : subject.kind === "reference"
            ? { ...input.note, reference_id: subject.id }
            : { ...input.note, analysis_id: subject.id };
      return api.createNote(noteIn);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: noteSubjectKey(subject) });
      void queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useDeleteNoteFor(subject: NoteSubject) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteNote(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: noteSubjectKey(subject) });
      void queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

// ---- search + graph ---------------------------------------------------------

/** Runs when `query` is non-empty (the UI submits explicitly). */
export function useSearch(query: string | null) {
  return useQuery({
    queryKey: ["search", query],
    queryFn: () => api.search(query as string),
    enabled: query !== null && query.trim().length > 0,
    staleTime: 30_000,
    retry: false,
  });
}

export function useGraph(filters: { sector?: string; tickers?: string[]; collection?: string }) {
  return useQuery({
    queryKey: ["graph", filters],
    queryFn: () => api.graph(filters),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    retry: false,
  });
}

// ---- attributes (typed, namespaced company facts, with history) -------------

export function useAttributeDefinitions() {
  return useQuery({
    queryKey: ["attribute-definitions"],
    queryFn: () => api.listAttributeDefinitions(),
    staleTime: 30_000,
    retry: false,
  });
}

export function useUpdateAttributeDefinition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, patch }: { key: string; patch: AttributeDefinitionPatch }) =>
      api.updateAttributeDefinition(key, patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["attribute-definitions"] });
      void queryClient.invalidateQueries({ queryKey: ["screener-columns"] });
    },
  });
}

export function useCurrentAttributes(ticker: string | null) {
  return useQuery({
    queryKey: ["attributes", ticker],
    queryFn: () => api.currentAttributes(ticker as string),
    enabled: ticker !== null,
    retry: false,
  });
}

export function useAttributeHistory(ticker: string | null, key: string | null) {
  return useQuery({
    queryKey: ["attribute-history", ticker, key],
    queryFn: () => api.attributeHistory(ticker as string, key as string),
    enabled: ticker !== null && key !== null,
    retry: false,
  });
}

export function useSetAttribute(ticker: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (value: AttributeValueIn) => api.setAttribute(ticker, value),
    onSuccess: (_data, value) => {
      void queryClient.invalidateQueries({ queryKey: ["attributes", ticker] });
      void queryClient.invalidateQueries({ queryKey: ["attribute-history", ticker, value.key] });
      void queryClient.invalidateQueries({ queryKey: ["attribute-definitions"] });
      void queryClient.invalidateQueries({ queryKey: ["screener"] });
      void queryClient.invalidateQueries({ queryKey: ["screener-columns"] });
    },
  });
}

// ---- screener ---------------------------------------------------------------

export function useScreenerRows() {
  return useQuery({
    queryKey: ["screener"],
    queryFn: () => api.screenerRows(),
    staleTime: 15_000,
    retry: false,
  });
}

export function useScreenerColumns() {
  return useQuery({
    queryKey: ["screener-columns"],
    queryFn: () => api.screenerColumns(),
    staleTime: 15_000,
    retry: false,
  });
}

// ---- references (the knowledge library) --------------------------------------

export function useReferences() {
  return useQuery({
    queryKey: ["references"],
    queryFn: () => api.listReferences(),
    staleTime: 15_000,
    retry: false,
  });
}

export function useReference(id: number | null) {
  return useQuery({
    queryKey: ["reference", id],
    queryFn: () => api.getReference(id as number),
    enabled: id !== null,
    retry: false,
  });
}

export function useCreateReference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ref: ReferenceIn) => api.createReference(ref),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["references"] }),
  });
}

export function useUpdateReference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: ReferenceUpdate }) =>
      api.updateReference(id, patch),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ["references"] });
      void queryClient.invalidateQueries({ queryKey: ["reference", id] });
    },
  });
}

export function useDeleteReference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteReference(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["references"] }),
  });
}

export function useScanReferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.scanReferences(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["references"] }),
  });
}

// ---- analyses (the balcony) ----------------------------------------------------

export function useAnalyses() {
  return useQuery({
    queryKey: ["analyses"],
    queryFn: () => api.listAnalyses(),
    staleTime: 15_000,
    retry: false,
  });
}

export function useAnalysis(id: number | null) {
  return useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api.getAnalysis(id as number),
    enabled: id !== null,
    retry: false,
  });
}

export function useCreateAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (a: AnalysisIn) => api.createAnalysis(a),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["analyses"] }),
  });
}

export function useUpdateAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: AnalysisUpdate }) =>
      api.updateAnalysis(id, patch),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ["analyses"] });
      void queryClient.invalidateQueries({ queryKey: ["analysis", id] });
    },
  });
}

export function useDeleteAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteAnalysis(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["analyses"] }),
  });
}

function invalidateConstituents(
  queryClient: ReturnType<typeof useQueryClient>,
  analysisId: number,
) {
  void queryClient.invalidateQueries({ queryKey: ["analysis-companies", analysisId] });
  void queryClient.invalidateQueries({ queryKey: ["analysis-references", analysisId] });
  void queryClient.invalidateQueries({ queryKey: ["analysis-links", analysisId] });
  void queryClient.invalidateQueries({ queryKey: ["graph"] });
}

export function useAnalysisCompanies(id: number | null) {
  return useQuery({
    queryKey: ["analysis-companies", id],
    queryFn: () => api.analysisCompanies(id as number),
    enabled: id !== null,
    retry: false,
  });
}

export function useAddAnalysisCompany(analysisId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.addAnalysisCompany(analysisId, ticker),
    onSuccess: () => invalidateConstituents(queryClient, analysisId),
  });
}

export function useRemoveAnalysisCompany(analysisId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.removeAnalysisCompany(analysisId, ticker),
    onSuccess: () => invalidateConstituents(queryClient, analysisId),
  });
}

export function useAnalysesForCompany(ticker: string | null) {
  return useQuery({
    queryKey: ["analyses-for-company", ticker],
    queryFn: () => api.analysesForCompany(ticker as string),
    enabled: ticker !== null,
    retry: false,
  });
}

export function useAnalysisReferences(id: number | null) {
  return useQuery({
    queryKey: ["analysis-references", id],
    queryFn: () => api.analysisReferences(id as number),
    enabled: id !== null,
    retry: false,
  });
}

export function useAddAnalysisReference(analysisId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (referenceId: number) => api.addAnalysisReference(analysisId, referenceId),
    onSuccess: () => invalidateConstituents(queryClient, analysisId),
  });
}

export function useRemoveAnalysisReference(analysisId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (referenceId: number) => api.removeAnalysisReference(analysisId, referenceId),
    onSuccess: () => invalidateConstituents(queryClient, analysisId),
  });
}

export function useAnalysesForReference(referenceId: number | null) {
  return useQuery({
    queryKey: ["analyses-for-reference", referenceId],
    queryFn: () => api.analysesForReference(referenceId as number),
    enabled: referenceId !== null,
    retry: false,
  });
}

export function useAnalysisLinks(id: number | null) {
  return useQuery({
    queryKey: ["analysis-links", id],
    queryFn: () => api.analysisLinks(id as number),
    enabled: id !== null,
    retry: false,
  });
}

export function useAddAnalysisLink(analysisId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkedId: number) => api.addAnalysisLink(analysisId, linkedId),
    onSuccess: () => invalidateConstituents(queryClient, analysisId),
  });
}

export function useRemoveAnalysisLink(analysisId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkedId: number) => api.removeAnalysisLink(analysisId, linkedId),
    onSuccess: () => invalidateConstituents(queryClient, analysisId),
  });
}
