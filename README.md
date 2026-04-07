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


> **Not financial advice — evaluation environment only.**


---


## Table of Contents


- [Motivation](#motivation)
- [OpenEnv Compliance](#openenv-compliance)
- [Tasks](#tasks)
- [Observation Space](#observation-space)
- [Action Space](#action-space)
- [Reward Function](#reward-function)
- [Setup & Usage](#setup--usage)
- [Deployment](#deployment)
- [Baseline Scores](#baseline-scores)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Tech Stack](#tech-stack)


---


## Motivation


Geopolitical events move markets in predictable but complex ways. An expert trader monitors breaking news, assesses crisis severity, and rapidly repositions portfolios. This requires:


1. **Domain knowledge** — knowing which assets are sensitive to which geopolitical events
2. **Causal reasoning** — tracing multi-hop impact chains (e.g. Iran conflict → oil supply disruption → inflation → central bank response → equity repricing)
3. **Risk management** — hedging against uncertainty while capturing directional opportunities
4. **Temporal adaptation** — updating decisions as crises evolve over days or weeks


Geopolitical trading is a genuinely hard real-world task that:


- Requires deep cross-domain knowledge (geopolitics + financial markets)
- Involves multi-hop causal reasoning across asset classes
- Demands temporal coherence over evolving crisis episodes
- Has clear, measurable ground truth (directional market impact)
- Is directly useful for evaluating LLM agents in finance


No existing OpenEnv environment covers this domain. GeoTrade fills that gap.


---


## OpenEnv Compliance


GeoTrade fully implements the OpenEnv specification:


| Requirement | Implementation |
|---|---|
| Typed `Observation` model | `GeoTradeObservation` — Pydantic v2, see `openenv/models.py` |
| Typed `Action` model | `GeoTradeAction` — Pydantic v2, see `openenv/models.py` |
| Typed `Reward` model | `GeoTradeReward` — Pydantic v2 with decomposed components |
| `reset() → observation` | `GeoTradeEnv.reset(seed?)` in `openenv/environment.py` |
| `step(action) → (obs, reward, done, info)` | `GeoTradeEnv.step(action)` in `openenv/environment.py` |
| `state() → current state` | `GeoTradeEnv.state()` in `openenv/environment.py` |
| `openenv.yaml` metadata | Root-level `openenv.yaml` |
| HTTP server endpoints | `/reset`, `/step`, `/state`, `/tasks`, `/health` via FastAPI |
| Baseline inference script | `inference.py` — reads credentials from `HF_TOKEN` env var |
| Hugging Face Space deployment | Docker SDK, tagged `openenv`, port 7860 |


Validate the environment with:


```bash
openenv validate
```


---


## Tasks


GeoTrade provides three tasks of increasing difficulty, each with a programmatic grader that returns a deterministic score in **[0.0, 1.0]**.


---


### Task 1: Geopolitical Signal Identification (`task_easy`)


**Difficulty:** Easy | **Steps:** 1 | **Scenarios:** 5


Given a geopolitical event description and a 5-asset market snapshot, identify the **top 3 most impacted assets** and their direction (BUY / SELL / HOLD).


**Example scenario:** *"Russia halts all natural gas pipeline exports to Europe"*
Expected: NATGAS (BUY), EURUSD (SELL), XAUUSD (BUY)


**Grading (deterministic):**


```
0.45 × asset_identification_F1
+ 0.45 × direction_accuracy
+ 0.10 × reasoning_quality
```


- `asset_identification_F1` — precision/recall against the ground-truth asset set
- `direction_accuracy` — fraction of matched assets with the correct BUY/SELL/HOLD
- `reasoning_quality` — keyword overlap score against a reference explanation


**Expected score range:** 0.30 – 0.80


---


### Task 2: Portfolio Geopolitical Hedging (`task_medium`)


**Difficulty:** Medium | **Steps:** 1 | **Scenarios:** 3


Given a **6-asset portfolio** and a geopolitical scenario with crisis intensity, rebalance portfolio weights to hedge geopolitical risk while capturing opportunities. Weights must sum to ≤ 1.0; no single asset may exceed 45%.


**Example scenario:** *"Iran-Israel direct military exchange; oil facilities targeted"*
Expected moves: Reduce SPX, increase XAUUSD + WTI + USDJPY + NATGAS, reduce EURUSD.


**Grading (deterministic):**


```
0.40 × opportunity_capture   (move alignment + weight proximity to optimal)
+ 0.25 × risk_management     (diversification score)
+ 0.20 × constraint_satisfaction (portfolio weights valid)
+ 0.15 × reasoning_quality
```


**Expected score range:** 0.20 – 0.70


---


### Task 3: Crisis Cascade Portfolio Management (`task_hard`)


**Difficulty:** Hard | **Steps:** 5 | **Scenarios:** 2


Manage a 6-asset portfolio through a **5-step evolving geopolitical crisis** — from initial warning signs through peak escalation to de-escalation and ceasefire. The agent receives updated intelligence and market data at each step and must adapt its portfolio accordingly.


**Example scenario:** *Middle East Escalation & Ceasefire*
Step sequence: IAEA alert → Israeli strikes → Hormuz blockade → mine-clearing → Muscat ceasefire


**Grading (deterministic, terminal):**


```
0.35 × mean_step_prediction_accuracy
+ 0.40 × simulated_PnL_vs_benchmark
+ 0.25 × max_drawdown_control
```


- Partial-progress reward is emitted at every step (per-step direction accuracy)
- Terminal reward adds PnL simulation and drawdown scoring


**Expected score range:** 0.10 – 0.60


---


## Observation Space


Each observation is a typed `GeoTradeObservation` (Pydantic v2) containing:


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
| `market_snapshot[symbol].gti_sensitivity` | float [0–1] | Asset responsiveness to geopolitical stress |
| `portfolio.weights` | dict | Current portfolio weights by symbol |
| `portfolio.cash_pct` | float | Cash allocation percentage |
| `portfolio.unrealized_pnl` | float | Cumulative unrealized PnL |
| `prompt` | string | Natural-language description of the agent's task |


---


## Action Space


Each action is a typed `GeoTradeAction` (Pydantic v2):


| Field | Type | Description |
|---|---|---|
| `task_id` | string | Must match the environment task |
| `decisions[].symbol` | string | Asset symbol (e.g. `XAUUSD`) |
| `decisions[].direction` | enum | `BUY`, `SELL`, or `HOLD` |
| `decisions[].weight` | float [0–1] | Target portfolio weight |
| `decisions[].confidence` | float [0–1] | Agent's confidence in this decision |
| `primary_signal` | string | One-sentence geopolitical interpretation |
| `reasoning` | string | Full chain-of-thought explanation |


**Hard constraints:** `sum(weights) ≤ 1.0`, `max(weight) ≤ 0.45`


---


## Reward Function


All rewards are in **[0.0, 1.0]**. Partial-progress signals are provided at every step — reward is never purely sparse.


| Task | Partial signal | Terminal signal |
|---|---|---|
| Easy | Immediate after single step | Same |
| Medium | Immediate after single step | Same |
| Hard | Per-step direction accuracy | PnL + drawdown scoring |


**Penalties for undesirable behaviour:**


| Behaviour | Penalty |
|---|---|
| Violating weight constraints (`sum > 1.0`) | `constraint_satisfaction = 0` |
| Over-concentration (single asset > 45%) | `risk_management` score penalised |
| Wrong direction on high-volatility assets | Negative contribution to `opportunity_capture` |
| Empty or missing decisions | All component scores zeroed |


The reward is decomposed into named components (`accuracy`, `risk_management`, `opportunity_capture`, `constraint_satisfaction`, `reasoning_quality`) so agents can receive targeted feedback at every step.


---


## Setup & Usage


### Prerequisites


- Python 3.11+
- `pip` or Docker


### Local Python (no Docker)


```bash
# Clone the repository
git clone https://github.com/Shreya5473/Meta-Hackathon
cd Meta-Hackathon


# Install lean dependencies
pip install -r requirements_openenv.txt


# Set environment variables
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export HF_TOKEN=hf_[your-actual-token-here]


# Run the baseline inference script
python inference.py


# Start the HTTP server
python -m uvicorn openenv.server:app --host 0.0.0.0 --port 7860
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


# State — inspect current environment state
curl "http://localhost:7860/state?session_id=<SESSION_ID>"


# List available tasks
curl http://localhost:7860/tasks


# Health check
curl http://localhost:7860/health
```


---


## Deployment


### Docker


```bash
# Build the image
docker build -t geotrade-openenv .


# Run the container
docker run -p 7860:7860 \
 -e API_BASE_URL=https://router.huggingface.co/v1 \
 -e MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
 -e HF_TOKEN=hf_[your-actual-token-here] \
 geotrade-openenv
```


The server starts on port **7860** and serves the OpenEnv FastAPI endpoints.


### Hugging Face Spaces


The environment is deployable as a Docker-SDK Hugging Face Space tagged with `openenv`.


1. Fork or push this repository to Hugging Face Hub
2. Set the following Space secrets: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
3. The Space will build and expose the server at `https://<your-space>.hf.space`


The `openenv.yaml` file at the repository root provides all metadata required by the OpenEnv registry.


---


## Baseline Scores


Baseline scores produced by `Qwen/Qwen2.5-72B-Instruct` via the Hugging Face Inference Router (temperature=0.2) across all scenarios:


| Task | Scenarios | Mean Score | Score Range |
|---|---|---|---|
| `task_easy` | 5 | ~0.62 | 0.40 – 0.82 |
| `task_medium` | 3 | ~0.48 | 0.30 – 0.65 |
| `task_hard` | 2 | ~0.35 | 0.22 – 0.48 |
| **Overall** | **10** | **~0.48** | |


To reproduce these scores:


```bash
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export HF_TOKEN=hf_[your-actual-token-here]
python inference.py
```


---


## Project Structure


```
Meta-Hackathon/
├── openenv/
│   ├── __init__.py          # Public exports: GeoTradeEnv, GeoTradeAction
│   ├── models.py            # Pydantic v2 Observation/Action/Reward models
│   ├── scenarios.py         # Scenario datasets (5 easy, 3 medium, 2 hard)
│   ├── graders.py           # Deterministic task graders (scores 0.0–1.0)
│   ├── environment.py       # GeoTradeEnv — reset / step / state
│   └── server.py            # FastAPI HTTP server for HF Spaces
├── app/                     # Full GeoTrade AI backend (GTI engine, ML models)
├── frontend/                # React/TypeScript frontend (built into Docker image)
├── config/                  # Application configuration
├── db/                      # Database schema and migrations
├── alembic/                 # Alembic migration scripts
├── scripts/                 # Utility scripts
├── tests/                   # Test suite
├── infra/docker/            # Additional Docker configuration
├── openenv.yaml             # OpenEnv spec metadata
├── inference.py             # Baseline inference script
├── Dockerfile               # Single-stage Python Docker build for OpenEnv server
├── docker-compose.yml       # Compose configuration
├── requirements_openenv.txt # Lean dependencies for the OpenEnv layer
├── requirements.txt         # Full application dependencies
└── README.md                # This file
```


---


## Environment Variables


| Variable | Required | Default | Description |
|---|---|---|---|
| `API_BASE_URL` | Yes | `https://router.huggingface.co/v1` | OpenAI-compatible API base URL |
| `MODEL_NAME` | Yes | `Qwen/Qwen2.5-72B-Instruct` | Model identifier for LLM inference |
| `HF_TOKEN` | Yes | — | Hugging Face API token (obtain from https://huggingface.co/settings/tokens) |
| `IMAGE_NAME` | No | — | Docker image name for containerised evaluation |


> **Note:** Replace `hf_[your-actual-token-here]` with your actual Hugging Face token when running locally or in production.


---


## Tech Stack


- **Python 3.11** + **FastAPI** + **Pydantic v2**
- **LLM Inference:** OpenAI-compatible client — default model `Qwen/Qwen2.5-72B-Instruct` via HF Inference Router
- **NLP (backend):** `cross-encoder/nli-distilroberta-base` for geopolitical event classification
- **Environment:** Fully self-contained, no external data APIs required at runtime
- **Deployment:** Docker + Hugging Face Spaces (port 7860)
- **Validation:** `openenv validate` compatible


---


*Disclaimer: GeoTrade OpenEnv is an evaluation environment. All scenarios are synthetic and calibrated to historical geo-financial patterns. Not financial advice.*
