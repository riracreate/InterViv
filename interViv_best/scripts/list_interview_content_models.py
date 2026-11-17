"""Read-only eligible-model catalog. Requires live questions gate; no completions."""
from __future__ import annotations

import argparse
import http.client
import json
import ssl
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import interview_llm, llm_outbound_gate  # noqa: E402


def _urlerror_summary(exc: urllib.error.URLError) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTPError (status={exc.code})" if type(exc.code) is int else "HTTPError"
    reason = exc.reason
    parts = [type(reason).__name__ if isinstance(reason, BaseException) else "non_exception_reason"]
    err_no = getattr(reason, "errno", None) if isinstance(reason, BaseException) else None
    if type(err_no) is int:
        parts.append(f"errno={err_no}")
    ssl_reason = getattr(reason, "reason", None) if isinstance(reason, ssl.SSLError) else None
    if (isinstance(ssl_reason, str) and ssl_reason.isascii() and ssl_reason.isupper()
            and ssl_reason.replace("_", "").isalnum() and len(ssl_reason) <= 64):
        parts.append(f"ssl_reason={ssl_reason}")
    verify_code = getattr(reason, "verify_code", None) if isinstance(reason, ssl.SSLCertVerificationError) else None
    if type(verify_code) is int:
        parts.append(f"verify_code={verify_code}")
    return f"URLError ({', '.join(parts)})"


def main(argv=None, *, catalog_source=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-context", type=int, default=interview_llm.RoutingSettings.from_env().min_content_context)
    parser.add_argument("--diagnostics", action="store_true",
                        help="Also print row count, links.next presence and conversation ID/canonical slug.")
    args = parser.parse_args(argv)
    if args.min_context < 1:
        parser.error("--min-context must be positive")
    if not llm_outbound_gate.llm_consumer_enabled("questions"):
        parser.error("LLM_LIVE_FETCH=1 and the questions consumer are required; no catalog was fetched")
    # This endpoint carries no candidate text and creates no budget/journal.
    try:
        payload = (catalog_source or interview_llm._fetch_catalog)()
        rows = interview_llm.catalog_rows(payload)
    except interview_llm.RoutingError as exc:
        parser.exit(1, f"Catalog unavailable: {exc}\n")
    except urllib.error.URLError as exc:
        parser.exit(1, f"Catalog unavailable: {_urlerror_summary(exc)}\n")
    except (KeyError, TypeError, ValueError, OSError, http.client.HTTPException) as exc:
        parser.exit(1, f"Catalog unavailable: {type(exc).__name__}\n")
    if args.diagnostics:
        links = payload.get("links")
        print(f"total_rows_received\t{len(rows)}")
        print(f"links_present\t{str('links' in payload).lower()}")
        print(f"links_object_present\t{str(isinstance(links, dict)).lower()}")
        print(f"links_value\t{json.dumps(links, sort_keys=True)}")
        print(f"links_next_present\t{str('next' in (payload.get('links') or {})).lower()}")
        print(f"links_next_value\t{json.dumps(links.get('next') if isinstance(links, dict) else None, sort_keys=True)}")
        paid = next((row for row in rows if isinstance(row, dict)
                     and row.get("id") == interview_llm.PAID_CONVERSATION_MODEL), {})
        print(f"conversation_model_id\t{paid.get('id') or '(absent)'}")
        print(f"conversation_canonical_slug\t{paid.get('canonical_slug') or '(absent)'}")
    print("id\tcontext_length\tparameters")
    for entry in sorted((row for row in rows if isinstance(row, dict)
                         and interview_llm._free_structured(row, args.min_context)), key=lambda row: row["id"]):
        print(f"{entry['id']}\t{interview_llm.content_context_length(entry)}\t{','.join(sorted(entry['supported_parameters']))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
