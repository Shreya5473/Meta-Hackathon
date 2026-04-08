"""GeoTrade OpenEnv — task graders.

Each grader is a pure function:
    grade_<task>(action, scenario, **ctx) -> GeoTradeReward

All graders are deterministic and produce scores in [0.0, 1.0].
Partial-credit signals are emitted even for incomplete answers.
"""
from __future__ import annotations

import math
from typing import Any

from openenv.models import (
    AssetDecision,
    GeoTradeAction,
    GeoTradeReward,
    RewardComponents,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _strict_unit(v: float, eps: float = 1e-4) -> float:
    """Clamp score strictly inside (0, 1), avoiding exact boundary values."""
    return max(eps, min(1.0 - eps, v))


def _reasoning_keywords_score(text: str, keywords: list[str]) -> float:
    """Return fraction of keywords present in the reasoning text (case-insensitive)."""
    if not keywords or not text:
        return 0.0
    text_low = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_low)
    return hits / len(keywords)


def _direction_map(decisions: list[AssetDecision]) -> dict[str, str]:
    return {d.symbol: d.direction for d in decisions}


def _weight_map(decisions: list[AssetDecision]) -> dict[str, float]:
    return {d.symbol: d.weight for d in decisions}


# ══════════════════════════════════════════════════════════════════════════════
# TASK 1 — EASY grader
# ══════════════════════════════════════════════════════════════════════════════

def grade_easy(action: GeoTradeAction, scenario: dict[str, Any]) -> GeoTradeReward:
    """Score an agent's answer on the signal-identification task.

    Component weights:
        accuracy (asset identification):   45%
        accuracy (direction):              45%
        reasoning quality:                 10%
    """
    gt = scenario["ground_truth"]
    correct_top3: list[str] = gt["top_impacted"]        # top 3 expected assets
    correct_dirs: dict[str, str] = gt["directions"]     # all expected directions
    keywords: list[str] = gt.get("reasoning_keywords", [])

    dir_map = _direction_map(action.decisions)
    active_decisions = [d for d in action.decisions if d.direction != "HOLD"]

    # ── Asset identification ──────────────────────────────────────────────────
    identified_symbols = {d.symbol for d in active_decisions}
    top3_set = set(correct_top3)
    true_positives = identified_symbols & top3_set
    # Precision * Recall F1-style: reward for getting the right ones, penalise extras
    precision = len(true_positives) / max(1, len(identified_symbols))
    recall = len(true_positives) / max(1, len(top3_set))
    if precision + recall == 0:
        asset_score = 0.0
    else:
        asset_score = 2 * precision * recall / (precision + recall)  # F1

    # ── Direction accuracy ────────────────────────────────────────────────────
    direction_hits = sum(
        1
        for sym, direction in dir_map.items()
        if sym in correct_dirs and direction == correct_dirs[sym]
    )
    direction_total = len(correct_dirs)
    direction_score = direction_hits / max(1, direction_total)

    # ── Reasoning quality ─────────────────────────────────────────────────────
    reasoning_text = (action.reasoning or "") + " " + (action.primary_signal or "")
    reasoning_score = _reasoning_keywords_score(reasoning_text, keywords)

    # ── Weighted total ────────────────────────────────────────────────────────
    total = _strict_unit(_clamp(0.45 * asset_score + 0.45 * direction_score + 0.10 * reasoning_score))
    partial = _clamp((asset_score + direction_score) / 2)

    explanation = (
        f"Asset identification (F1): {asset_score:.2f} | "
        f"Direction accuracy: {direction_score:.2f} ({direction_hits}/{direction_total}) | "
        f"Reasoning keywords: {reasoning_score:.2f}"
    )

    return GeoTradeReward(
        total=round(total, 4),
        components=RewardComponents(
            accuracy=round((asset_score + direction_score) / 2, 4),
            risk_management=0.0,
            opportunity_capture=round(direction_score, 4),
            constraint_satisfaction=1.0,
            reasoning_quality=round(reasoning_score, 4),
        ),
        partial_progress=round(partial, 4),
        explanation=explanation,
        is_terminal=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TASK 2 — MEDIUM grader
# ══════════════════════════════════════════════════════════════════════════════

def grade_medium(action: GeoTradeAction, scenario: dict[str, Any]) -> GeoTradeReward:
    """Score a portfolio rebalancing action.

    Component weights:
        opportunity_capture (move alignment):  40%
        risk_management (weight distribution): 25%
        constraint_satisfaction:               20%
        reasoning quality:                     15%
    """
    gt = scenario["ground_truth"]
    optimal: dict[str, float] = gt["optimal_weights"]
    optimal_cash: float = gt.get("optimal_cash", 0.05)
    key_moves: dict[str, str] = gt["key_moves"]   # symbol → INCREASE/REDUCE/HOLD
    keywords: list[str] = gt.get("reasoning_keywords", [])

    initial: dict[str, float] = scenario["initial_portfolio"]
    weight_map = _weight_map(action.decisions)
    dir_map = _direction_map(action.decisions)

    # ── Constraint: weights sum ≤ 1, per-asset ≤ 0.45 ──────────────────────
    total_weight = sum(weight_map.values())
    constraint_ok = (total_weight <= 1.01) and all(w <= 0.45 for w in weight_map.values())
    constraint_score = 1.0 if constraint_ok else max(0.0, 1.0 - abs(total_weight - 1.0))

    # ── Move alignment: did agent move in the right direction? ───────────────
    move_hits = 0
    move_total = len(key_moves)
    for sym, expected_move in key_moves.items():
        init_w = initial.get(sym, 0.0)
        new_w = weight_map.get(sym, init_w)
        delta = new_w - init_w
        if expected_move == "INCREASE" and delta > 0.01:
            move_hits += 1
        elif expected_move == "REDUCE" and delta < -0.01:
            move_hits += 1
        elif expected_move == "HOLD" and abs(delta) <= 0.03:
            move_hits += 1
    move_score = move_hits / max(1, move_total)

    # ── Weight proximity to optimal ──────────────────────────────────────────
    weight_error = sum(
        abs(weight_map.get(sym, 0.0) - opt_w)
        for sym, opt_w in optimal.items()
    )
    max_possible_error = sum(abs(v) for v in optimal.values()) * 2  # worst case
    proximity_score = _clamp(1.0 - weight_error / max(1e-6, max_possible_error))

    # ── Risk management: diversification metric ──────────────────────────────
    weights_list = list(weight_map.values())
    if weights_list:
        herfindahl = sum(w ** 2 for w in weights_list)
        n = len(weights_list)
        min_hhi = 1.0 / n if n > 0 else 0.0
        diversification = _clamp(1.0 - (herfindahl - min_hhi) / max(1e-6, 1.0 - min_hhi))
    else:
        diversification = 0.0

    # ── Reasoning quality ─────────────────────────────────────────────────────
    reasoning_text = (action.reasoning or "") + " " + (action.primary_signal or "")
    reasoning_score = _reasoning_keywords_score(reasoning_text, keywords)

    # ── Weighted total ────────────────────────────────────────────────────────
    opportunity = 0.6 * move_score + 0.4 * proximity_score
    risk_mgmt = 0.5 * diversification + 0.5 * constraint_score

    total = _strict_unit(_clamp(
        0.40 * opportunity
        + 0.25 * risk_mgmt
        + 0.20 * constraint_score
        + 0.15 * reasoning_score
    ))
    partial = _clamp((move_score + proximity_score) / 2)

    explanation = (
        f"Move alignment: {move_score:.2f} ({move_hits}/{move_total}) | "
        f"Weight proximity: {proximity_score:.2f} | "
        f"Diversification: {diversification:.2f} | "
        f"Constraint: {'OK' if constraint_ok else 'VIOLATED'} | "
        f"Reasoning: {reasoning_score:.2f}"
    )

    return GeoTradeReward(
        total=round(total, 4),
        components=RewardComponents(
            accuracy=round(move_score, 4),
            risk_management=round(risk_mgmt, 4),
            opportunity_capture=round(opportunity, 4),
            constraint_satisfaction=round(constraint_score, 4),
            reasoning_quality=round(reasoning_score, 4),
        ),
        partial_progress=round(partial, 4),
        explanation=explanation,
        is_terminal=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TASK 3 — HARD grader (per-step and terminal)
# ══════════════════════════════════════════════════════════════════════════════

def grade_hard_step(
    action: GeoTradeAction,
    step_data: dict[str, Any],
    current_portfolio: dict[str, float],
) -> GeoTradeReward:
    """Grade a single step of the multi-step crisis episode.

    Per-step components:
        accuracy (direction vs optimal):   35%
        opportunity_capture:               35%
        risk_management:                   20%
        reasoning_quality:                 10%
    """
    optimal_action: dict[str, tuple[str, float]] = step_data["optimal_action"]
    price_moves: dict[str, float] = step_data["price_moves"]
    keywords: list[str] = step_data.get("reasoning_keywords", [])

    dir_map = _direction_map(action.decisions)
    weight_map = _weight_map(action.decisions)

    # ── Direction accuracy vs optimal ─────────────────────────────────────────
    direction_hits = 0
    total_assets = len(optimal_action)
    for sym, (opt_dir, _) in optimal_action.items():
        if dir_map.get(sym, "HOLD") == opt_dir:
            direction_hits += 1
    direction_score = direction_hits / max(1, total_assets)

    # ── Opportunity capture: did agent profit from actual price moves? ─────────
    # Positive if agent holds BUY on rising assets and SELL on falling
    opportunity_sum = 0.0
    opportunity_count = len(price_moves)
    for sym, move_pct in price_moves.items():
        direction = dir_map.get(sym, "HOLD")
        weight = weight_map.get(sym, current_portfolio.get(sym, 0.0))
        if direction == "BUY" and move_pct > 0:
            opportunity_sum += weight * move_pct * 10  # scaled contribution
        elif direction == "SELL" and move_pct < 0:
            opportunity_sum += weight * abs(move_pct) * 10
        elif direction == "HOLD":
            pass  # neutral
        else:
            opportunity_sum -= weight * abs(move_pct) * 5  # partial penalty
    opportunity_score = _clamp(0.5 + opportunity_sum)

    # ── Risk management: avoid over-concentration in volatile assets ──────────
    total_w = sum(weight_map.values())
    weight_ok = 0.85 <= total_w <= 1.01
    max_single = max((weight_map.get(s, 0.0) for s in optimal_action), default=0.0)
    concentration_ok = max_single <= 0.40
    risk_score = (0.5 if weight_ok else 0.0) + (0.5 if concentration_ok else 0.0)

    # ── Reasoning quality ─────────────────────────────────────────────────────
    reasoning_text = (action.reasoning or "") + " " + (action.primary_signal or "")
    reasoning_score = _reasoning_keywords_score(reasoning_text, keywords)

    total = _strict_unit(_clamp(
        0.35 * direction_score
        + 0.35 * opportunity_score
        + 0.20 * risk_score
        + 0.10 * reasoning_score
    ))
    partial = _clamp((direction_score + opportunity_score) / 2)

    explanation = (
        f"Step direction accuracy: {direction_score:.2f} ({direction_hits}/{total_assets}) | "
        f"Opportunity: {opportunity_score:.2f} | "
        f"Risk mgmt: {risk_score:.2f} | "
        f"Reasoning: {reasoning_score:.2f}"
    )

    return GeoTradeReward(
        total=round(total, 4),
        components=RewardComponents(
            accuracy=round(direction_score, 4),
            risk_management=round(risk_score, 4),
            opportunity_capture=round(opportunity_score, 4),
            constraint_satisfaction=round(1.0 if weight_ok else 0.0, 4),
            reasoning_quality=round(reasoning_score, 4),
        ),
        partial_progress=round(partial, 4),
        explanation=explanation,
        is_terminal=False,
    )


def grade_hard_terminal(
    step_rewards: list[GeoTradeReward],
    scenario: dict[str, Any],
    portfolio_history: list[dict[str, float]],
    price_history: list[dict[str, float]],
) -> GeoTradeReward:
    """Compute terminal reward for the full episode.

    Terminal components (override per-step):
        prediction_accuracy: mean per-step direction scores
        pnl_performance:     simulated PnL vs benchmark
        risk_management:     max drawdown vs allowed threshold
    """
    scoring = scenario["scoring"]
    benchmark_pnl: float = scoring["benchmark_pnl"]
    max_allowed_dd: float = scoring["max_allowed_drawdown"]
    weights: dict[str, float] = scoring["weights"]

    # ── Mean per-step accuracy ────────────────────────────────────────────────
    mean_accuracy = (
        sum(r.components.accuracy for r in step_rewards) / len(step_rewards)
        if step_rewards else 0.0
    )

    # ── Simulated PnL ─────────────────────────────────────────────────────────
    portfolio_value = 1.0
    peak_value = 1.0
    max_drawdown = 0.0
    pnl_per_step: list[float] = []

    for i, (pf, prices) in enumerate(zip(portfolio_history, price_history)):
        step_return = sum(pf.get(sym, 0.0) * prices.get(sym, 0.0) for sym in pf)
        portfolio_value *= (1.0 + step_return)
        peak_value = max(peak_value, portfolio_value)
        drawdown = (peak_value - portfolio_value) / peak_value
        max_drawdown = max(max_drawdown, drawdown)
        pnl_per_step.append(step_return)

    final_pnl = portfolio_value - 1.0  # total return over episode

    # Score PnL vs benchmark (linear scale, capped)
    pnl_score = _clamp(final_pnl / max(1e-6, benchmark_pnl))

    # Score drawdown: 1.0 if under limit, degrades linearly above
    if max_drawdown <= max_allowed_dd:
        dd_score = 1.0
    else:
        excess = max_drawdown - max_allowed_dd
        dd_score = _clamp(1.0 - excess / max_allowed_dd)

    # ── Weighted terminal total ───────────────────────────────────────────────
    total = _strict_unit(_clamp(
        weights["prediction_accuracy"] * mean_accuracy
        + weights["pnl_performance"] * pnl_score
        + weights["risk_management"] * dd_score
    ))

    explanation = (
        f"Mean step accuracy: {mean_accuracy:.2f} | "
        f"Portfolio PnL: {final_pnl:.3f} vs benchmark {benchmark_pnl:.3f} (score {pnl_score:.2f}) | "
        f"Max drawdown: {max_drawdown:.3f} (limit {max_allowed_dd}) (score {dd_score:.2f}) | "
        f"TERMINAL SCORE: {total:.4f}"
    )

    return GeoTradeReward(
        total=round(total, 4),
        components=RewardComponents(
            accuracy=round(mean_accuracy, 4),
            risk_management=round(dd_score, 4),
            opportunity_capture=round(pnl_score, 4),
            constraint_satisfaction=1.0,
            reasoning_quality=0.0,
        ),
        partial_progress=1.0,
        explanation=explanation,
        is_terminal=True,
    )
