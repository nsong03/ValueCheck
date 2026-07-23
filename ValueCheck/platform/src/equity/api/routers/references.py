"""References router: the knowledge library (books, articles, PDFs,
webpages) — CRUD, on-demand scan, and opening the underlying file/URL."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse, RedirectResponse

from equity.api.deps import get_references
from equity.api.schemas.references import (
    ReferenceIn,
    ReferenceOut,
    ReferenceScanOut,
    ReferenceUpdate,
)
from equity.application.reference_service import ReferenceService
from equity.errors import NotFoundError

router = APIRouter(prefix="/references", tags=["references"])


@router.post("", response_model=ReferenceOut, status_code=201)
def create_reference(
    payload: ReferenceIn,
    references: Annotated[ReferenceService, Depends(get_references)],
) -> ReferenceOut:
    ref = references.create(
        kind=payload.kind,
        title=payload.title,
        location=payload.location,
        collection=payload.collection,
    )
    return ReferenceOut.from_domain(ref)


@router.get("", response_model=list[ReferenceOut])
def list_references(
    references: Annotated[ReferenceService, Depends(get_references)],
) -> list[ReferenceOut]:
    """Every tracked reference, ordered by collection then title."""
    return [ReferenceOut.from_domain(r) for r in references.list_all()]


@router.post("/scan", response_model=ReferenceScanOut)
def scan_references(
    references: Annotated[ReferenceService, Depends(get_references)],
) -> ReferenceScanOut:
    """Walk the configured library path for PDFs not yet tracked (also runs
    once automatically at server startup); a no-op if unconfigured."""
    created = references.scan()
    return ReferenceScanOut(created=[ReferenceOut.from_domain(r) for r in created])


@router.get("/{reference_id}", response_model=ReferenceOut)
def get_reference(
    reference_id: int,
    references: Annotated[ReferenceService, Depends(get_references)],
) -> ReferenceOut:
    return ReferenceOut.from_domain(references.get(reference_id))


@router.patch("/{reference_id}", response_model=ReferenceOut)
def update_reference(
    reference_id: int,
    payload: ReferenceUpdate,
    references: Annotated[ReferenceService, Depends(get_references)],
) -> ReferenceOut:
    updated = references.update(
        reference_id,
        kind=payload.kind,
        title=payload.title,
        collection=payload.collection,
    )
    return ReferenceOut.from_domain(updated)


@router.delete("/{reference_id}", status_code=204)
def delete_reference(
    reference_id: int,
    references: Annotated[ReferenceService, Depends(get_references)],
) -> Response:
    references.delete(reference_id)
    return Response(status_code=204)


@router.get("/{reference_id}/file")
def reference_file(
    reference_id: int,
    references: Annotated[ReferenceService, Depends(get_references)],
) -> Response:
    """Open the reference: redirects to the URL, or streams the local file.

    Single-user, local-first, bound to 127.0.0.1 — the same trust boundary
    as your own file explorer, so any local path you've pointed a reference
    at is servable, not just ones under the configured library folder.
    """
    ref = references.get(reference_id)
    if ref.location.startswith(("http://", "https://")):
        return RedirectResponse(ref.location)
    path = Path(ref.location)
    if not path.is_file():
        raise NotFoundError(f"file not found on disk: {ref.location}")
    return FileResponse(path, filename=path.name)
