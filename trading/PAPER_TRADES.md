# GeoTrade — Hypothetical Paper Trades
## Based on Freeze Snapshot: Monday 16 March 2026, 16:43 UTC

> **Premise:** GeoTrade's NLP + ML engine detected an Iran-Israel military escalation event
> (severity 92%) and generated BUY signals across safe-haven commodities and defense stocks.
> We are hypothetically investing a **$100,000 paper portfolio** proportional to signal confidence.
> In 12 hours, we will record actual prices and show the P&L trail.

---

## Portfolio Allocation Rules

- Total capital: **$100,000 USD**
- Position sizing: proportional to (confidence% × (1 - uncertainty%))
- Max single position: 15% of portfolio
- HOLD signals: allocated only 2% (watchlist only, no real conviction)
- All trades entered at the frozen snapshot price

---

## Position Sizing Calculation

| Symbol | Action | Conf% | Uncert% | Adj Score | Weight | Allocation |
|--------|--------|-------|---------|-----------|--------|------------|
| RTX | BUY | 88.8% | 18.3% | 72.5 | 15.0% | $15,000 |
| ITA | BUY | 84.5% | 10.8% | 75.4 | 15.0% | $15,000 |
| XAUUSD | BUY | 83.8% | 17.3% | 69.3 | 14.3% | $14,300 |
| LMT | BUY | 80.4% | 25.1% | 60.2 | 12.4% | $12,400 |
| WTI | BUY | 76.6% | 32.2% | 51.9 | 10.7% | $10,700 |
| NOC | BUY | 76.3% | 31.3% | 52.4 | 10.8% | $10,800 |
| XAGUSD | BUY | 71.9% | 29.6% | 50.7 | — | folded into NATGAS |
| BA | BUY | 71.5% | 31.3% | 49.1 | — | folded into GD |
| GD | BUY | 74.3% | 29.7% | 52.3 | — | (GD+BA combined) |
| NATGAS | BUY | 56.1% | 42.3% | 32.4 | 6.6% | $6,600 |
| BTCUSD | HOLD | 55.8% | 48.2% | 28.9 | 2.0% | $2,000 |
| GD + BA combo | BUY | 73% avg | 30% avg | 51% | 13.2% | $13,200 |

**Total Deployed: $100,000**

---

## Trade Ledger

### TRADE #001 — Raytheon Technologies (RTX)
```
Symbol:        RTX
Action:        BUY
Allocation:    $15,000
Entry Price:   $205.22
Units:         73.09 shares
Stop Loss:     $199.03  (risk per share: $6.19 → total risk: $452.46)
Target:        $217.59  (upside per share: $12.37)
Risk:Reward:   2.0
Position Size: 7.3% of portfolio
Triggered By:  Iran-Israel Escalation — military_escalation (sev 92%)
Signal Conf:   88.8%  |  Vol Spike: 81.7%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #002 — iShares Defense ETF (ITA)
```
Symbol:        ITA
Action:        BUY
Allocation:    $15,000
Entry Price:   $231.31
Units:         64.84 shares
Stop Loss:     $226.29  (risk per share: $5.02 → total risk: $325.45)
Target:        $241.35  (upside per share: $10.04)
Risk:Reward:   2.0
Position Size: 7.5% of portfolio
Triggered By:  Iran-Israel Escalation — military_escalation (sev 92%)
Signal Conf:   84.5%  |  Vol Spike: 77.7%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #003 — Gold / XAUUSD (via GLD ETF proxy)
```
Symbol:        XAUUSD (GLD proxy)
Action:        BUY
Allocation:    $14,300
Entry Price:   $458.05
Units:         31.22 units
Stop Loss:     $445.90  (risk per unit: $12.15 → total risk: $379.32)
Target:        $482.35  (upside per unit: $24.30)
Risk:Reward:   2.0
Position Size: 6.9% of portfolio
Triggered By:  Iran-Israel Escalation — safe-haven flight
Signal Conf:   83.8%  |  Vol Spike: 77.1%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #004 — Lockheed Martin (LMT)
```
Symbol:        LMT
Action:        BUY
Allocation:    $12,400
Entry Price:   $642.28
Units:         19.31 shares
Stop Loss:     $622.92  (risk per share: $19.36 → total risk: $373.84)
Target:        $681.00  (upside per share: $38.72)
Risk:Reward:   2.0
Position Size: 6.2% of portfolio
Triggered By:  Iran-Israel Escalation — defense contractor demand
Signal Conf:   80.4%  |  Vol Spike: 74.0%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #005 — WTI Crude Oil (via USO ETF proxy)
```
Symbol:        WTI (USO proxy)
Action:        BUY
Allocation:    $10,700
Entry Price:   $117.86
Units:         90.79 units
Stop Loss:     $114.73  (risk per unit: $3.13 → total risk: $284.17)
Target:        $124.11  (upside per unit: $6.25)
Risk:Reward:   2.0
Position Size: 5.4% of portfolio
Triggered By:  Iran-Israel Escalation — Middle East supply disruption risk
Signal Conf:   76.6%  |  Vol Spike: 70.5%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #006 — Northrop Grumman (NOC)
```
Symbol:        NOC
Action:        BUY
Allocation:    $10,800
Entry Price:   $450.11
Units:         24.00 shares
Stop Loss:     $436.54  (risk per share: $13.57 → total risk: $325.68)
Target:        $477.25  (upside per share: $27.14)
Risk:Reward:   2.0
Position Size: 5.4% of portfolio
Triggered By:  Iran-Israel Escalation — defense/aerospace demand
Signal Conf:   76.3%  |  Vol Spike: 70.2%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #007 — General Dynamics + Boeing Combined
```
Symbol:        GD + BA  (split $6,600 / $6,600)
Action:        BUY
Sub-trade GD:
  Entry Price: $284.44  |  Units: 23.20 shares
  Stop: $275.86  |  Target: $301.58  |  R:R: 2.0
Sub-trade BA:
  Entry Price: $180.47  |  Units: 36.57 shares
  Stop: $175.03  |  Target: $191.35  |  R:R: 2.0
Total Allocation: $13,200
Triggered By:  Iran-Israel Escalation — aerospace/defense
Signal Conf:   GD 74.3% / BA 71.5%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #008 — Natural Gas (via UNG ETF proxy)
```
Symbol:        NATGAS (UNG proxy)
Action:        BUY
Allocation:    $6,600
Entry Price:   $12.22
Units:         540.10 units
Stop Loss:     $11.91  (risk per unit: $0.31 → total risk: $167.43)
Target:        $12.84  (upside per unit: $0.62)
Risk:Reward:   2.0
Position Size: 3.3% of portfolio
Triggered By:  US-China Trade Tariff Expansion — Semiconductors
Signal Conf:   56.1%  |  Vol Spike: 42.1%
Entry Time:    2026-03-16T16:43 UTC
Status:        OPEN
```

### TRADE #009 — Bitcoin (WATCHLIST ONLY)
```
Symbol:        BTCUSD
Action:        HOLD (watchlist)
Allocation:    $2,000
Entry Price:   $73,640.18  (Binance live — authoritative source)
Units:         0.0272 BTC
Stop Loss:     $64,068.00  (signal-derived)
Target:        $71,131.87  (signal-derived — note: target < entry due to stale signal cache)
Risk:Reward:   1.0
Position Size: 1.0% of portfolio
Note:          Signal engine used stale $67,599 cache price. Binance confirms $73,640.
               HOLD signal maintained. Monitoring only. No active direction bet.
Signal Conf:   55.8%  |  Uncertainty: 48.2%
Entry Time:    2026-03-16T16:43 UTC
Status:        WATCHLIST / OPEN
```

---

## Portfolio Summary at Open

| Metric | Value |
|--------|-------|
| Total Capital | $100,000 |
| Deployed | $100,000 (100%) |
| Open Positions | 9 (11 instruments) |
| Avg Confidence | 75.1% |
| Total Risk if All Stops Hit | ~$2,500 (2.5%) |
| Weighted R:R Ratio | ~2.0 |
| Primary Thesis | Iran-Israel military escalation → safe-haven + defense rally |
| Secondary Thesis | US-China tariffs → energy supply rerouting → NatGas bid |

---

## Outcome Tracking (To Be Filled at Investor Meeting ~04:43 UTC, 17 Mar 2026)

| Symbol | Entry | Exit Price | P&L $ | P&L % | Hit Target? | Hit Stop? |
|--------|-------|------------|-------|-------|-------------|-----------|
| RTX | $205.22 | TBD | TBD | TBD | — | — |
| ITA | $231.31 | TBD | TBD | TBD | — | — |
| XAUUSD | $458.05 | TBD | TBD | TBD | — | — |
| LMT | $642.28 | TBD | TBD | TBD | — | — |
| WTI | $117.86 | TBD | TBD | TBD | — | — |
| NOC | $450.11 | TBD | TBD | TBD | — | — |
| GD | $284.44 | TBD | TBD | TBD | — | — |
| BA | $180.47 | TBD | TBD | TBD | — | — |
| NATGAS | $12.22 | TBD | TBD | TBD | — | — |
| BTCUSD | $73,640 | TBD | TBD | TBD | — | — |

---

*All trades hypothetical. Not financial advice. GeoTrade demonstration only.*
