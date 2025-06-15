# Trading Consumer

Independent trading consumer that reads Telegram messages and executes trades on Hyperliquid using CCXT.

## Features

- **Telegram Bot Integration**: Uses python-telegram-bot for reliable message consumption
- **Hyperliquid Trading**: CCXT-based trading execution on Hyperliquid DEX
- **Pydantic Models**: Type-safe data validation and serialization
- **Modular Architecture**: Decoupled components for easy testing and maintenance
- **Async/Await**: Full async support for high performance
- **Error Handling**: Robust error handling with retry mechanisms
- **Configuration**: Environment-based configuration management

## Architecture

```
trading_consumer/
├── models/          # Pydantic models for data validation
├── telegram/        # Telegram bot client and message handling
├── trading/         # Trading logic and exchange integration
├── parsers/         # Message parsing and signal extraction
├── config/          # Configuration management
└── utils/           # Utility functions and helpers
```

## Installation

```bash
pip install -e .
```

## Configuration

Create a `.env` file:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_target_chat_id

# Hyperliquid Configuration
HYPERLIQUID_API_KEY=your_api_key
HYPERLIQUID_SECRET=your_secret
HYPERLIQUID_TESTNET=true

# Trading Configuration
DEFAULT_POSITION_SIZE=100
MAX_POSITION_SIZE=1000
RISK_PERCENTAGE=0.02
```

## Usage

```bash
# Run the trading consumer
trading-consumer

# Or run directly with Python
python -m trading_consumer.main
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black trading_consumer/
isort trading_consumer/

# Type checking
mypy trading_consumer/
``` 