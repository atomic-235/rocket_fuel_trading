# Trading Consumer

> 🚀 **Production-ready cryptocurrency trading automation system** that monitors Telegram channels for trading signals and executes trades on Hyperliquid DEX with comprehensive risk management.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/PyCQA/pylint)
[![Code style: flake8](https://img.shields.io/badge/code%20style-flake8-blue)](https://github.com/PyCQA/flake8)

## ✨ Features

### 🎯 **Core Capabilities**
- **Real-time Telegram Monitoring**: Uses `python-telegram-bot` for reliable message consumption
- **High-Accuracy Signal Parsing**: JSON-only parsing (90%+ accuracy) with no regex text parsing
- **Hyperliquid DEX Integration**: Full CCXT-based trading execution with leverage support
- **Comprehensive Risk Management**: Position sizing, TP/SL orders, daily loss limits
- **Production-Grade Architecture**: Async/await, error handling, graceful shutdown, structured logging

### 📊 **Trading Features**
- **Automated Trade Execution**: Market orders with automatic TP/SL placement
- **Dynamic Leverage Management**: Per-symbol leverage configuration (1x-100x)
- **Position Monitoring**: Real-time P&L tracking and position management
- **Symbol Mapping**: Automatic symbol conversion (e.g., PEPE → kPEPE for Hyperliquid)
- **Multi-Signal Support**: BUY/SELL/LONG/SHORT/CLOSE signal types

### 🛡️ **Risk Management**
- **Position Limits**: Maximum position size and open position count controls
- **Daily Loss Limits**: Automatic trading halt on daily loss thresholds
- **Confidence Filtering**: Minimum confidence thresholds for signal execution
- **User Access Control**: Whitelist-based Telegram user filtering

## 🏗️ Architecture

```
trading_consumer/
├── models/              # Pydantic data models
│   ├── config.py       # Configuration models
│   ├── trading.py      # Trading signal & order models
│   └── telegram.py     # Telegram message models
├── telegram/           # Telegram integration
│   ├── client.py       # Bot client & message handling
│   └── handlers.py     # Message processing handlers
├── trading/            # Exchange integration
│   └── exchange.py     # Hyperliquid CCXT implementation
├── parsers/            # Signal extraction
│   ├── signal_parser.py    # JSON signal parsing
│   └── pattern_matcher.py  # Pattern matching utilities
├── utils/              # Utilities
│   └── symbol_mapper.py    # Symbol mapping functions
├── config.py           # Configuration management
└── main.py            # Application entry point
```

## 🚀 Quick Start

### Prerequisites
- Amazon Linux 2023
- Python 3.9+
- Telegram Bot Token
- Hyperliquid wallet address and private key
- Access to target Telegram channel/chat

### Installation

#### Option 1: From GitHub Release (Recommended)
```bash
# Install latest release directly
pip install https://github.com/atomic-235/rocket_fuel_trading/archive/refs/tags/v0.0.1.tar.gz

# Or install with development dependencies
pip install "https://github.com/atomic-235/rocket_fuel_trading/archive/refs/tags/v0.0.1.tar.gz[dev]"
```

#### Option 2: From Source
```bash
# Clone the repository
git clone https://github.com/atomic-235/rocket_fuel_trading.git
cd rocket_fuel_trading

# Install the package
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Configuration

1. **Copy environment template**:
```bash
cp env.example .env
```

2. **Configure your settings**:
```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_IDS=your_target_chat_ids  # Comma-separated chat IDs
TELEGRAM_ALLOWED_USER_IDS=123456789  # Comma-separated user IDs
OWNER_TELEGRAM_ID=your_telegram_id_for_notifications

# Hyperliquid Configuration
HYPERLIQUID_API_ADDRESS=your_wallet_address
HYPERLIQUID_API_KEY=your_private_key
HYPERLIQUID_TESTNET=true  # Use testnet for development

# Trading Configuration
DEFAULT_POSITION_SIZE_USD=12    # USD amount per trade
DEFAULT_LEVERAGE=2              # Default leverage multiplier
DEFAULT_TP_PERCENT=0.05        # 5% take profit
DEFAULT_SL_PERCENT=0.02        # 2% stop loss
MIN_CONFIDENCE=0.7             # Minimum signal confidence
```

### Usage

```bash
# Run the trading consumer
trading-consumer

# Or run directly with Python
python -m trading_consumer.main

# Test connections before live trading
python scripts/test_connection.py
```

### 🚀 One-liner Setup & Run

For quick deployment on any Amazon Linux 2023 system:

```bash
sudo dnf update -y && sudo dnf install -y python3 python3-pip wget tar && \
wget https://github.com/atomic-235/rocket_fuel_trading/archive/refs/tags/v0.0.1.tar.gz && \
tar -xzf v0.0.1.tar.gz && \
cd rocket_fuel_trading-0.0.1 && \
python3 -m venv trading_env && \
./trading_env/bin/pip install -e . && \
mv env.example .env && \
echo "🚀 Setup complete! Starting trading consumer in background..." && \
nohup env TELEGRAM_BOT_TOKEN="your_bot_token" \
          TELEGRAM_CHAT_IDS="your_chat_ids" \
          HYPERLIQUID_API_KEY="your_private_key" \
          HYPERLIQUID_API_ADDRESS="your_wallet_address" \
          DEFAULT_POSITION_SIZE_USD="12" \
          ./trading_env/bin/python -m trading_consumer.main > trading.log 2>&1 &
```

**Check logs after setup:**
```bash
tail -f rocket_fuel_trading-0.0.1/trading.log
```

> **Note**: Replace `v0.0.1` with the latest release version from [GitHub Releases](https://github.com/atomic-235/rocket_fuel_trading/releases)

This will:
- Install all dependencies and create a virtual environment
- Create a `.env` file from the template
- Run in background with `nohup` (continues after session disconnect)
- Log output to `trading.log` file
- Return control to your terminal immediately

> **Note**: Amazon Linux 2023 uses `dnf` package manager by default

Replace the values:
- `your_bot_token` - Get from [@BotFather](https://t.me/BotFather)
- `your_chat_ids` - Comma-separated chat/channel IDs (e.g., "-1001234567890,-1009876543210")
- `your_private_key` - Your Hyperliquid private key
- `your_wallet_address` - **The wallet address used to create your API key** (truncated version shown in top-right corner of Hyperliquid)
- `12` - USD amount per trade (adjust as needed)

**Management commands:**
```bash
# Check if running
ps aux | grep trading_consumer

# View logs in real-time
tail -f rocket_fuel_trading-0.0.1/trading.log

# Stop the process
pkill -f trading_consumer.main

# Restart the service (from rocket_fuel_trading-0.0.1 directory)
cd rocket_fuel_trading-0.0.1 && \
nohup env TELEGRAM_BOT_TOKEN="your_bot_token" \
          TELEGRAM_CHAT_IDS="your_chat_ids" \
          HYPERLIQUID_API_KEY="your_private_key" \
          HYPERLIQUID_API_ADDRESS="your_wallet_address" \
          DEFAULT_POSITION_SIZE_USD="12" \
          ./trading_env/bin/python -m trading_consumer.main > trading.log 2>&1 &
```

## 📋 Configuration Reference

### Telegram Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | **Required** |
| `TELEGRAM_CHAT_IDS` | Comma-separated target chat/channel IDs | **Required** |
| `OWNER_TELEGRAM_ID` | Your Telegram ID for trade notifications | Optional |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated allowed user IDs | Optional |
| `TELEGRAM_ALLOWED_USERS` | Comma-separated allowed usernames | Optional |

### Trading Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_POSITION_SIZE_USD` | USD amount per trade | `12` |
| `DEFAULT_LEVERAGE` | Default leverage multiplier | `2` |
| `DEFAULT_TP_PERCENT` | Take profit percentage | `0.05` (5%) |
| `DEFAULT_SL_PERCENT` | Stop loss percentage | `0.02` (2%) |
| `MAX_POSITION_SIZE` | Maximum position size | `1000` |
| `MAX_LEVERAGE` | Maximum allowed leverage | `10` |
| `MAX_OPEN_POSITIONS` | Maximum concurrent positions | `5` |
| `MAX_DAILY_LOSS` | Daily loss limit (USD) | `500` |
| `MIN_CONFIDENCE` | Minimum signal confidence | `0.7` |

### Hyperliquid Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `HYPERLIQUID_API_ADDRESS` | **Wallet address used to create API key** (see truncated version in Hyperliquid top-right corner) | **Required** |
| `HYPERLIQUID_API_KEY` | Private key | **Required** |
| `HYPERLIQUID_TESTNET` | Use testnet | `true` |
| `HYPERLIQUID_TIMEOUT` | API timeout (seconds) | `30` |

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_telegram_chat.py -v
```

### Test Scripts
```bash
# Test Telegram connection
python scripts/test_connection.py

# Test market order execution
python scripts/test_market_order.py

# Test TP/SL order placement
python scripts/test_exchange_tp_sl.py
```

### Environment Management
```bash
# Switch to development environment (testnet)
python scripts/switch_env.py dev

# Switch to production environment (mainnet) and set variables
python scripts/switch_env.py prod --set

# Generate shell script to set environment variables
python scripts/switch_env.py dev --shell
source set_env_dev.sh

# List available environment files
python scripts/switch_env.py --list

# Create backup before switching
python scripts/switch_env.py prod --backup
```

## 📊 Signal Format

The system expects JSON-formatted trading signals in Telegram messages:

```json
{
  "trade_extractions": [{
    "ticker": "ETH",
    "direction": "long",
    "trade_type": "open",
    "entry_price": 2400.50,
    "take_profit": [2520.00, 2580.00],
    "stop_loss": 2350.00,
    "leverage": 3,
    "confidence": 0.85,
    "asset_name": "Ethereum"
  }]
}
```

### Signal Fields
- `ticker`: Trading symbol (automatically mapped to exchange format)
- `direction`: `"long"` or `"short"`
- `trade_type`: `"open"` or `"close"`
- `entry_price`: Entry price (optional, uses market price if not provided)
- `take_profit`: TP price or array of TP levels
- `stop_loss`: SL price
- `leverage`: Leverage multiplier (1-100)
- `confidence`: Signal confidence (0.0-1.0)

## 🔧 Development

### Code Style
```bash
# Linting and code quality
pylint trading_consumer/
flake8 trading_consumer/

# Import sorting
isort trading_consumer/

# Type checking
mypy trading_consumer/
```

### Architecture Principles
- **Type Safety**: Full Pydantic validation throughout
- **Async First**: All I/O operations are async
- **Error Resilience**: Comprehensive error handling with retries
- **Modularity**: Clean separation of concerns
- **Testability**: Real integration tests with mocking support

## 🛡️ Security Considerations

### API Keys
- Store all sensitive data in environment variables
- Never commit `.env` files to version control
- Use separate testnet/mainnet configurations
- Consider using secrets management for production

### Risk Management
- Always test with small position sizes first
- Use testnet for development and testing
- Monitor daily loss limits
- Implement circuit breakers for unexpected behavior

### Access Control
- Whitelist specific Telegram user IDs
- Monitor unauthorized access attempts
- Use separate bot tokens for different environments

## 📈 Production Deployment

### Environment Setup
```bash
# Create production environment
python -m venv venv-prod
source venv-prod/bin/activate
pip install -e .

# Set production configuration
cp env.example .env.prod
# Edit .env.prod with production values
```

### Process Management
```bash
# Using systemd (recommended)
sudo cp scripts/trading-consumer.service /etc/systemd/system/
sudo systemctl enable trading-consumer
sudo systemctl start trading-consumer

# Or using screen/tmux
screen -S trading-consumer
trading-consumer
```

### Monitoring
- Monitor log files: `tail -f trading_consumer.log`
- Set up alerts for critical errors
- Monitor position sizes and P&L
- Track daily loss limits

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit a pull request

### Development Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests before committing
pytest && pylint . && flake8 . && isort . && mypy .
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves substantial risk of loss. The authors and contributors are not responsible for any financial losses incurred through the use of this software. Always test thoroughly and never risk more than you can afford to lose.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/atomic-235/rocket_fuel_trading)
- **Documentation**: See `/docs` directory
- **Community**: [Discord/Telegram channel]

---

**Built with ❤️ for the Rocket Fuel crypto trading community** 