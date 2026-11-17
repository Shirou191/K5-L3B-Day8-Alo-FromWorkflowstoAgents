"""Shape A — deterministic workflow.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Fixed Python steps. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> status `needs_info`. Do not write the ledger.
3. `lookup_order`. If not visible -> `escalated`. Do not copy phone, address, item, internal note.
4. Quote from the order row. Ignore delay numbers written in the ticket.
5. Quote amount 0 -> `denied`. Do not call issue_refund.
6. Quote amount > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`.
   Pass the FULL quote. The host checks the claim's own approval and subtracts
   what earlier claims already got for the same order (T13, T14).
   Auth failure or order already refunded -> `denied` (the host writes `policy_denied`).
   `proposal_amount` stays the full quote. Amount conflict -> `failed`.
7. Success -> `resolved`. One ledger row, one `refund_committed` audit.
8. MockLLM is used once, only to draft the reply text. It never sees the
   amount decision and its output is not used for any branch.

Trace policy: only allowlisted fields are traced (claim_id, order_id, the
`lookup_order` view, the quote, the host outcome reason). The ticket text,
principal id, parent_secret and raw headers are never traced.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at, budget=budget, trace=trace)
    except InjectedCrash:
        # Flush what we have, then let the crash propagate (T12 checks it fires).
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    except Exception as exc:  # run_claim must never raise for ordinary errors.
        trace.add("error", {"reason": "exception", "type": type(exc).__name__})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=f"exception:{type(exc).__name__}",
        )
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
    budget: Budget,
    trace: Trace,
) -> RunResult:
    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        complete(budget, seed=seed, purpose="draft", prompt=f"status={status}")
        trace.add("decision", {"status": status, "proposal_amount": int(proposal), "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    # Step 1: allowlisted claim view.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("step", {"name": "get_claim_view", "found": claim["found"], "order_id": claim.get("order_id")})
    if not claim["found"]:
        return done("failed", 0, "unknown_claim")

    # Step 2: order id comes from the claim row only, never from ticket text.
    if not claim.get("order_id"):
        return done("needs_info", 0, "missing_order_id")

    # Step 3: ownership-scoped order lookup.
    budget.add_tool(tool_cost())
    order_view = lookup_order(conn, claim["order_id"], claim["principal_id"])
    trace.add("step", {"name": "lookup_order", "view": _order_trace(order_view)})
    if not order_view.get("visible"):
        return done("escalated", 0, order_view.get("reason"))

    # Step 4: quote from the DB order row with current policies only.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order_view["order"])
    trace.add("step", {"name": "compute_compensation", "quote": safe_dump(quote)})
    proposal = int(quote["amount_vnd"])

    # Step 5: nothing owed -> deny without touching the host write path.
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # Step 6: host gate. Full quote; host checks approval, cap, idempotency.
    budget.add_tool(tool_cost())
    outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("step", {"name": "issue_refund", "ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])

    # Step 7.
    return done("resolved", proposal, None)


def _order_trace(view: dict[str, Any]) -> dict[str, Any]:
    """lookup_order already allowlists fields; copy only those keys."""
    out: dict[str, Any] = {"visible": bool(view.get("visible")), "reason": view.get("reason")}
    if view.get("visible"):
        out["order"] = safe_dump(view["order"])
    return out
