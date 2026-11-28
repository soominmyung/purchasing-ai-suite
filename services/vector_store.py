"""
The history store: one Chroma collection of purchasing history documents, each stored whole
and retrieved by its header metadata. No embedding is computed and nothing is searched by
similarity: Chroma is used as a document store with metadata filters.
"""
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

# Chroma storage path (local directory)
_CHROMA_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma"
_CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Chroma keeps a vector with every record. Retrieval here is by metadata alone (search_history),
# so each document gets this one-number placeholder instead of an embedding. Given no vector,
# Chroma would download an embedding model and embed every document itself.
_NO_VECTOR = [0.0]
_BATCH = 1000  # records per write

_history = None
# Opening the Chroma client from several threads at once fails ("Could not connect to tenant
# default_tenant", seen 2026-10-24 with four approval calls in parallel): one opener at a time.
_open_lock = threading.Lock()


def _add(collection, ids: list[str], texts: list[str], metadatas: list[dict[str, Any]]) -> None:
    for i in range(0, len(ids), _BATCH):
        part = slice(i, i + _BATCH)
        collection.add(ids=ids[part], documents=texts[part], metadatas=metadatas[part],
                       embeddings=[_NO_VECTOR] * len(ids[part]))


def _fill_unread_dates(collection) -> int:
    """A document's date is read once, when it is stored, and retrieval uses the stored value. So
    a document stored without a date is read again here: if its date line can be read now, the
    date is filled in. A document with no date line stays as it is, placed by the date it was
    stored. Returns how many dates were filled in."""
    held = collection.get(include=["metadatas"])
    undated = [i for i, m in zip(held["ids"], held["metadatas"]) if not (m or {}).get("event_date")]
    filled = 0
    for start in range(0, len(undated), _BATCH):
        rows = collection.get(ids=undated[start:start + _BATCH], include=["documents", "metadatas"])
        found = [(i, {**(m or {}), "event_date": day})
                 for i, text, m in zip(rows["ids"], rows["documents"], rows["metadatas"])
                 if (day := _extract_event_date(text))]
        if found:
            collection.update(ids=[i for i, _ in found], metadatas=[m for _, m in found])
            filled += len(found)
    return filled


def history_collection():
    """The history collection, opened once, with Chroma's usage telemetry off. On opening, a store
    written with embeddings is rewritten (its documents and metadata kept, the vectors dropped),
    and documents stored without a date are read again for one (_fill_unread_dates)."""
    global _history
    with _open_lock:
        if _history is None:
            client = chromadb.PersistentClient(path=str(_CHROMA_DIR),
                                               settings=ChromaSettings(anonymized_telemetry=False))
            collection = client.get_or_create_collection(HISTORY_COLLECTION, embedding_function=None)
            held = collection.get(limit=1, include=["embeddings"])["embeddings"]
            if held is not None and len(held) and len(held[0]) != len(_NO_VECTOR):
                rows = collection.get(include=["documents", "metadatas"])
                client.delete_collection(HISTORY_COLLECTION)
                collection = client.get_or_create_collection(HISTORY_COLLECTION, embedding_function=None)
                _add(collection, rows["ids"], rows["documents"], rows["metadatas"])
            _fill_unread_dates(collection)
            _history = collection
        return _history


def get_vector_stores() -> None:
    """Open the history store at start-up."""
    history_collection()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# The document's date: its 'Date:' line (also 'Dated:', 'Report date:', 'Document date:',
# 'Issue date:'), in whichever way the date is written.
_DATE_LINE_RE = re.compile(r"^\s*(?:(?:Report|Document|Issue)\s+)?Dated?\s*[:\-–]\s*(.+?)\s*$",
                           re.IGNORECASE | re.MULTILINE)
_MONTHS = {name: n for n, names in enumerate(
    ("january jan", "february feb", "march mar", "april apr", "may", "june jun", "july jul", "august aug",
     "september sep sept", "october oct", "november nov", "december dec"), 1) for name in names.split()}
_ORDINAL = r"(?:st|nd|rd|th)?"
_DATE_PATTERNS = (
    # year first: 2025-04-05, 2025/4/5, 2025.04.05, 2025. 4. 5., 2025년 4월 5일, 20250405
    ("ymd", re.compile(r"(?<!\d)(\d{4})\s*[-/.년]\s*(\d{1,2})\s*[-/.월]\s*(\d{1,2})(?!\d)")),
    ("ymd", re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")),
    # the month as a word: 5 April 2025, 5th Apr 2025, 05-Apr-25; April 5, 2025, Apr 5th 2025
    ("dmy_name", re.compile(rf"(?<!\d)(\d{{1,2}}){_ORDINAL}[\s\-.]*(?:of\s+)?([A-Za-z]{{3,9}})\.?,?[\s\-.]*(\d{{4}}|\d{{2}})(?!\d)")),
    ("mdy_name", re.compile(rf"([A-Za-z]{{3,9}})\.?\s*(\d{{1,2}}){_ORDINAL},?\s*(\d{{4}})(?!\d)")),
    # figures only, day first as dates are written in the UK (and in the stock CSV's file name):
    # 05/04/2025, 5.4.25. Month first is read only where it cannot be a day (04/25/2025).
    ("dmy", re.compile(r"(?<!\d)(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4}|\d{2})(?!\d)")),
)


def read_date(raw: str) -> str:
    """A written date as an ISO date; "" when the text holds no full date in a form listed above
    (a month and year alone, a quarter). An unknown form is left unread rather than guessed."""
    for kind, pattern in _DATE_PATTERNS:
        for m in pattern.finditer(raw or ""):
            a, b, c = m.groups()
            if kind == "ymd":
                y, mo, d = int(a), int(b), int(c)
            elif kind == "dmy_name":
                d, mo, y = int(a), _MONTHS.get(b.lower()), int(c)
            elif kind == "mdy_name":
                mo, d, y = _MONTHS.get(a.lower()), int(b), int(c)
            else:
                d, mo, y = int(a), int(b), int(c)
                if mo > 12 >= d:
                    d, mo = mo, d
            if not mo:
                continue
            y += 2000 if y < 100 else 0
            try:
                if 1990 <= y <= 2100:
                    return datetime(y, mo, d).date().isoformat()
            except ValueError:
                continue
    return ""


def _extract_event_date(text: str) -> str:
    """The date on the document's own date line, as an ISO date: the first such line that holds a
    date. Returns "" if there is none; callers fall back to ingested_at in that case (see
    _doc_date) rather than mistaking an undated document for old.
    """
    for m in _DATE_LINE_RE.finditer(text or ""):
        found = read_date(m.group(1))
        if found:
            return found
    return ""


# ----------------------------------------------------------------------------- history
# One collection for all purchasing history. Every document belongs to a supplier, read from
# its header (not from where it was uploaded):
#   Supplier: <name>          (required; alone = supplier-wide, e.g. a strike or line refit)
#   Item: <name>[, <name>]    (optional; narrows the document to those items from this supplier)
#   ItemCode: <code>[, ...]   (optional)
#   Date: <date>
HISTORY_COLLECTION = "history"
HEADER_LINES = 15
_HEADER_RE = {
    "supplier": re.compile(r"^\s*Supplier\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "items": re.compile(r"^\s*Items?\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "item_codes": re.compile(r"^\s*Item\s*Codes?\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE),
}


def history_key(value: str) -> str:
    """Case, spacing and punctuation do not matter when matching names and codes."""
    return re.sub(r"[\W_]+", "", str(value or "").lower())


def _split_list(value: str) -> list[str]:
    return [v.strip() for v in re.split(r"[,;/]", value) if v.strip()]


def parse_history_header(text: str) -> dict[str, Any]:
    """Supplier, items, item codes and date from the first lines of a history document."""
    header = {"supplier": "", "items": [], "item_codes": []}
    for line in (text or "").splitlines()[:HEADER_LINES]:
        for field, rx in _HEADER_RE.items():
            m = rx.match(line)
            if not m:
                continue
            if field == "supplier":
                header["supplier"] = header["supplier"] or m.group(1)
            else:
                header[field] += _split_list(m.group(1))
            break
    header["date"] = _extract_event_date(text)
    return header


def history_metadata(header: dict[str, Any], source: str = "", origin: str = "upload",
                     fingerprint: str = "") -> dict[str, Any]:
    """Chroma metadata for one history document. Lists cannot be filtered in Chroma, so each
    supplier, item name and item code also gets its own key for the retrieval filter.
    origin + source identify the document: "folder" with its path in the shared folder, or
    "upload" with its file name."""
    meta: dict[str, Any] = {
        "doc_type": "history",
        "supplier_name": header.get("supplier") or "",
        "items": ", ".join(header.get("items") or []),
        "item_codes": ", ".join(header.get("item_codes") or []),
        "event_date": header.get("date") or "",
        "ingested_at": _now_iso(),
        "source": source or "",
        "origin": origin,
        "source_id": f"{origin}:{source}",
        "fingerprint": fingerprint or "",
    }
    if meta["supplier_name"]:
        meta[f"s:{history_key(meta['supplier_name'])}"] = True
    for value in (header.get("items") or []) + (header.get("item_codes") or []):
        meta[f"i:{history_key(value)}"] = True
    return meta


def ingest_history(text: str, source: str = "", origin: str = "upload", fingerprint: str = "") -> dict[str, Any]:
    """Store one history document, replacing any earlier version with the same origin and
    source, so a file sent twice is held once. Returns what its header was read as, so the
    uploader can check it. A document that names no supplier is refused."""
    header = parse_history_header(text)
    if not header["supplier"]:
        raise ValueError("The header names no supplier (expected a 'Supplier:' line).")
    if source:
        delete_history_source(origin, source)
    # stored whole: a history document is at most two pages and is retrieved by its metadata
    _add(history_collection(), [uuid.uuid4().hex], [text], [history_metadata(header, source, origin, fingerprint)])
    return header


def delete_history_source(origin: str, source: str) -> int:
    """Remove one document. Returns how many entries were removed (0 if it was not held)."""
    collection = history_collection()
    ids = collection.get(where={"source_id": f"{origin}:{source}"})["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def history_sources(origin: str) -> dict[str, dict[str, str]]:
    """Documents held from one origin: {source: {fingerprint, supplier, items}}."""
    raw = history_collection().get(where={"origin": origin}, include=["metadatas"])
    out: dict[str, dict[str, str]] = {}
    for m in raw.get("metadatas") or []:
        out[m.get("source") or ""] = {"fingerprint": m.get("fingerprint") or "",
                                      "supplier": m.get("supplier_name") or "", "items": m.get("items") or ""}
    return out


def known_suppliers() -> set[str]:
    """Normalised names of every supplier named in a history header."""
    raw = history_collection().get(include=["metadatas"])
    return {history_key(m.get("supplier_name")) for m in raw.get("metadatas") or [] if m.get("supplier_name")}


# Retrieval rule agreed with the purchasing team: documents from the 12 months before the
# snapshot date, and within that the 5 most recent about the supplier as a whole and the 5 most
# recent about each item. Set in config.py (history_window_months, history_docs_per_scope).
def _doc_date(meta: dict[str, Any]) -> str:
    """The document's own date, or its upload date when the document is undated."""
    return meta.get("event_date") or (meta.get("ingested_at") or "")[:10]


def _months_before(day: str, months: int) -> str:
    y, m, d = (int(x) for x in day[:10].split("-"))
    m -= months
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}-{min(d, 28):02d}"


def search_history(supplier: str, items: list[tuple[str, str]], as_of: str,
                   months: int, per_scope: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    History documents for one analysis. A document qualifies when its header names this
    supplier and it is dated within `months` before `as_of`. Within that, the `per_scope` most
    recent documents are kept in each scope:
    - supplier scope: supplier-wide documents and documents about this supplier's other items;
    - item scope (one per item in `items`): this supplier's documents about that item.
    A scope with fewer documents gives those it has. A document in several scopes is kept once.
    Returns (documents, counts) where counts says how many qualified and how many were left out,
    for the report.
    """
    own = history_key(supplier)
    counts = {"window_months": months, "from": _months_before(as_of, months), "to": as_of[:10],
              "per_scope": per_scope, "matched": 0, "in_window": 0, "included": 0, "left_out": 0}
    if not own:
        return [], counts
    raw = history_collection().get(where={f"s:{own}": True}, include=["metadatas", "documents"])

    # one entry per document
    docs: dict[tuple, dict[str, Any]] = {}
    for text, m in zip(raw.get("documents") or [], raw.get("metadatas") or []):
        key = (m.get("source_id") or m.get("source"), m.get("supplier_name"), m.get("items"),
               m.get("item_codes"), m.get("event_date"), m.get("ingested_at"))
        if key in docs:
            docs[key]["text"] += "\n" + text
            continue
        docs[key] = {"supplier": m.get("supplier_name") or "",
                     "items": _split_list(m.get("items") or ""),
                     "item_codes": _split_list(m.get("item_codes") or ""),
                     "date": m.get("event_date") or "", "source": m.get("source") or "",
                     "_sort": _doc_date(m), "_keys": {k_ for k_ in m if k_.startswith("i:")},
                     "text": text}
    counts["matched"] = len(docs)
    start, end = counts["from"], counts["to"]
    pool = sorted((d for d in docs.values() if start < d["_sort"] <= end), key=lambda d: d["_sort"], reverse=True)
    counts["in_window"] = len(pool)

    item_keys = [{f"i:{history_key(v)}" for v in (code, name) if history_key(v)} for code, name in items]
    all_item_keys = set().union(*item_keys) if item_keys else set()
    scopes = [[d for d in pool if not (d["_keys"] & all_item_keys)]]
    for ik in item_keys:
        scopes.append([d for d in pool if d["_keys"] & ik])
    chosen: list[dict[str, Any]] = []
    for scope in scopes:
        for d in scope[:per_scope]:
            if not any(d is c for c in chosen):
                chosen.append(d)
    chosen.sort(key=lambda d: d["_sort"], reverse=True)
    counts["included"] = len(chosen)
    counts["left_out"] = counts["in_window"] - len(chosen)
    for d in chosen:
        d.pop("_sort"), d.pop("_keys")
    return chosen, counts

