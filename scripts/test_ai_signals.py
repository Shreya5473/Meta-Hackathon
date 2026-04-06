import asyncio
import os
import sys

# Add current directory to sys.path
sys.path.append(os.getcwd())

from app.pipelines.ai_signals.main_engine import get_ai_signals_engine
from app.pipelines.market_feeds import get_feed_manager

async def test_signals():
    print("🚀 Starting Signal Engine Test...")
    fm = get_feed_manager()
    
    # We need to set a dummy API key if not present to avoid RuntimeError
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.finnhub_api_key:
        print("⚠️ No Finnhub API key found, using synthetic fallback for test if enabled...")
        # For testing purposes, we'll mock the adapter if needed or just catch the error
    
    try:
        await fm.start()
        print(f"✅ Feed Manager started with {len(fm.symbols)} symbols")
        
        engine = get_ai_signals_engine()
        print("⌛ Generating signals (this may take a few seconds)...")
        signals = await engine.generate_all_signals()
        
        print(f"\n✨ Successfully generated {len(signals)} signals!")
        print("-" * 50)
        for s in signals[:10]:
            print(f"Asset: {s.symbol:10} | Signal: {s.recommendation:5} | Confidence: {s.confidence:5.1f}% | Vol: {s.volatility:7}")
        print("-" * 50)
        
        if len(signals) > 0:
            print("✅ Test PASSED")
        else:
            print("❌ Test FAILED: No signals generated")
            
    except Exception as e:
        print(f"❌ Test FAILED with error: {e}")
    finally:
        await fm.stop()
        print("🛑 Feed Manager stopped")

if __name__ == "__main__":
    asyncio.run(test_signals())
