"""Broker Connector Layer.

This package provides a pluggable interface for connecting GEOTRADE to
external brokers. Automatic trade execution is DISABLED by default and
requires explicit user authorization.

Available connectors:
    - AlpacaConnector  (paper + live, US stocks & crypto)
    - IBKRConnector    (Interactive Brokers, multi-asset — stub)

Usage (future):
    from app.connectors import get_connector
    broker = get_connector("alpaca")
    await broker.place_order(symbol="GLD", side="buy", qty=10)

Architecture:
    BaseBrokerConnector  ←  abstract interface
    AlpacaConnector      ←  Alpaca Markets implementation
    IBKRConnector        ←  Interactive Brokers stub
"""
from app.connectors.base import BaseBrokerConnector, OrderRequest, OrderResult

__all__ = ["BaseBrokerConnector", "OrderRequest", "OrderResult", "get_connector"]


def get_connector(name: str) -> BaseBrokerConnector:
    """Return a named broker connector instance.

    Args:
        name: "alpaca" | "ibkr"

    Raises:
        ValueError: If connector name is unknown or disabled.
    """
    from app.connectors.alpaca import AlpacaConnector
    from app.connectors.ibkr import IBKRConnector

    registry = {
        "alpaca": AlpacaConnector,
        "ibkr":   IBKRConnector,
    }
    cls = registry.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown broker connector: {name!r}. Available: {list(registry)}")
    return cls()
