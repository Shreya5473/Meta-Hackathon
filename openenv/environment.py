"""GeoTrade OpenEnv — main environment.

Implements the OpenEnv spec:
    reset(seed) -> GeoTradeObservation
    step(action) -> StepResult
    state()      -> EnvironmentState

The environment is fully self-contained — no external APIs required.
All scenario data is drawn from openenv/scenarios.py.
"""
from __future__ import annotations

import copy
from typing import Any, Literal

from openenv.graders import grade_easy, grade_hard_step, grade_hard_terminal, grade_medium
from openenv.models import (
    AssetSnapshot,
    EnvironmentState,
    GeopoliticalContext,
    GeoTradeAction,
    GeoTradeObservation,
    GeoTradeReward,
    PortfolioState,
    RewardComponents,
    StepResult,
)
from openenv.scenarios import (
    EASY_SCENARIOS,
    HARD_SCENARIOS,
    MEDIUM_SCENARIOS,
)

TaskID = Literal["task_easy", "task_medium", "task_hard"]

_TASK_PROMPTS: dict[str, str] = {
    "task_easy": (
        "You are a geopolitical trading analyst. Given the geopolitical event described above "
        "and the current market snapshot, identify the top 3 most impacted assets and state "
        "whether to BUY, SELL, or HOLD each one. Provide a concise reasoning chain."
    ),
    "task_medium": (
        "You are a portfolio risk manager. Given the geopolitical scenario and your current "
        "portfolio, rebalance the portfolio weights to hedge geopolitical risk while capturing "
        "opportunities. Weights must sum to ≤ 1.0, with the remainder in cash. "
        "No single asset may exceed 45% of the portfolio."
    ),
    "task_hard": (
        "You are managing a multi-asset portfolio through an evolving geopolitical crisis. "
        "At each step you receive updated intelligence and market data. "
        "Adjust your portfolio weights and trading decisions to maximise risk-adjusted returns "
        "while controlling drawdown. Explain your reasoning at each step."
    ),
}


class GeoTradeEnv:
    """GeoTrade geopolitical trading environment.

    Simulates real-world geopolitical trading tasks for agent evaluation.
    Three tasks of increasing difficulty: Easy → Medium → Hard.

    Usage:
        env = GeoTradeEnv(task_id="task_easy")
        obs = env.reset(seed=42)
        result = env.step(action)
    """

    def __init__(self, task_id: TaskID = "task_easy", scenario_idx: int = 0) -> None:
        if task_id not in ("task_easy", "task_medium", "task_hard"):
            raise ValueError(f"Unknown task_id: {task_id}")
        self.task_id: TaskID = task_id
        self.scenario_idx: int = scenario_idx

        # Mutable episode state
        self._step: int = 0
        self._done: bool = True
        self._seed: int = 42
        self._scenario: dict[str, Any] = {}
        self._portfolio: dict[str, float] = {}
        self._cash: float = 0.0
        self._cumulative_reward: float = 0.0
        self._history: list[dict[str, Any]] = []

        # Hard-task extras
        self._step_rewards: list[GeoTradeReward] = []
        self._portfolio_history: list[dict[str, float]] = []
        self._price_history: list[dict[str, float]] = []

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def max_steps(self) -> int:
        if self.task_id == "task_hard":
            return len(self._scenario.get("steps", []))
        return 1

    # ── Public API ────────────────────────────────────────────────────────────

    def reset(self, seed: int = 42) -> GeoTradeObservation:
        """Initialise the environment and return the first observation."""
        self._seed = seed
        self._step = 0
        self._done = False
        self._cumulative_reward = 0.0
        self._history = []
        self._step_rewards = []
        self._portfolio_history = []
        self._price_history = []

        # Select scenario deterministically from seed
        if self.task_id == "task_easy":
            pool = EASY_SCENARIOS
        elif self.task_id == "task_medium":
            pool = MEDIUM_SCENARIOS
        else:
            pool = HARD_SCENARIOS

        idx = (seed + self.scenario_idx) % len(pool)
        self._scenario = copy.deepcopy(pool[idx])

        # Initialise portfolio
        if self.task_id == "task_hard":
            self._portfolio = dict(self._scenario["initial_portfolio"])
            self._cash = self._scenario.get("initial_cash", 0.05)
        elif self.task_id == "task_medium":
            self._portfolio = dict(self._scenario["initial_portfolio"])
            self._cash = self._scenario.get("initial_cash", 0.10)
        else:
            self._portfolio = {}
            self._cash = 1.0

        return self._build_observation()

    def step(self, action: GeoTradeAction) -> StepResult:
        """Process the agent's action and return the next observation + reward."""
        if self._done:
            raise RuntimeError("Episode is done. Call reset() before step().")

        if action.task_id != self.task_id:
            raise ValueError(
                f"Action task_id '{action.task_id}' does not match env task_id '{self.task_id}'"
            )

        # Compute reward
        if self.task_id == "task_easy":
            reward = grade_easy(action, self._scenario)
            self._done = True

        elif self.task_id == "task_medium":
            reward = grade_medium(action, self._scenario)
            # Update portfolio to agent's declared weights
            self._portfolio = {d.symbol: d.weight for d in action.decisions}
            self._cash = max(0.0, 1.0 - sum(self._portfolio.values()))
            self._done = True

        else:  # task_hard
            step_data = self._scenario["steps"][self._step]
            reward = grade_hard_step(action, step_data, self._portfolio)
            self._step_rewards.append(reward)

            # Update portfolio: apply agent weights, then simulate price moves
            new_weights = {d.symbol: d.weight for d in action.decisions}
            self._portfolio_history.append(dict(new_weights))

            price_moves = step_data["price_moves"]
            self._price_history.append(dict(price_moves))

            # Apply price moves to portfolio
            for sym in list(new_weights.keys()):
                move = price_moves.get(sym, 0.0)
                new_weights[sym] = new_weights[sym] * (1.0 + move)

            total_w = sum(new_weights.values())
            if total_w > 0:
                self._portfolio = {s: w / total_w for s, w in new_weights.items()}
            else:
                self._portfolio = new_weights

            self._cash = max(0.0, 1.0 - sum(new_weights.values()))
            self._step += 1

            if self._step >= len(self._scenario["steps"]):
                # Terminal: compute episode-level reward
                terminal_reward = grade_hard_terminal(
                    self._step_rewards,
                    self._scenario,
                    self._portfolio_history,
                    self._price_history,
                )
                terminal_reward.is_terminal = True
                self._cumulative_reward += terminal_reward.total
                self._done = True
                self._history.append({"step": self._step - 1, "action": action.model_dump(), "reward": reward.model_dump()})
                return StepResult(
                    observation=self._build_observation(),
                    reward=terminal_reward,
                    done=True,
                    info={"step_reward": reward.model_dump(), "terminal_reward": terminal_reward.model_dump()},
                )

        self._cumulative_reward += reward.total
        self._history.append({"step": self._step, "action": action.model_dump(), "reward": reward.model_dump()})
        if self.task_id != "task_hard":
            pass
        else:
            pass  # step was already incremented above

        return StepResult(
            observation=self._build_observation(),
            reward=reward,
            done=self._done,
            info={},
        )

    def state(self) -> EnvironmentState:
        """Return a snapshot of the internal state (for debugging / logging)."""
        return EnvironmentState(
            task_id=self.task_id,
            scenario_id=self._scenario.get("id", ""),
            step=self._step,
            done=self._done,
            cumulative_reward=round(self._cumulative_reward, 6),
            history=self._history,
            seed=self._seed,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_observation(self) -> GeoTradeObservation:
        """Construct the observation for the current step."""
        scenario = self._scenario

        if self.task_id == "task_hard":
            step_idx = min(self._step, len(scenario["steps"]) - 1)
            step_data = scenario["steps"][step_idx]
            geo_ctx_raw = step_data["geopolitical_context"]
            snap_symbols: list[str] = scenario["assets"]
            # Compute current prices based on accumulated moves
            base_prices = {sym: 1.0 for sym in snap_symbols}  # normalised
            market_snap = self._build_snapshot(snap_symbols, base_prices, geo_ctx_raw)
        else:
            geo_ctx_raw = scenario["geopolitical_context"]
            snap_raw = scenario["market_snapshot"]
            market_snap = {
                sym: AssetSnapshot(**data)
                for sym, data in snap_raw.items()
            }

        geo_ctx = GeopoliticalContext(**geo_ctx_raw)

        portfolio_state = PortfolioState(
            weights=dict(self._portfolio),
            cash_pct=self._cash,
            total_value=1.0,
            unrealized_pnl=self._cumulative_reward,
        )

        available = list(market_snap.keys())
        prompt = _TASK_PROMPTS[self.task_id]
        if self.task_id == "task_hard" and not self._done:
            step_idx = min(self._step, len(scenario["steps"]) - 1)
            step_data = scenario["steps"][step_idx]
            prompt = (
                f"[Step {self._step + 1}/{self.max_steps}] "
                + _TASK_PROMPTS["task_hard"]
            )

        return GeoTradeObservation(
            task_id=self.task_id,
            scenario_id=scenario["id"],
            step=self._step,
            max_steps=self.max_steps,
            geopolitical_context=geo_ctx,
            market_snapshot=market_snap,
            portfolio=portfolio_state,
            prompt=prompt,
            available_assets=available,
            info={"scenario_name": scenario.get("name", scenario["id"])},
        )

    @staticmethod
    def _build_snapshot(
        symbols: list[str],
        prices: dict[str, float],
        geo_ctx: dict,
    ) -> dict[str, AssetSnapshot]:
        from openenv.scenarios import ASSET_META
        snap: dict[str, AssetSnapshot] = {}
        for sym in symbols:
            meta = ASSET_META.get(sym, {"name": sym, "asset_class": "commodity", "gti_sensitivity": 0.5})
            snap[sym] = AssetSnapshot(
                symbol=sym,
                name=meta["name"],
                asset_class=meta["asset_class"],
                price=prices.get(sym, 1.0),
                daily_change_pct=0.0,
                volatility_regime="NORMAL",
                gti_sensitivity=meta["gti_sensitivity"],
            )
        return snap


# ── Convenience factory ───────────────────────────────────────────────────────

def make_env(task_id: TaskID = "task_easy", scenario_idx: int = 0) -> GeoTradeEnv:
    """Create a ready-to-use environment instance."""
    return GeoTradeEnv(task_id=task_id, scenario_idx=scenario_idx)
