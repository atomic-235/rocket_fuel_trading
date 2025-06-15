"""
Test configuration for integration tests using real .env file.
"""

import pytest
import asyncio
import os
from pathlib import Path

from trading_consumer.config import load_config, validate_config


# Remove the custom event_loop fixture to avoid deprecation warning
# pytest-asyncio will handle this automatically


@pytest.fixture(scope="session")
def config():
    """Load actual configuration from .env file."""
    # Look for .env file in project root
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        pytest.skip("No .env file found. Create one to run integration tests.")
    
    config = load_config(str(env_path))
    validate_config(config)
    return config


@pytest.fixture(scope="session")
async def telegram_client(config):
    """Create real Telegram client from config."""
    from trading_consumer.telegram import TelegramClient
    
    client = TelegramClient(config.telegram)
    await client.initialize()
    yield client
    await client.stop()


@pytest.fixture(scope="session")
async def exchange_client(config):
    """Create real exchange client from config."""
    from trading_consumer.trading import HyperliquidExchange
    
    exchange = HyperliquidExchange(config.hyperliquid)
    await exchange.initialize()
    yield exchange
    await exchange.close()


@pytest.fixture
def signal_parser():
    """Create real signal parser."""
    from trading_consumer.parsers import SignalParser
    return SignalParser()


@pytest.fixture
async def trading_consumer(config):
    """Create real trading consumer instance."""
    from trading_consumer.main import TradingConsumer
    
    consumer = TradingConsumer()
    await consumer.initialize()
    yield consumer
    await consumer.stop()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: integration tests requiring real services"
    )
    config.addinivalue_line(
        "markers", "telegram: tests requiring Telegram API access"
    )
    config.addinivalue_line(
        "markers", "exchange: tests requiring exchange API access"
    )
    config.addinivalue_line(
        "markers", "slow: slow running tests"
    ) 