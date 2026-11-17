"""Shape B — one ReAct agent.

Uses `lab8.runtime.run_react` with max_steps=8. `decide` picks read tools only
(get_claim_view -> lookup_order -> lookup_refund_history -> compute_compensation)
and then returns a final suggestion. Every decide step is one MockLLM call so
the cost stays comparable with the other shapes.

Code / model boundary:
- The model sees the ticket, but `decide` takes order facts only from tool
  results (the DB row), never from ticket text. A ticket that says "trễ 9 ngày"
  or cites SHIP-LATE-OLD does not change anything.
- The model never chooses the amount. After the loop the shape takes the quote
  from the `compute_compensation` tool result (code) and is the only caller of
  `durability.issue_refund`, with the FULL quote. The host subtracts what other
  claims already got for the same order.
- `run_react` dispatches with worker=True, so a write tool raises ToolRejected.

Trace policy: only tool names, allowlisted order view, refund totals, the quote
and the host outcome. No ticket text, no principal id, no parent context.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


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


class _Agent:
    """Seeded ReAct policy. Remembers tool results across steps."""

    def __init__(self, budget: Budget, trace: Trace, *, seed: int, claim_id: str) -> None:
        self.budget = budget
        self.trace = trace
        self.seed = seed
        self.claim_id = claim_id
        self.claim: dict[str, Any] | None = None
        self.order_view: dict[str, Any] | None = None
        self.history: dict[str, Any] | None = None
        self.quote: dict[str, Any] | None = None
        self.step = 0

    def _remember(self, obs: dict[str, Any]) -> None:
        name = obs.get("last_tool")
        result = obs.get("last_result")
        if name is None or result is None:
            return
        if name == "get_claim_view":
            self.claim = result
            self.trace.add("observe", {"tool": name, "found": result.get("found"), "order_id": result.get("order_id")})
        elif name == "lookup_order":
            self.order_view = result
            view = {"visible": bool(result.get("visible")), "reason": result.get("reason")}
            if result.get("visible"):
                view["order"] = safe_dump(result["order"])
            self.trace.add("observe", {"tool": name, "view": view})
        elif name == "lookup_refund_history":
            self.history = result
            self.trace.add(
                "observe",
                {"tool": name, "refund_count": result.get("refund_count"), "refunded_vnd": result.get("refunded_vnd")},
            )
        elif name == "compute_compensation":
            self.quote = result
            self.trace.add("observe", {"tool": name, "quote": safe_dump(result)})

    def _act(self, action: dict[str, Any]) -> dict[str, Any]:
        label = action.get("tool") or "final"
        self.trace.add("act", {"step": self.step, "action": label})
        return action

    def decide(self, obs: dict[str, Any]) -> dict[str, Any]:
        self.step += 1
        self._remember(obs)
        # One model call per step. The prompt holds no secret; the reply is not used for money.
        complete(self.budget, seed=self.seed, purpose="react", prompt=f"{self.claim_id}|step={self.step}")

        if self.claim is None:
            return self._act({"tool": "get_claim_view", "args": {"claim_id": self.claim_id}})
        if not self.claim.get("found"):
            return self._act({"final": {"status": "failed", "error_reason": "unknown_claim"}})
        if not self.claim.get("order_id"):
            return self._act({"final": {"status": "needs_info", "error_reason": "missing_order_id"}})
        scope = {"order_id": self.claim["order_id"], "principal_id": self.claim["principal_id"]}
        if self.order_view is None:
            return self._act({"tool": "lookup_order", "args": scope})
        if not self.order_view.get("visible"):
            return self._act({"final": {"status": "escalated", "error_reason": self.order_view.get("reason")}})
        if self.history is None:
            return self._act({"tool": "lookup_refund_history", "args": scope})
        if self.quote is None:
            # Facts come from the DB order row, not the ticket.
            return self._act({"tool": "compute_compensation", "args": {"order": dict(self.order_view["order"])}})
        if int(self.quote["amount_vnd"]) <= 0:
            return self._act({"final": {"status": "denied", "error_reason": self.quote.get("reason")}})
        return self._act({"final": {"status": "propose_refund"}})


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

    agent = _Agent(budget, trace, seed=seed, claim_id=claim_id)
    # The ticket is user data. The model gets only the claim id as its task; it reads facts via tools.
    loop = run_react(
        conn,
        budget,
        observation={"claim": {"claim_id": claim_id}},
        decide=agent.decide,
        max_steps=MAX_STEPS,
        worker=True,
    )
    trace.add("loop", {"stopped": loop["stopped"], "steps": agent.step})
    final = loop["final"]
    status = final.get("status")

    if loop["stopped"] != "final":
        return done("failed", 0, "step_cap")
    if status in ("failed", "needs_info", "escalated", "denied"):
        return done(status, 0, final.get("error_reason"))

    # Code, not the model, validates the proposal before the host write.
    if status != "propose_refund" or agent.quote is None or agent.order_view is None:
        return done("failed", 0, "invalid_final")
    # Re-check ownership with code after the loop: the claim row is the source of truth.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if claim.get("order_id") != agent.order_view["order"]["order_id"]:
        return done("failed", 0, "order_mismatch")
    proposal = int(agent.quote["amount_vnd"])
    if proposal <= 0:
        return done("denied", 0, agent.quote.get("reason"))

    budget.add_tool(tool_cost())
    outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)
