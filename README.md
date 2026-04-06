---
title: GeoTrade OpenEnv
emoji: 🌍
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - geopolitics
  - trading
  - finance
  - agent-evaluation
license: mit
---

# GeoTrade OpenEnv

**An AI agent evaluation environment for geopolitical financial market analysis.**

GeoTrade OpenEnv simulates the real-world task of analysing geopolitical events and making trading decisions across asset classes. The environment is grounded in actual geo-financial correlations — how events like oil supply disruptions, military escalations, and trade wars ripple through currencies, commodities, equities, and bonds.

This environment is built on top of the GeoTrade AI system, which uses a Geopolitical Tension Index (GTI), NLP-based event classification, and market impact modelling to produce trading signals.

> **Not financial advice — evaluation environment only.**

---

## Environment Description

Geopolitical events move markets in predictable but complex ways. An expert trader monitors breaking news, assesses crisis severity, and rapidly repositions portfolios. This requires:

1. **Domain knowledge** — knowing which assets are sensitive to which geopolitical events
2. **Causal reasoning** — tracing multi-hop impact chains (e.g. Iran conflict → oil supply disruption → inflation → central bank response → equity repricing)
3. **Risk management** — hedging against uncertainty while capturing directional opportunities
4. **Temporal adaptation** — updating decisions as crises evolve over days or weeks

GeoTrade OpenEnv tests all four capabilities across three tasks of increasing difficulty.

---

## Tasks

### Task 1: Geopolitical Signal Identification (`task_easy`)
**Difficulty:** Easy | **Steps:** 1 | **Scenarios:** 5

Given a geopolitical event description and a 5-asset market snapshot, identify the **top 3 most impacted assets** and their direction (BUY / SELL / HOLD).

**Example scenario:** *"Russia halts all natural gas pipeline exports to Europe"*
Expected: NATGAS (BUY), EURUSD (SELL), XAUUSD (BUY)

**Scoring:**
```
0.45 × asset_identification_F1
+ 0.45 × direction_accuracy
+ 0.10 × reasoning_quality
```

---

### Task 2: Portfolio Geopolitical Hedging (`task_medium`)
**Difficulty:** Medium | **Steps:** 1 | **Scenarios:** 3

Given a **6-asset portfolio** and a geopolitical scenario with crisis intensity, rebalance portfolio weights to hedge geopolitical risk while capturing opportunities. Weights must sum to ≤ 1.0; no single asset may exceed 45%.

**Example scenario:** *"Iran-Israel direct military exchange; oil facilities targeted"*
Expected moves: Reduce SPX, increase XAUUSD + WTI + USDJPY + NATGAS, reduce EURUSD.

**Scoring:**
```
0.40 × opportunity_capture (move alignment + weight proximity)
+ 0.25 × risk_management (diversification)
+ 0.20 × constraint_satisfaction (weights valid)
+ 0.15 × reasoning_quality
```

---

### Task 3: Crisis Cascade Portfolio Management (`task_hard`)
**Difficulty:** Hard | **Steps:** 5 | **Scenarios:** 2

Manage a 6-asset portfolio through a **5-step evolving geopolitical crisis** — from initial warning signs through peak escalation to de-escalation and ceasefire. The agent receives updated intelligence and market data at each step and must adapt its portfolio accordingly.

**Example scenario:** *Middle East Escalation & Ceasefire* (IAEA alert → Israeli strikes → Hormuz blockade → mine-clearing → Muscat ceasefire)

**Terminal scoring:**
```
0.35 × mean_step_prediction_accuracy
+ 0.40 × simulated_PnL_vs_benchmark
+ 0.25 × max_drawdown_control
```

---

## Observation Space

Each observation contains:

| Field | Type | Description |
|---|---|---|
| `task_id` | string | `task_easy`, `task_medium`, or `task_hard` |
| `scenario_id` | string | Unique scenario identifier |
| `step` | int | Current step (0-indexed) |
| `max_steps` | int | Total steps in episode |
| `geopolitical_context.gti_score` | float [0–100] | Geopolitical Tension Index |
| `geopolitical_context.severity` | enum | `low`, `medium`, `high`, `critical` |
| `geopolitical_context.region` | string | Affected geopolitical region |
| `geopolitical_context.categories` | list[str] | Event types (e.g. `military_escalation`) |
| `geopolitical_context.headline` | string | Short event headline |
| `geopolitical_context.description` | string | Full event description |
| `geopolitical_context.news_headlines` | list[str] | Related news items |
| `market_snapshot[symbol].price` | float | Current asset price |
| `market_snapshot[symbol].asset_class` | enum | `forex`, `commodity`, `equity`, `bond` |
| `market_snapshot[symbol].volatility_regime` | enum | `LOW`, `NORMAL`, `HIGH`, `EXTREME` |
| `market_snapshot[symbol].gti_sensitivity` | float [0–1] | How responsive asset is to geopolitical stress |
| `portfolio.weights` | dict | Current portfolio weights by symbol |
| `portfolio.cash_pct` | float | Cash allocation |
| `portfolio.unrealized_pnl` | float | Cumulative PnL |
| `prompt` | string | Natural-language description of what to do |

---

## Action Space

| Field | Type | Description |
|---|---|---|
| `task_id` | string | Must match environment task |
| `decisions[].symbol` | string | Asset symbol (e.g. `XAUUSD`) |
| `decisions[].direction` | enum | `BUY`, `SELL`, or `HOLD` |
| `decisions[].weight` | float [0–1] | Target portfolio weight |
| `decisions[].confidence` | float [0–1] | Agent's confidence in this decision |
| `primary_signal` | string | One-sentence geopolitical interpretation |
| `reasoning` | string | Full chain-of-thought explanation |

**Constraints:** `sum(weights) ≤ 1.0`, `max(weight) ≤ 0.45`

---

## Reward Function

All rewards are in **[0.0, 1.0]**. Partial-progress signals are provided at every step — reward is never purely sparse.

| Task | Partial signal | Terminal signal |
|---|---|---|
| Easy | Immediate after single step | Same |
| Medium | Immediate after single step | Same |
| Hard | Per-step direction accuracy | PnL + drawdown scoring |

**Penalties for undesirable behaviour:**
- Violating weight constraints → `constraint_satisfaction = 0`
- Over-concentrating (single asset > 45%) → `risk_management` penalised
- Wrong direction on highly volatile assets → `opportunity_capture` negative contribution

---

## Setup & Usage

### Local Python (no Docker)

```bash
# Install lean dependencies
pip install -r requirements_openenv.txt

# Set environment variables
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export HF_TOKEN=sk-your-key-here

# Run the baseline inference script
python inference.py

# Start the HTTP server
python -m uvicorn openenv.server:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
docker build -t geotrade-openenv .

docker run -p 7860:7860 \
  -e API_BASE_URL=https://api.openai.com/v1 \
  -e MODEL_NAME=gpt-4o-mini \
  -e HF_TOKEN=sk-your-key-here \
  geotrade-openenv
```

### Using the Python API directly

```python
from openenv import GeoTradeEnv, GeoTradeAction
from openenv.models import AssetDecision

# Create and reset environment
env = GeoTradeEnv(task_id="task_easy")
obs = env.reset(seed=42)
print(obs.geopolitical_context.headline)

# Submit an action
action = GeoTradeAction(
    task_id="task_easy",
    decisions=[
        AssetDecision(symbol="XAUUSD", direction="BUY",  weight=0.20, confidence=0.85),
        AssetDecision(symbol="NATGAS", direction="BUY",  weight=0.15, confidence=0.80),
        AssetDecision(symbol="EURUSD", direction="SELL", weight=0.10, confidence=0.75),
    ],
    primary_signal="Gas supply shock → energy spike, EUR weakness, gold safe-haven bid.",
    reasoning="Russia's gas halt creates immediate supply scarcity in Europe...",
)
result = env.step(action)
print(f"Score: {result.reward.total:.4f}")
print(result.reward.explanation)
```

### HTTP API (when server is running)

```bash
# Reset — start a new episode
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task_easy", "seed": 42}'

# Step — submit action (use session_id from reset response)
curl -X POST "http://localhost:7860/step?session_id=<SESSION_ID>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task_easy",
    "decisions": [
      {"symbol": "XAUUSD", "direction": "BUY", "weight": 0.20, "confidence": 0.85}
    ],
    "primary_signal": "Safe haven bid on energy crisis",
    "reasoning": "Gold typically surges during European energy crises..."
  }'

# State — inspect internal state
curl "http://localhost:7860/state?session_id=<SESSION_ID>"

# List tasks
curl http://localhost:7860/tasks
```

---

## Baseline Scores

Baseline scores produced by `gpt-4o-mini` (temperature=0.2):

| Task | Scenarios | Mean Score | Score Range |
|---|---|---|---|
| `task_easy` | 5 | ~0.62 | 0.40–0.82 |
| `task_medium` | 3 | ~0.48 | 0.30–0.65 |
| `task_hard` | 2 | ~0.35 | 0.22–0.48 |
| **Overall** | **10** | **~0.48** | |

> Frontier models (GPT-4o, Claude Opus) are expected to score 15–25% higher. Task 3 is designed to challenge even the best models.

---

## Project Structure

```
geotrade/
├── openenv/
│   ├── __init__.py          # Public exports
│   ├── models.py            # Pydantic Observation/Action/Reward models
│   ├── scenarios.py         # Scenario datasets (5 easy, 3 medium, 2 hard)
│   ├── graders.py           # Deterministic task graders
│   ├── environment.py       # GeoTradeEnv (reset/step/state)
│   └── server.py            # FastAPI HTTP server for HF Spaces
├── app/                     # Full GeoTrade AI backend (GTI engine, ML models)
├── openenv.yaml             # OpenEnv spec metadata
├── inference.py             # Baseline inference script (place in root per spec)
├── Dockerfile               # HF Spaces / container deployment
├── requirements_openenv.txt # Lean dependency list for the env only
└── README.md                # This file
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_BASE_URL` | Yes | OpenAI-compatible API base URL |
| `MODEL_NAME` | Yes | Model identifier (e.g. `gpt-4o-mini`) |
| `HF_TOKEN` | Yes | Hugging Face / OpenAI API key |

---

## Why GeoTrade?

Geopolitical trading is a genuinely hard real-world task that:
- Requires deep cross-domain knowledge (geopolitics + financial markets)
- Involves multi-hop causal reasoning across asset classes
- Demands temporal coherence over evolving crisis episodes
- Has clear, measurable ground truth (directional market impact)
- Is directly useful for evaluating LLM agents in finance

No existing OpenEnv environment covers this domain. GeoTrade fills that gap.

---

## Tech Stack

- **Python 3.11** + **FastAPI** + **Pydantic v2**
- **Environment:** Fully self-contained, no external APIs required
- **Inference:** OpenAI client with JSON-mode for structured outputs
- **Deployment:** Docker + Hugging Face Spaces (port 7860)

---

*Disclaimer: GeoTrade OpenEnv is an evaluation environment. All scenarios are synthetic and calibrated to historical geo-financial patterns. Not financial advice.*
