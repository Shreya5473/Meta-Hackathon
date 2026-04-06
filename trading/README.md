# GeoTrade — Trading Folder

This folder tracks the live investor demonstration for GeoTrade.

## Files

| File | Purpose |
|------|---------|
| `SNAPSHOT_2026-03-16.md` | **Frozen market prices** at 16:43 UTC, 16 Mar 2026. All prices verified live from Finnhub + Binance. This is the baseline for Round 1. |
| `PAPER_TRADES.md` | **Round 1 — hypothetical $100,000 portfolio** built on GeoTrade signals. 9 trades across 11 instruments. Entry, stop-loss, and target documented. |
| `PAPER_TRADES_ROUND2.md` | **Round 2 — paper trades** entered ~18:27 UTC 16 Mar 2026 after ML deployment; live snapshot, allocations, and risk (1.5% per trade). |
| `OUTCOME_LOG.md` | **P&L / outcome tracking** — Round 2 live outcome table (updated 2026-03-17 08:08 UTC, ~14h after entry) plus meeting checklist. |

## The Story for Investors

```
16:43 UTC — FREEZE
GeoTrade detects Iran-Israel escalation (sev 92%)
  ↓
NLP pipeline classifies event → military_escalation
  ↓
GTI engine updates geopolitical tension index
  ↓
LightGBM + XGBoost ensemble generates signals
  ↓
BUY: Gold, Silver, WTI, NatGas, LMT, RTX, NOC, GD, BA, ITA
HOLD: BTC
↓
$100,000 paper portfolio deployed (Round 1 — see `PAPER_TRADES.md`)
↓
Round 2 re-entry after ML + key rotation — see `PAPER_TRADES_ROUND2.md` + `OUTCOME_LOG.md`
↓
~04:43 UTC — INVESTOR MEETING
Check prices. Show trail. Prove it works.
```

## Assets Tracked

### Commodities (5)
- XAUUSD — Gold
- XAGUSD — Silver
- WTI — Crude Oil (Petroleum)
- NATGAS — Natural Gas
- BTCUSD — Bitcoin

### Defense Stocks (6)
- LMT — Lockheed Martin
- RTX — Raytheon Technologies
- NOC — Northrop Grumman
- GD — General Dynamics
- BA — Boeing
- ITA — iShares Defense ETF (basket)

## Data Verification

All prices confirmed **live and real-time**:
- Finnhub API timestamps: 16:41–16:43 UTC on 16 Mar 2026
- Binance public REST API for BTC: 16:43 UTC
- Source field in API responses: `"source": "finnhub"`
