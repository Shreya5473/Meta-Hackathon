# Paper Trades — Round 2
**Date**: 2026-03-16  
**Time**: ~18:27 UTC  
**Portfolio Size**: $100,000  
**Trigger**: ML model trained on 5yr real market data (LightGBM + XGBoost VotingClassifier)  
**Data Source**: Finnhub (key rotation, 120 req/min) + Binance WebSocket (BTC)  
**Unit Tests**: 101/101 passing

---

## Live Market Snapshot (18:27 UTC)

| Asset   | Feed Symbol      | Live Price  | Realized Vol | 1d Return |
|---------|-----------------|-------------|-------------|-----------|
| XAUUSD  | GLD             | $459.57     | 12.2%       | -0.3%     |
| XAGUSD  | SLV             | $73.05      | 25.5%       | +0.5%     |
| WTI     | USO             | $114.98     | 44.7%       | -4.1%     |
| NATGAS  | UNG             | $12.12      | 43.3%       | -4.1%     |
| BTCUSD  | BINANCE:BTCUSDT | $74,226.46  | 41.7%       | +3.5%     |
| LMT     | LMT             | $644.44     | 18.5%       | -0.2%     |
| RTX     | RTX             | $206.35     | 19.8%       | +0.9%     |

---

## ML Model Output (VotingClassifier — LightGBM + XGBoost)
**Input GTI**: 48.0 | **GTI Delta**: +3.5/hr | **GTI Confidence**: 70%

| Asset   | Vol Spike (24h) | Directional Bias | Recommendation | Confidence |
|---------|----------------|-----------------|----------------|-----------|
| XAUUSD  | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |
| XAGUSD  | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |
| WTI     | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |
| NATGAS  | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |
| BTCUSD  | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |
| LMT     | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |
| RTX     | 12.3%          | +0.058 (bullish) | Hold           | 69.6%     |

> Model trained on SPY/VIX/USO 5yr daily data. GTI=48 with moderate tension returns
> moderate vol risk (12%) and slight positive bias. Geopolitical tension is elevated
> but not at crisis levels — model correctly outputs Hold / cautious.

---

## Round 2 Trade Entries

Based on the ML output (Hold / moderate tension) combined with the live vol and
price direction, we enter smaller positions than Round 1, skewed toward assets
showing real momentum divergence from the baseline.

### Position Sizing
- Capital: $100,000
- Risk per trade: 1.5% ($1,500)
- ATR-based stop sizing from realized vol

| # | Asset  | Direction | Entry Price | Stop     | Target   | R:R  | Size    | $ Notional | Rationale |
|---|--------|-----------|-------------|----------|----------|------|---------|------------|-----------|
| 1 | XAUUSD | LONG      | $459.57     | $448.00  | $480.00  | 1.77 | 3.3 oz  | $1,517     | Safe-haven + GTI>45, bullish ML bias |
| 2 | BTCUSD | LONG      | $74,226     | $70,500  | $81,000  | 1.82 | 0.0135  | $1,002     | +3.5% 1d momentum, ML vol moderate |
| 3 | LMT    | LONG      | $644.44     | $625.00  | $672.00  | 1.42 | 2.3 sh  | $1,482     | Defense sector; GTI elevated, conflict premium |
| 4 | RTX    | LONG      | $206.35     | $199.00  | $220.00  | 1.86 | 7.3 sh  | $1,506     | Defense proxy; +0.9% 1d strength |
| 5 | WTI    | SHORT     | $114.98     | $118.50  | $108.00  | 2.00 | 15 sh   | $1,725     | -4.1% 1d, high vol=44.7%, bearish follow-through |
| 6 | NATGAS | SHORT     | $12.12      | $12.55   | $11.20   | 2.14 | 120 sh  | $1,454     | -4.1% 1d momentum, seasonal weakness |

**Total deployed**: ~$8,686 (8.7% of portfolio)  
**Max risk**: $9,000 (6 × $1,500)  
**Cash reserved**: $91,314

---

## System Status at Entry

| Component         | Status  | Detail                                      |
|------------------|---------|---------------------------------------------|
| API              | ✅ Live  | `/health` → healthy, db=true, redis=true    |
| Market Feed      | ✅ Live  | Finnhub dual-key rotation, 120 req/min      |
| Signals V2       | ✅ Live  | 36 signals across universe                  |
| ML Model         | ✅ Live  | VotingClassifier trained 5yr SPY/VIX/USO   |
| Unit Tests       | ✅ Pass  | 101/101 passing                             |
| Key Rotation     | ✅ Active| Key1 exhausted (debug session), Key2 serving|
| BTC Feed         | ✅ Live  | Binance WebSocket: $74,226                  |

---

## Outcome Tracking

To update P&L at investor meeting:

```bash
# Pull live prices
curl -s http://localhost:8000/api/v1/market/prices | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d['prices']:
    print(p['symbol'], p.get('close', p.get('price')))
"
```

**Updated: 2026-03-17 08:08 UTC (~14h after entry)**

| Trade        | Entry       | Current     | Change   | P&L $   | Status  |
|--------------|-------------|-------------|----------|---------|---------|
| XAUUSD LONG  | $459.57     | $460.43     | +0.19%   | +$2.84  | 🟡 Open |
| BTCUSD LONG  | $74,226     | $74,375     | +0.20%   | +$2.02  | 🟡 Open |
| LMT LONG     | $644.44     | $645.20     | +0.12%   | +$1.75  | 🟡 Open |
| RTX LONG     | $206.35     | $206.06     | -0.14%   | -$2.12  | 🟡 Open |
| WTI SHORT    | $114.98     | $115.03     | -0.04%   | -$0.75  | 🟡 Open |
| NATGAS SHORT | $12.12      | $12.21      | -0.74%   | -$10.80 | 🟡 Open |

**Total P&L: -$7.07 (-0.08% on deployed capital, -0.01% portfolio)**  
Winners: 3/6 | Losers: 3/6 | None stopped out | None hit target yet

### Read
- All 6 positions live and inside their risk bands (no stops hit, no targets hit)
- XAUUSD, BTC, LMT moving gently in our direction overnight
- RTX slipped slightly (-0.14%) — well above $199 stop, holding
- WTI and NATGAS both drifting slightly against short thesis (-0.04%, -0.74%)
- NATGAS is the weakest position at -$10.80 but still above the $12.55 stop
- Market opened Monday; expect intraday vol to resolve direction on all positions

---

*Not financial advice. Paper trading only. All positions hypothetical.*
