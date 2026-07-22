/** TanStack Query hooks over the typed client. */
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, type AssumptionsIn, type NoteIn, type NoteUpdate } from "./client";

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

// ---- notes + tags ---------------------------------------------------------

export function useNotes(ticker: string) {
  return useQuery({
    queryKey: ["notes", ticker],
    queryFn: () => api.listNotes(ticker),
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

export function useSaveNote(ticker: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number | null; note: NoteUpdate }) =>
      input.id === null
        ? api.createNote({ ...input.note, ticker } as NoteIn)
        : api.updateNote(input.id, input.note),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notes", ticker] });
      void queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

// ---- search + graph -------------------------------------------------------

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

export function useGraph(filters: { sector?: string; tickers?: string[] }) {
  return useQuery({
    queryKey: ["graph", filters],
    queryFn: () => api.graph(filters),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    retry: false,
  });
}

export function useDeleteNote(ticker: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteNote(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notes", ticker] });
      void queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}
