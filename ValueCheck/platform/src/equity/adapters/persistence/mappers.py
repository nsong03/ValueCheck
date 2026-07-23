"""Row <-> domain mappers for the SQLite adapter.

Pure translation only — no SQL, no connections. Serialization choices:
- history series -> (fiscal_year, metric, value) rows, NaNs skipped;
- assumptions/projection/warnings -> JSON text (JSON round-trips Python floats
  exactly, so stored valuations reproduce bit-identical numbers);
- timestamps -> ISO 8601 UTC strings.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from typing import Any

import pandas as pd

from equity.domain.analysis import Analysis
from equity.domain.assumptions import Assumptions
from equity.domain.attributes import AttributeDefinition, AttributeValue
from equity.domain.models import CompanyFinancials, SourceLink
from equity.domain.references import Reference
from equity.domain.research import Note, NoteLink
from equity.domain.valuation import DCFResult, ValuationRecord

# metric column value <-> CompanyFinancials series attribute (same names)
SERIES_METRICS = ("revenue", "ebit", "da", "capex", "nwc", "tax_rate")


# --------------------------------------------------------------------------- #
# companies + facts + sources
# --------------------------------------------------------------------------- #
def company_row(fin: CompanyFinancials, fetched_at: datetime) -> dict[str, Any]:
    return {
        "ticker": fin.ticker,
        "name": fin.name,
        "sector": fin.sector,
        "industry": fin.industry,
        "sic": fin.sic,
        "total_debt": fin.total_debt,
        "cash": fin.cash,
        "shares_out": fin.shares_out,
        "price": fin.price,
        "beta": fin.beta,
        "fetched_at": fetched_at.isoformat(),
    }


def fact_rows(fin: CompanyFinancials) -> list[tuple[str, int, str, float]]:
    rows: list[tuple[str, int, str, float]] = []
    for metric in SERIES_METRICS:
        series: pd.Series[float] = getattr(fin, metric)
        for year, value in series.items():
            if value == value:  # skip NaN — absent is absent
                rows.append((fin.ticker, int(str(year)), metric, float(value)))
    return rows


def source_rows(fin: CompanyFinancials) -> list[tuple[str, int, str, str, str]]:
    return [(fin.ticker, pos, s.label, s.url, s.accession) for pos, s in enumerate(fin.sources)]


def build_company(
    row: sqlite3.Row,
    facts: list[sqlite3.Row],
    sources: list[sqlite3.Row],
) -> CompanyFinancials:
    by_metric: dict[str, dict[int, float]] = {m: {} for m in SERIES_METRICS}
    for f in facts:
        by_metric[f["metric"]][int(f["fiscal_year"])] = float(f["value"])

    def series(metric: str) -> pd.Series[float]:
        data = by_metric[metric]
        if not data:
            return pd.Series(dtype=float)
        years = sorted(data)
        return pd.Series(
            [data[y] for y in years],
            index=pd.Index(years, name="fiscal_year"),
            dtype=float,
        )

    return CompanyFinancials(
        ticker=row["ticker"],
        name=row["name"],
        sector=row["sector"],
        industry=row["industry"],
        sic=row["sic"],
        revenue=series("revenue"),
        ebit=series("ebit"),
        da=series("da"),
        capex=series("capex"),
        nwc=series("nwc"),
        tax_rate=series("tax_rate"),
        total_debt=float(row["total_debt"]),
        cash=float(row["cash"]),
        shares_out=float(row["shares_out"]),
        price=float(row["price"]),
        beta=float(row["beta"]),
        sources=[
            SourceLink(label=s["label"], url=s["url"], accession=s["accession"]) for s in sources
        ],
    )


# --------------------------------------------------------------------------- #
# valuations
# --------------------------------------------------------------------------- #
def _null_if_nan(x: float) -> float | None:
    """NaN (incomputable: no shares, no price, g >= WACC) is stored as NULL."""
    return None if x != x else x


def _nan_if_null(x: float | None) -> float:
    """NULL restores as NaN so the domain semantics survive the round trip."""
    return float("nan") if x is None else float(x)


def valuation_row(result: DCFResult, created_at: datetime) -> dict[str, Any]:
    return {
        "ticker": result.fin.ticker,
        "created_at": created_at.isoformat(),
        "wacc": result.wacc,
        "enterprise_value": _null_if_nan(result.enterprise_value),
        "equity_value": _null_if_nan(result.equity_value),
        "fair_value_per_share": _null_if_nan(result.fair_value_per_share),
        "upside": _null_if_nan(result.upside),
        "assumptions_json": json.dumps(asdict(result.assumptions)),
        "projection_json": serialize_projection(result.projection),
        "warnings_json": json.dumps(result.warnings),
    }


def serialize_projection(df: pd.DataFrame) -> str:
    payload = {
        "index_name": df.index.name or "year",
        "columns": list(df.columns),
        "records": [
            {"__index__": int(str(idx)), **{c: float(row[c]) for c in df.columns}}
            for idx, row in df.iterrows()
        ],
    }
    return json.dumps(payload)


def deserialize_projection(text: str) -> pd.DataFrame:
    payload = json.loads(text)
    records = payload["records"]
    index = pd.Index([r["__index__"] for r in records], name=payload["index_name"])
    return pd.DataFrame(
        {c: [float(r[c]) for r in records] for c in payload["columns"]},
        index=index,
    )


def build_valuation_record(row: sqlite3.Row) -> ValuationRecord:
    return ValuationRecord(
        id=int(row["id"]),
        ticker=row["ticker"],
        created_at=datetime.fromisoformat(row["created_at"]),
        wacc=float(row["wacc"]),
        enterprise_value=_nan_if_null(row["enterprise_value"]),
        equity_value=_nan_if_null(row["equity_value"]),
        fair_value_per_share=_nan_if_null(row["fair_value_per_share"]),
        upside=_nan_if_null(row["upside"]),
        assumptions=Assumptions(**json.loads(row["assumptions_json"])),
        projection=deserialize_projection(row["projection_json"]),
        warnings=list(json.loads(row["warnings_json"])),
    )


# --------------------------------------------------------------------------- #
# notes
# --------------------------------------------------------------------------- #
def links_to_json(links: list[NoteLink]) -> str:
    return json.dumps([{"label": link.label, "url": link.url} for link in links])


def links_from_json(text: str) -> list[NoteLink]:
    return [NoteLink(label=d["label"], url=d["url"]) for d in json.loads(text)]


def build_note(row: sqlite3.Row, tags: list[str]) -> Note:
    return Note(
        id=int(row["id"]),
        ticker=row["ticker"],
        reference_id=(int(row["reference_id"]) if row["reference_id"] is not None else None),
        analysis_id=(int(row["analysis_id"]) if row["analysis_id"] is not None else None),
        title=row["title"],
        body=row["body"],
        tags=tags,
        links=links_from_json(row["links_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


# --------------------------------------------------------------------------- #
# reference library
# --------------------------------------------------------------------------- #
def reference_row(ref: Reference, added_at: datetime) -> dict[str, Any]:
    return {
        "kind": ref.kind,
        "title": ref.title,
        "location": ref.location,
        "collection": ref.collection,
        "origin": ref.origin,
        "added_at": added_at.isoformat(),
    }


def build_reference(row: sqlite3.Row) -> Reference:
    return Reference(
        id=int(row["id"]),
        kind=row["kind"],
        title=row["title"],
        location=row["location"],
        collection=row["collection"],
        origin=row["origin"],
        added_at=datetime.fromisoformat(row["added_at"]),
    )


# --------------------------------------------------------------------------- #
# attribute definitions + history
# --------------------------------------------------------------------------- #
def definition_row(d: AttributeDefinition, created_at: datetime) -> dict[str, Any]:
    return {
        "key": d.key,
        "label": d.label,
        "value_type": d.value_type,
        "scale_min": d.scale_min,
        "scale_max": d.scale_max,
        "allowed_values_json": json.dumps(d.allowed_values)
        if d.allowed_values is not None
        else None,
        "colors_json": json.dumps(d.colors) if d.colors is not None else None,
        "created_at": created_at.isoformat(),
    }


def build_definition(row: sqlite3.Row) -> AttributeDefinition:
    return AttributeDefinition(
        key=row["key"],
        label=row["label"],
        value_type=row["value_type"],
        scale_min=row["scale_min"],
        scale_max=row["scale_max"],
        allowed_values=(
            json.loads(row["allowed_values_json"]) if row["allowed_values_json"] else None
        ),
        colors=json.loads(row["colors_json"]) if row["colors_json"] else None,
    )


def attribute_value_row(v: AttributeValue, created_at: datetime) -> dict[str, Any]:
    return {
        "ticker": v.ticker,
        "key": v.key,
        "value": v.value,
        "source": v.source,
        "note_id": v.note_id,
        "reason": v.reason,
        "created_at": created_at.isoformat(),
    }


def build_attribute_value(row: sqlite3.Row) -> AttributeValue:
    return AttributeValue(
        id=int(row["id"]),
        ticker=row["ticker"],
        key=row["key"],
        value=row["value"],
        source=row["source"],
        note_id=int(row["note_id"]) if row["note_id"] is not None else None,
        reason=row["reason"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# --------------------------------------------------------------------------- #
# analyses (the balcony)
# --------------------------------------------------------------------------- #
def analysis_row(a: Analysis, now: datetime) -> dict[str, Any]:
    return {
        "kind": a.kind,
        "title": a.title,
        "summary": a.summary,
        "created_at": (a.created_at or now).isoformat(),
        "updated_at": now.isoformat(),
    }


def build_analysis(row: sqlite3.Row) -> Analysis:
    return Analysis(
        id=int(row["id"]),
        kind=row["kind"],
        title=row["title"],
        summary=row["summary"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
