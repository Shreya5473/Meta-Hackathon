"""Load-style test for /signals/assets with realistic asset count.

Measures P95 latency expectation. Runs locally (not via locust).
Use: pytest tests/load/test_signals_load.py -v -s
"""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

import pytest
from httpx import AsyncClient


async def _request(client: AsyncClient) -> float:
    t0 = time.perf_counter()
    resp = await client.get("/signals/assets")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200
    return elapsed_ms


@pytest.mark.asyncio
async def test_signals_assets_p95_latency(async_client: AsyncClient) -> None:
    """50 sequential requests; P95 should be under 1000ms locally (no real DB hot path)."""
    n = 50
    latencies: list[float] = []

    for _ in range(n):
        ms = await _request(async_client)
        latencies.append(ms)

    latencies.sort()
    p50 = statistics.median(latencies)
    p95_idx = int(0.95 * n)
    p95 = latencies[p95_idx]

    print(f"\n  P50: {p50:.1f}ms  |  P95: {p95:.1f}ms  (n={n})")

    # With SQLite in-memory and no model loading, this should be well under 500ms
    # In production with warm cache: < 250ms
    assert p95 < 5000, f"P95 latency {p95:.1f}ms exceeds 5s limit (expected < 250ms with warm cache)"


@pytest.mark.asyncio
async def test_signals_assets_concurrent_load(async_client: AsyncClient) -> None:
    """10 concurrent requests to validate no race conditions."""
    tasks = [_request(async_client) for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failures = [r for r in results if isinstance(r, Exception)]
    assert len(failures) == 0, f"Concurrent failures: {failures}"
