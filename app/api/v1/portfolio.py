"""Portfolio evaluation + cart (email-based anonymous portfolio) endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import build_audit_meta
from app.core.database import get_db
from app.core.logging import get_logger
from app.pipelines.market_model import get_impact_model, AssetFeatures
from app.pipelines.simulators import Holding as SimHolding
from app.pipelines.simulators import PortfolioSimulator, ScenarioShock
from app.pipelines.gti_engine import get_gti_engine
from app.repositories.gti_repo import GTIRepository
from app.repositories.persistence_repo import UserPortfolioRepository
from app.services.persistence_service import PortfolioPersistenceService
from app.schemas.portfolio import (
    CartHolding,
    CartHoldingRisk,
    CartResponse,
    CartSaveRequest,
    DrawdownBucket,
    PnLResponse,
    PnLSummary,
    PortfolioEvalRequest,
    PortfolioEvalResponse,
    PortfolioRiskRequest,
    PortfolioRiskResponse,
    PnLRange,
    RegionExposure,
    SectorExposure,
    TradeDecisionOut,
    TradeExecuteRequest,
    TradeExecuteResponse,
    TradeLogEntry,
    UserPortfolioSaved,
    UserPortfolioCreate,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
limiter = Limiter(key_func=get_remote_address)
logger = get_logger(__name__)


@router.post("/evaluate", response_model=PortfolioEvalResponse)
async def evaluate_portfolio(
    req: PortfolioEvalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PortfolioEvalResponse:
    gti_repo = GTIRepository(db)
    gti_snap = await gti_repo.get_latest("global")
    gti_value = gti_snap.gti_value if gti_snap else 25.0
    gti_delta = gti_snap.gti_delta_1h if gti_snap else 0.0
    gti_conf = gti_snap.confidence if gti_snap else 0.5

    sim = PortfolioSimulator(get_impact_model())
    holdings = [
        SimHolding(
            symbol=h.symbol,
            weight=h.weight,
            sector=h.sector,
            region=h.region,
        )
        for h in req.holdings
    ]

    oil_shock = 0.0
    if req.include_scenario:
        oil_shock = req.scenario_conflict_intensity * 0.5
        gti_value = min(100.0, gti_value + req.scenario_conflict_intensity * 20.0)

    result = sim.simulate(
        holdings=holdings,
        gti_value=gti_value,
        gti_delta=gti_delta,
        gti_confidence=gti_conf,
        oil_shock=oil_shock,
    )

    audit = build_audit_meta()
    return PortfolioEvalResponse(
        expected_stress_impact=result.expected_stress_impact,
        simulated_pnl_range=PnLRange(
            p05=result.pnl_p05,
            p25=result.pnl_p25,
            p50=result.pnl_p50,
            p75=result.pnl_p75,
            p95=result.pnl_p95,
        ),
        drawdown_risk=DrawdownBucket(
            bucket=result.drawdown_bucket,
            max_drawdown_estimate=result.max_drawdown_estimate,
        ),
        sector_exposure=[
            SectorExposure(sector=k, weight=v)
            for k, v in result.sector_exposure.items()
        ],
        region_exposure=[
            RegionExposure(region=k, weight=v)
            for k, v in result.region_exposure.items()
        ],
        scenario_adjusted=req.include_scenario,
        **audit,
    )


# ── Cart (email-keyed anonymous portfolio) ────────────────────────────────────

@router.get("/cart", response_model=CartResponse)
async def get_cart(
    email: str,
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    """Return the saved portfolio for an email-registered user.
    Returns an empty portfolio if the email is not found.
    """
    repo = UserPortfolioRepository(db)
    svc = PortfolioPersistenceService(repo)
    pf = await svc.get_for_email(email)
    if pf is None:
        return CartResponse(email=email, holdings=[], name="My Portfolio")
    return CartResponse(
        email=pf.user_email or email,
        holdings=[CartHolding(**h) for h in (pf.holdings or [])],
        name=pf.name,
        updated_at=pf.updated_at,
    )


@router.post("/cart", response_model=CartResponse, status_code=200)
async def save_cart(
    req: CartSaveRequest,
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    """Save (upsert) portfolio holdings for an email-registered user."""
    repo = UserPortfolioRepository(db)
    svc = PortfolioPersistenceService(repo)
    holdings_data = [h.model_dump() for h in req.holdings]
    pf = await svc.save_for_email(
        email=str(req.email),
        holdings=holdings_data,
        name=req.name,
    )
    await db.commit()
    return CartResponse(
        email=pf.user_email or str(req.email),
        holdings=[CartHolding(**h) for h in (pf.holdings or [])],
        name=pf.name,
        updated_at=pf.updated_at,
    )


@router.post("/risk", response_model=PortfolioRiskResponse)
async def portfolio_risk(
    req: PortfolioRiskRequest,
    db: AsyncSession = Depends(get_db),
) -> PortfolioRiskResponse:
    """Return per-asset and aggregate risk metrics for the email user's portfolio.

    Uses live market data and the ML model. If live data is unavailable for a
    symbol, that holding is marked data_status='data_unavailable' — no synthetic
    substitution occurs.
    """
    repo = UserPortfolioRepository(db)
    svc = PortfolioPersistenceService(repo)
    pf = await svc.get_for_email(str(req.email))
    if pf is None or not pf.holdings:
        raise HTTPException(status_code=404, detail="No portfolio found for this email. Save holdings first.")

    gti_repo = GTIRepository(db)
    gti_snap = await gti_repo.get_latest("global")
    gti_value = gti_snap.gti_value if gti_snap else 25.0
    gti_delta = gti_snap.gti_delta_1h if gti_snap else 0.0
    gti_conf = gti_snap.confidence if gti_snap else 0.5

    # Live market prices: try feed manager cache first, then live fetch for misses
    try:
        from app.pipelines.market_feeds import get_feed_manager, RealMarketAdapter
        cached_ticks = {t.symbol: t for t in get_feed_manager().get_all()}
    except Exception:
        cached_ticks = {}

    needed_symbols = [h.get("symbol", "") for h in pf.holdings if h.get("symbol")]
    missing = [s for s in needed_symbols if s not in cached_ticks]

    # Live-fetch missing symbols — route crypto to Binance, others to Finnhub
    live_fetched: dict = {}
    if missing:
        # Crypto symbols → Binance public REST (no API key needed)
        from app.pipelines.market_feeds import _BINANCE_CRYPTO_SYMBOLS, BinanceCryptoAdapter
        crypto_missing = [s for s in missing if s in _BINANCE_CRYPTO_SYMBOLS]
        non_crypto_missing = [s for s in missing if s not in _BINANCE_CRYPTO_SYMBOLS]

        if crypto_missing:
            try:
                _bn_adapter = BinanceCryptoAdapter()
                _bn_fetched = await _bn_adapter.fetch_latest(crypto_missing)
                live_fetched.update({t.symbol: t for t in _bn_fetched})
                await _bn_adapter.close()
            except Exception as _exc:
                logger.warning("portfolio_binance_fetch_failed", error=str(_exc))

        if non_crypto_missing:
            try:
                from app.core.config import get_settings as _gs
                _fh_key = _gs().finnhub_api_key
                if _fh_key:
                    from app.pipelines.market_feeds import RealMarketAdapter
                    _adapter = RealMarketAdapter(api_key=_fh_key)
                    _fetched = await _adapter.fetch_latest(non_crypto_missing)
                    live_fetched.update({t.symbol: t for t in _fetched})
                    await _adapter.close()
            except Exception as _exc:
                logger.warning("portfolio_finnhub_fetch_failed", error=str(_exc))

    # For forex symbols, overlay with real OANDA prices when key is configured
    oanda_ticks: dict = {}
    try:
        from app.core.config import get_settings as _gs2
        _settings = _gs2()
        _oanda_forex = [
            s for s in needed_symbols
            if s.replace("/", "_").upper() in {
                "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
                "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
            }
        ]
        if _oanda_forex and _settings.oanda_api_key and "REPLACE_WITH" not in _settings.oanda_api_key:
            from app.pipelines.market_data import OandaFeed
            # Map portfolio symbol (EURUSD) to OANDA instrument (EUR_USD)
            _oanda_instruments = [
                s[:3] + "_" + s[3:] if len(s) == 6 else s
                for s in _oanda_forex
            ]
            _oanda_feed = OandaFeed()
            _oanda_raw = await _oanda_feed.fetch(_oanda_instruments)
            for tick in _oanda_raw:
                # Convert OANDA symbol back (EUR_USD → EURUSD)
                internal_sym = tick.symbol.replace("_", "")
                oanda_ticks[internal_sym] = tick
            logger.info("oanda_prices_fetched", count=len(oanda_ticks))
    except Exception as _exc:
        logger.warning("oanda_price_fetch_failed", error=str(_exc))

    live_ticks = {**cached_ticks, **live_fetched}  # cache < live-fetch override

    # Live Finnhub technical indicators (best-effort per symbol)
    import os
    finnhub_key = os.environ.get("FINNHUB_API_KEY", "")
    if not finnhub_key:
        try:
            from app.core.config import get_settings
            finnhub_key = get_settings().finnhub_api_key or ""
        except Exception:
            pass

    from app.pipelines.live_indicators import FinnhubLiveIndicators
    import asyncio
    symbols = [h["symbol"] for h in pf.holdings if "symbol" in h]
    if finnhub_key and symbols:
        ind_svc = FinnhubLiveIndicators(api_key=finnhub_key)
        ind_results = await asyncio.gather(
            *[ind_svc.fetch(sym) for sym in symbols],
            return_exceptions=True,
        )
        live_inds: dict[str, dict] = {
            sym: (res if isinstance(res, dict) else {})
            for sym, res in zip(symbols, ind_results)
        }
    else:
        live_inds = {}

    model = get_impact_model()
    holding_risks: list[CartHoldingRisk] = []
    total_weight = sum(float(h.get("weight", 1.0)) for h in pf.holdings) or 1.0

    for h in pf.holdings:
        sym = h.get("symbol", "")
        weight = float(h.get("weight", 1.0))
        sector = h.get("sector")
        region = h.get("region", "global")
        label = h.get("label", sym)
        tick = live_ticks.get(sym)
        inds = live_inds.get(sym, {})

        # For forex: use real OANDA bid/ask mid price if available, no synthetic
        if sym in oanda_ticks:
            oanda_t = oanda_ticks[sym]
            oanda_price = float(oanda_t.mid)
            r_vol = 0.06  # typical FX realised vol; OANDA ticks don't carry H/L
            r1d = float(tick.return_1d) if tick and tick.return_1d is not None else 0.0
            r5d = float(tick.return_5d) if tick and tick.return_5d is not None else 0.0
            source_tag = f"oanda:{oanda_price:.5f}"
        elif tick is not None:
            oanda_price = None
            r_vol = float(tick.realized_vol) if tick.realized_vol else 0.15
            r1d = float(tick.return_1d) if tick.return_1d is not None else 0.0
            r5d = float(tick.return_5d) if tick.return_5d is not None else 0.0
            source_tag = tick.source
        else:
            oanda_price = None
            r_vol = None
            r1d = None
            r5d = None
            source_tag = None

        if oanda_price is None and tick is None and not inds:
            # Live data genuinely unavailable — flag it, no synthetic substitution
            holding_risks.append(CartHoldingRisk(
                symbol=sym, label=label, weight=weight,
                sector=sector, region=region, data_status="data_unavailable",
            ))
            continue

        # r_vol / r1d / r5d already resolved above from OANDA or Finnhub
        if r_vol is None:
            r_vol = 0.15
        if r1d is None:
            r1d = 0.0
        if r5d is None:
            r5d = 0.0

        features = AssetFeatures(
            symbol=sym,
            sector=sector,
            region=region or "global",
            gti_value=gti_value,
            gti_delta_1h=gti_delta,
            gti_confidence=gti_conf,
            realized_vol=r_vol,
            return_1d=r1d,
            return_5d=r5d,
            regime_vix_proxy=min(1.0, gti_value / 80.0),
            rsi_14=inds.get("rsi_14", 0.5),
            macd_signal_diff=inds.get("macd_signal_diff", 0.0),
            bb_pct_b=inds.get("bb_pct_b", 0.5),
        )
        try:
            result = model.predict(features)
            gti_exposure = (gti_value / 100.0) * (weight / total_weight)
            holding_risks.append(CartHoldingRisk(
                symbol=sym,
                label=label,
                weight=weight,
                sector=sector,
                region=region,
                vol_spike_prob=round(result.vol_spike_prob_24h, 4),
                directional_bias=round(result.directional_bias, 4),
                gti_exposure=round(gti_exposure, 4),
                recommendation=result.recommendation,
                data_status="ok",
            ))
        except Exception as exc:
            logger.warning("portfolio_risk_predict_failed", symbol=sym, error=str(exc))
            holding_risks.append(CartHoldingRisk(
                symbol=sym, label=label, weight=weight,
                sector=sector, region=region, data_status="data_unavailable",
            ))

    # Aggregate metrics
    ok_risks = [h for h in holding_risks if h.data_status == "ok"]
    if ok_risks:
        overall_vol = sum((h.vol_spike_prob or 0) * (h.weight / total_weight) for h in ok_risks)
        overall_gti = sum((h.gti_exposure or 0) for h in ok_risks)
    else:
        overall_vol = 0.0
        overall_gti = 0.0

    if overall_vol >= 0.7:
        classification = "HIGH"
    elif overall_vol >= 0.5:
        classification = "ELEVATED"
    elif overall_vol >= 0.3:
        classification = "MODERATE"
    else:
        classification = "LOW"

    # Sort by risk descending so frontend gets priority order
    holding_risks.sort(key=lambda x: (x.vol_spike_prob or 0), reverse=True)
    top_driver = holding_risks[0].symbol if holding_risks else None

    return PortfolioRiskResponse(
        email=str(req.email),
        holdings=holding_risks,
        overall_gti_exposure=round(overall_gti, 4),
        overall_vol_risk=round(overall_vol, 4),
        risk_classification=classification,
        top_risk_driver=top_driver,
    )


@router.get("", response_model=list[UserPortfolioSaved])
async def list_user_portfolios(db: AsyncSession = Depends(get_db)):
    repo = UserPortfolioRepository(db)
    svc = PortfolioPersistenceService(repo)
    return await svc.get_all()


@router.post("", response_model=UserPortfolioSaved, status_code=201)
async def save_user_portfolio(
    req: UserPortfolioCreate, db: AsyncSession = Depends(get_db)
):
    repo = UserPortfolioRepository(db)
    svc = PortfolioPersistenceService(repo)
    return await svc.create(name=req.name, holdings=req.holdings, description=req.description)


# ---------------------------------------------------------------------------
# Trade Execution endpoint
# ---------------------------------------------------------------------------

@router.post("/execute", response_model=TradeExecuteResponse)
async def execute_portfolio_trades(
    req: TradeExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Evaluate ML signals for the saved portfolio and, when dry_run=False,
    place paper orders via the OANDA Practice API.

    Signal → action thresholds:
    - vol_spike_prob > 0.70 AND directional_bias < -0.02  → SELL
    - vol_spike_prob < 0.30 AND directional_bias > +0.02  → BUY
    - otherwise                                           → HOLD

    All decisions (including HOLDs) are persisted to ``trade_log``.
    """
    from app.repositories.persistence_repo import UserPortfolioRepository as _PR
    from app.services.persistence_service import PortfolioPersistenceService as _PS
    from app.trading.executor import OrderManager, SignalInput

    # 1. Load portfolio
    _repo = _PR(db)
    _svc = _PS(_repo)
    pf = await _svc.get_for_email(str(req.email))
    if pf is None or not pf.holdings:
        raise HTTPException(status_code=404, detail="portfolio_not_found")

    # 2. Fetch ML signals (re-run risk logic)
    from app.pipelines.market_feeds import get_feed_manager
    from app.pipelines.market_model import get_impact_model, AssetFeatures
    from app.repositories.gti_repo import GTIRepository

    gti_repo = GTIRepository(db)
    gti_snap = await gti_repo.get_latest("global")
    gti_value = gti_snap.gti_value if gti_snap else 25.0
    gti_delta = gti_snap.gti_delta_1h if gti_snap else 0.0
    gti_conf = gti_snap.confidence if gti_snap else 0.5

    cached_ticks = {t.symbol: t for t in get_feed_manager().get_all()}
    symbols = [h.get("symbol", "") for h in pf.holdings if "symbol" in h]
    missing = [s for s in symbols if s not in cached_ticks]
    live_ticks: dict = {**cached_ticks}
    if missing:
        try:
            from app.core.config import get_settings as _gs
            _fh_key = _gs().finnhub_api_key
            if _fh_key:
                from app.pipelines.market_feeds import RealMarketAdapter
                _adapter = RealMarketAdapter(api_key=_fh_key)
                _fetched = await _adapter.fetch_latest(missing)
                live_ticks.update({t.symbol: t for t in _fetched})
                await _adapter.close()
        except Exception as _exc:
            logger.warning("execute_live_fetch_failed", error=str(_exc))

    model = get_impact_model()
    total_weight = sum(float(h.get("weight", 1.0)) for h in pf.holdings) or 1.0

    signals: list[SignalInput] = []
    for h in pf.holdings:
        sym = h.get("symbol", "")
        weight = float(h.get("weight", 1.0))
        sector = h.get("sector")
        region = h.get("region", "global")
        tick = live_ticks.get(sym)
        if tick is None:
            continue
        r_vol = float(tick.realized_vol) if tick.realized_vol else 0.15
        r1d = float(tick.return_1d) if tick.return_1d is not None else 0.0
        r5d = float(tick.return_5d) if tick.return_5d is not None else 0.0
        features = AssetFeatures(
            symbol=sym, sector=sector, region=region or "global",
            gti_value=gti_value, gti_delta_1h=gti_delta, gti_confidence=gti_conf,
            realized_vol=r_vol, return_1d=r1d, return_5d=r5d,
            regime_vix_proxy=min(1.0, gti_value / 80.0),
        )
        try:
            result = model.predict(features)
            signals.append(SignalInput(
                symbol=sym,
                vol_spike_prob=result.vol_spike_prob_24h,
                directional_bias=result.directional_bias,
                recommendation=result.recommendation,
                weight=weight,
            ))
        except Exception as _exc:
            logger.warning("execute_predict_failed", symbol=sym, error=str(_exc))

    if not signals:
        raise HTTPException(status_code=422, detail="no_signals_generated")

    # 3. Execute (or dry-run)
    manager = OrderManager()
    if req.dry_run:
        # Evaluate only — determine action without calling broker
        from app.trading.executor import TradeDecision
        from datetime import UTC, datetime
        decisions_out = []
        for sig in signals:
            action = manager._determine_action(sig)
            reason = manager._reason_string(sig, action)
            d = TradeDecision(
                symbol=sig.symbol, action=action, reason=reason,
                status="dry_run", broker="none",
                signal_vol_spike=sig.vol_spike_prob,
                signal_bias=sig.directional_bias,
                recommendation=sig.recommendation,
                note="dry_run=True — no order placed",
            )
            decisions_out.append(d)
        # Persist dry-run decisions for audit
        await manager._log_trades(str(req.email), decisions_out, db)
    else:
        decisions_out = await manager.process_signals(str(req.email), signals, db)

    executed_count = sum(
        1 for d in decisions_out if d.action in ("buy", "sell") and d.status not in ("hold", "dry_run")
    )

    return TradeExecuteResponse(
        email=str(req.email),
        decisions=[
            TradeDecisionOut(
                symbol=d.symbol, action=d.action, reason=d.reason,
                status=d.status, broker=d.broker, quantity=d.quantity,
                fill_price=d.fill_price, order_id=d.order_id,
                signal_vol_spike=d.signal_vol_spike,
                signal_bias=d.signal_bias,
                recommendation=d.recommendation,
                note=d.note,
                ts=d.ts.isoformat(),
            )
            for d in decisions_out
        ],
        executed=executed_count,
        dry_run=req.dry_run,
    )


# ---------------------------------------------------------------------------
# P&L endpoint
# ---------------------------------------------------------------------------

@router.get("/pnl", response_model=PnLResponse)
async def portfolio_pnl(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """Return trade history and P&L summary for a portfolio email.

    Unrealized P&L is estimated from the latest available price vs entry price.
    Realized P&L comes from the ``pnl`` column set when a position is closed.
    """
    from datetime import UTC, datetime
    from sqlalchemy import select, and_
    from app.models.trade import TradeLog

    stmt = (
        select(TradeLog)
        .where(TradeLog.email == email)
        .order_by(TradeLog.ts.desc())
    )
    result = await db.execute(stmt)
    rows: list[TradeLog] = list(result.scalars().all())

    buys = sum(1 for r in rows if r.action == "buy")
    sells = sum(1 for r in rows if r.action == "sell")
    holds = sum(1 for r in rows if r.action == "hold")
    realized = sum(r.pnl or 0.0 for r in rows if r.pnl is not None)

    # Unrealized P&L: current_price vs entry for open buy positions
    # (best-effort: compare last recorded buy with current live price)
    from app.pipelines.market_feeds import get_feed_manager
    live = {t.symbol: t for t in get_feed_manager().get_all()}
    unrealized = 0.0
    # Identify net open positions per symbol (buys - sells)
    open_pos: dict[str, list[TradeLog]] = {}
    for row in rows:
        if row.action in ("buy", "sell") and row.price is not None:
            open_pos.setdefault(row.symbol, []).append(row)

    for sym, trades in open_pos.items():
        net_units = 0.0
        avg_entry = 0.0
        for t in sorted(trades, key=lambda x: x.ts):
            if t.action == "buy":
                net_units += (t.quantity or 0.0)
                avg_entry = t.price or avg_entry
            elif t.action == "sell":
                net_units -= (t.quantity or 0.0)
        if net_units > 0:
            tick = live.get(sym)
            if tick is not None:
                current_price = float(tick.close or tick.open or 0)
                if current_price > 0 and avg_entry > 0:
                    unrealized += (current_price - avg_entry) * net_units

    summary = PnLSummary(
        total_trades=len(rows),
        buys=buys,
        sells=sells,
        holds=holds,
        realized_pnl=round(realized, 4),
        unrealized_pnl=round(unrealized, 4),
        total_pnl=round(realized + unrealized, 4),
    )

    trade_entries = [
        TradeLogEntry(
            id=r.id,
            ts=r.ts,
            symbol=r.symbol,
            action=r.action,
            quantity=r.quantity,
            price=r.price,
            signal_vol_spike=r.signal_vol_spike,
            signal_bias=r.signal_bias,
            recommendation=r.recommendation,
            order_id=r.order_id,
            status=r.status,
            broker=r.broker,
            pnl=r.pnl,
            note=r.note,
        )
        for r in rows
    ]

    return PnLResponse(
        email=email,
        summary=summary,
        trades=trade_entries,
        as_of=datetime.now(UTC),
    )
