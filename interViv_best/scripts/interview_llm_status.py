"""Inspect routing journal offline; clear a block only with an explicit option."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.interview_llm import RoutingSettings  # noqa: E402
from modules.interview_llm_budget import BudgetUnavailable, RequestBudget  # noqa: E402


def main(argv=None) -> int:
    settings = RoutingSettings.from_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, default=settings.state_path)
    parser.add_argument("--account", default=settings.account)
    parser.add_argument("--clear-credit-block", action="store_true",
                        help="Explicitly unblock after fixing credits; does not refund counters.")
    parser.add_argument("--clear-access-block", action="store_true",
                        help="Explicitly unblock a 401/403 after fixing credentials/access.")
    args = parser.parse_args(argv)
    try:
        budget = RequestBudget(args.journal, account=args.account, high_free_limit=settings.high_free_limit)
        status = budget.inspect()
        if args.clear_credit_block or args.clear_access_block:
            if status["state"] is None:
                parser.error("the selected account has no journal state to clear")
            if args.clear_credit_block:
                budget.clear_credit_block()
            if args.clear_access_block:
                budget.clear_access_block()
            status = budget.inspect()
        print(json.dumps(status, indent=2, sort_keys=True))
    except BudgetUnavailable as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
