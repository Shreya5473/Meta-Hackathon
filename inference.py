"""GeoTrade OpenEnv — Baseline Inference Script
================================================
STDOUT FORMAT (required by hackathon validator):

    [START] task=<task_name> env=geotrade model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>

Environment variables:
    API_BASE_URL   OpenAI-compatible API endpoint
    MODEL_NAME     Model identifier
    HF_TOKEN       API key (also accepted as OPENAI_API_KEY)

Runtime: < 15 minutes on 2 vCPU / 8 GB machine.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Optional

from openai import OpenAI

from openenv.environment import GeoTradeEnv
from openenv.models import AssetDecision, GeoTradeAction, GeoTradeObservation

# ── Env vars ──────────────────────────────────────────────────────────────────

API_BASE_URL: str = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME: str = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN: str = os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY", "")
ENV_NAME: str = "geotrade"

if not HF_TOKEN:
    print("[END] success=false steps=0 rewards=", flush=True)
    print("ERROR: HF_TOKEN (or OPENAI_API_KEY) is not set.", file=sys.stderr)
    sys.exit(1)

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

# ── Logging helpers (exact format required by validator) ──────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: list[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}", flush=True)


# ── System prompts ────────────────────────────────────────────────────────────

_SYSTEM_PROMPTS = {
    "task_easy": (
        "You are GeoTradeBot, an expert geopolitical trading analyst. "
        "Analyse the geopolitical event and market data provided, then identify the top-3 most "
        "impacted assets and whether to BUY, SELL, or HOLD each. "
        "Respond with valid JSON only — no markdown, no explanation outside the JSON."
        '\n\nJSON schema:\n{"decisions":[{"symbol":"XAUUSD","direction":"BUY","weight":0.20,"confidence":0.85}],'
        '"primary_signal":"one sentence","reasoning":"chain of thought"}'
    ),
    "task_medium": (
        "You are GeoTradeBot, an expert portfolio risk manager. "
        "Given the geopolitical scenario and current portfolio, rebalance weights to hedge risk "
        "and capture opportunities. Weights must sum to ≤ 1.0; no asset may exceed 0.45. "
        "Respond with valid JSON only."
        '\n\nJSON schema:\n{"decisions":[{"symbol":"XAUUSD","direction":"BUY","weight":0.25,"confidence":0.80}],'
        '"primary_signal":"one sentence","reasoning":"explain each move"}'
    ),
    "task_hard": (
        "You are GeoTradeBot managing a portfolio through an evolving geopolitical crisis. "
        "At each step update your positions based on the latest intelligence. "
        "Weights must sum to ≤ 1.0; no asset may exceed 0.45. "
        "Respond with valid JSON only."
        '\n\nJSON schema:\n{"decisions":[{"symbol":"WTI","direction":"BUY","weight":0.25,"confidence":0.80}],'
        '"primary_signal":"crisis trajectory","reasoning":"step-by-step reasoning"}'
    ),
}


# ── Observation → text ────────────────────────────────────────────────────────

def obs_to_text(obs: GeoTradeObservation) -> str:
    ctx = obs.geopolitical_context
    lines = [
        f"[GeoTrade Environment | {obs.task_id} | Step {obs.step + 1}/{obs.max_steps}]",
        f"Scenario: {obs.scenario_id}",
        "",
        "GEOPOLITICAL CONTEXT",
        f"Headline:    {ctx.headline}",
        f"Region:      {ctx.region}  |  Severity: {ctx.severity}  |  GTI: {ctx.gti_score:.1f} ({ctx.gti_delta:+.1f})",
        f"Categories:  {', '.join(ctx.categories)}",
        f"Description: {ctx.description}",
        "Recent news: " + " | ".join(ctx.news_headlines),
        "",
        "MARKET SNAPSHOT",
        f"{'Asset':<10} {'Class':<12} {'Price':>10} {'GTI-Sens':>9}",
    ]
    for sym, snap in obs.market_snapshot.items():
        lines.append(f"{snap.symbol:<10} {snap.asset_class:<12} {snap.price:>10.4f} {snap.gti_sensitivity:>9.2f}")

    pf = obs.portfolio
    lines += ["", "CURRENT PORTFOLIO"]
    lines.append(f"Cash: {pf.cash_pct:.1%}")
    for sym, w in pf.weights.items():
        lines.append(f"  {sym}: {w:.1%}")

    lines += ["", "YOUR TASK", obs.prompt, "", f"Available assets: {', '.join(obs.available_assets)}"]
    return "\n".join(lines)


# ── LLM call ──────────────────────────────────────────────────────────────────

def call_llm(task_id: str, obs_text: str, history: list[dict]) -> dict[str, Any]:
    messages = [{"role": "system", "content": _SYSTEM_PROMPTS[task_id]}]
    messages.extend(history)
    messages.append({"role": "user", "content": obs_text})

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as exc:
        return {"decisions": [], "primary_signal": "", "reasoning": str(exc)}


# ── Action builder ────────────────────────────────────────────────────────────

def build_action(task_id: str, parsed: dict, obs: GeoTradeObservation) -> GeoTradeAction:
    decisions: list[AssetDecision] = []
    seen: set[str] = set()

    for d in parsed.get("decisions", []):
        sym = d.get("symbol", "")
        if sym not in obs.market_snapshot or sym in seen:
            continue
        seen.add(sym)
        try:
            decisions.append(AssetDecision(
                symbol=sym,
                direction=d.get("direction", "HOLD"),
                weight=float(d.get("weight", 0.0)),
                confidence=float(d.get("confidence", 0.5)),
            ))
        except Exception:
            continue

    for sym in obs.available_assets:
        if sym not in seen:
            decisions.append(AssetDecision(
                symbol=sym, direction="HOLD",
                weight=obs.portfolio.weights.get(sym, 0.0), confidence=0.3,
            ))

    return GeoTradeAction(
        task_id=task_id,
        decisions=decisions,
        primary_signal=str(parsed.get("primary_signal", "")),
        reasoning=str(parsed.get("reasoning", "")),
    )


def action_to_str(action: GeoTradeAction) -> str:
    """Compact single-line representation for [STEP] line."""
    buys  = [f"{d.symbol}:BUY@{d.weight:.2f}"  for d in action.decisions if d.direction == "BUY"]
    sells = [f"{d.symbol}:SELL@{d.weight:.2f}" for d in action.decisions if d.direction == "SELL"]
    parts = buys + sells
    signal = action.primary_signal[:60].replace("\n", " ") if action.primary_signal else ""
    return f"[{','.join(parts)}] signal='{signal}'" if parts else f"HOLD signal='{signal}'"


# ── Single episode runner ─────────────────────────────────────────────────────

def run_episode(task_id: str, scenario_idx: int) -> None:
    scenario_tag = f"{task_id}_{scenario_idx + 1:02d}"
    env = GeoTradeEnv(task_id=task_id, scenario_idx=scenario_idx)
    obs = env.reset(seed=42)

    rewards: list[float] = []
    steps_taken = 0
    success = False
    history: list[dict] = []

    log_start(task=scenario_tag, env=ENV_NAME, model=MODEL_NAME)

    try:
        for step_num in range(1, obs.max_steps + 1):
            obs_text = obs_to_text(obs)
            parsed = call_llm(task_id, obs_text, history)
            action = build_action(task_id, parsed, obs)
            action_str = action_to_str(action)

            result = env.step(action)
            reward = result.reward.total
            done = result.done
            error_msg = None if result.reward.total > 0 else result.reward.explanation[:80]

            rewards.append(reward)
            steps_taken = step_num

            log_step(step=step_num, action=action_str, reward=reward, done=done, error=error_msg)

            # Add to conversation history for multi-step context
            history.append({"role": "user", "content": obs_text})
            history.append({"role": "assistant", "content": json.dumps(parsed)})

            obs = result.observation
            if done:
                success = reward >= 0.4
                break

    except Exception as exc:
        error_str = str(exc)[:100]
        log_step(step=steps_taken + 1, action="ERROR", reward=0.0, done=True, error=error_str)
        success = False

    log_end(success=success, steps=steps_taken, rewards=rewards)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    start = time.time()

    # Task definitions: (task_id, num_scenarios)
    tasks = [
        ("task_easy",   5),
        ("task_medium", 3),
        ("task_hard",   2),
    ]

    all_rewards: list[float] = []

    for task_id, n_scenarios in tasks:
        for scenario_idx in range(n_scenarios):
            run_episode(task_id=task_id, scenario_idx=scenario_idx)

    elapsed = time.time() - start
    print(f"# Total runtime: {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
