"""US-GAAP concept fallback tables (from the validated seed core, seed/data.py).

XBRL concept names vary by filer, so each line item lists common tags, best
first; the adapter takes the first that resolves. This is the core of the
normalization work that makes companies comparable.
"""

from __future__ import annotations

CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "ebit": ["OperatingIncomeLoss"],
    "da": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        # live finding (Phase 2 smoke): MSFT tags D&A as ...AndOther
        "DepreciationAmortizationAndOther",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "pretax": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "tax": ["IncomeTaxExpenseBenefit"],
}
