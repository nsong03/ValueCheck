/** TanStack Query hooks over the typed client. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type AssumptionsIn } from "./client";

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
