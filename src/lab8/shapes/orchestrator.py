"""Shape C — orchestrator plus read-only investigators.

1. The orchestrator reads the allowlisted claim view. Missing order_id ->
   `needs_info` before any handoff.
2. It builds a handoff with `lab8.handoff.make_handoff`: allowed tools are
   read-only (lookup_order, lookup_policy, lookup_refund_history,
   compute_compensation). `facts` is empty: the orchestrator has no verified
   order facts yet, and ticket text is never a fact. parent_secret, raw headers
   and the claim row never go into the handoff.
3. `lab8.runtime.run_readonly_investigators` runs those tools. Investigators
   have no write registry (worker=True, ToolRejected on write tools).
4. The orchestrator checks the investigator's order view, takes the quote from
   `compute_compensation` (code), and is the only caller of
   `durability.issue_refund`, with the FULL quote.
5. The trace holds the sanitized handoff and allowlisted tool outputs, never
   the parent context.

An LLM summary of the parent context is not a sanitizer. The allowlist is.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"
INVESTIGATOR_TOOLS = ["lookup_order", "lookup_policy", "lookup_refund_history", "compute_compensation"]


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
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    except Exception as exc:
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

    # Orchestrator: allowlisted claim view.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("orchestrator", {"step": "get_claim_view", "found": claim["found"], "order_id": claim.get("order_id")})
    if not claim["found"]:
        return done("failed", 0, "unknown_claim")
    if not claim.get("order_id"):
        return done("needs_info", 0, "missing_order_id")

    # Plan (model call). Prompt is the claim id only; the plan text is not used for decisions.
    complete(budget, seed=seed, purpose="plan", prompt=f"{claim_id}|investigate")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="verify_order_and_quote",
        facts={},
        allowed_tools=list(INVESTIGATOR_TOOLS),
    )
    trace.add("handoff", safe_dump(handoff))

    investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    # Investigator report is a model step too (summarising tool output for the orchestrator).
    complete(budget, seed=seed, purpose="investigator", prompt=f"{claim_id}|report")
    tools = investigated["tools"]
    order_view = tools.get("lookup_order") or {}
    history = tools.get("lookup_refund_history") or {}
    trace.add("investigator", _investigator_trace(investigated))

    if not order_view.get("visible"):
        return done("escalated", 0, order_view.get("reason"))

    order = order_view["order"]
    # Orchestrator cross-checks: the investigator must have looked at the claim's own order.
    if order.get("order_id") != claim["order_id"]:
        return done("failed", 0, "order_mismatch")

    quote = tools.get("compute_compensation")
    if not isinstance(quote, dict) or "amount_vnd" not in quote:
        budget.add_tool(tool_cost())
        quote = compute_compensation(conn, order)
    trace.add("quote", safe_dump(quote))
    proposal = int(quote["amount_vnd"])
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    trace.add("orchestrator", {"step": "pre_refund", "already_refunded_vnd": history.get("refunded_vnd")})
    budget.add_tool(tool_cost())
    outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)


def _investigator_trace(investigated: dict[str, Any]) -> dict[str, Any]:
    tools = investigated["tools"]
    order_view = tools.get("lookup_order") or {}
    view: dict[str, Any] = {"visible": bool(order_view.get("visible")), "reason": order_view.get("reason")}
    if order_view.get("visible"):
        view["order"] = safe_dump(order_view["order"])
    history = tools.get("lookup_refund_history") or {}
    policies = (tools.get("lookup_policy") or {}).get("policies") or []
    return {
        "claim_view": safe_dump(investigated.get("claim_view") or {}),
        "lookup_order": view,
        "refund_history": {"refund_count": history.get("refund_count"), "refunded_vnd": history.get("refunded_vnd")},
        "policy_ids": [p.get("policy_id") for p in policies],
    }
