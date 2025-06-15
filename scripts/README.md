# Hyperliquid Trading Test Scripts

This directory contains test scripts to verify all Hyperliquid trading functionality using the proper CCXT implementation.

## ⚠️ IMPORTANT WARNINGS

- **REAL MONEY**: Some tests can execute real trades with real money
- **SMALL AMOUNTS**: Tests use ~$10 USD positions (minimum order size)
- **TESTNET**: Make sure to use testnet for initial testing
- **BACKUP**: Always test with small amounts first

## Test Scripts

### 1. Connection Test (`test_connection.py`)
Tests basic connectivity and data fetching:
- Exchange initialization
- Balance fetching
- Ticker data (ETH price, mark price, etc.)
- Position fetching

```bash
python scripts/test_connection.py
```

### 2. Leverage Test (`test_leverage.py`)
Tests leverage and margin mode setting:
- Set different leverage levels (2x, 5x, 10x)
- Test cross margin mode
- Test isolated margin mode

```bash
python scripts/test_leverage.py
```

### 3. Limit Orders Test (`test_limit_orders.py`)
Tests limit order functionality:
- Create limit buy order (10% below market)
- Check order status
- Cancel order
- Verify cancellation

```bash
python scripts/test_limit_orders.py
```

### 4. Market Orders Test (`test_market_order.py`)
Tests market order execution (**REAL MONEY**):
- Create small market position (~$10 USD)
- Monitor position
- Auto-close position after 10 seconds

```bash
# Demo mode (safe)
python scripts/test_market_order.py

# Real money mode (DANGEROUS!)
python scripts/test_market_order.py --execute
```

### 5. TP/SL Orders Test (`test_tp_sl_orders.py`)
Tests Take Profit / Stop Loss functionality (**REAL MONEY**):
- Create position with TP/SL parameters
- Create separate TP/SL orders
- Monitor and close position
- Cancel remaining orders

```bash
# Demo mode (safe)
python scripts/test_tp_sl_orders.py

# Real money mode (DANGEROUS!)
python scripts/test_tp_sl_orders.py --execute
```

### 6. Run All Tests (`run_all_tests.py`)
Runs all tests in sequence with summary:

```bash
# Safe mode - no real trades
python scripts/run_all_tests.py

# Real money mode - executes actual trades
python scripts/run_all_tests.py --execute
```

## Configuration

Make sure your `.env` file is properly configured:

```env
# Hyperliquid Configuration
HYPERLIQUID_API_ADDRESS=your_wallet_address
HYPERLIQUID_API_KEY=your_private_key
HYPERLIQUID_TESTNET=true  # Set to false for mainnet
```

## Safety Features

1. **Demo Mode**: Most scripts run in demo mode by default
2. **Small Amounts**: Real trades use ~$10 USD (minimum order size)
3. **Auto-Close**: Market positions auto-close after monitoring
4. **Cancellation**: All remaining orders are cancelled
5. **Confirmation**: Real money trades have confirmation delays

## Expected Output

Each test provides detailed output:
- ✅ Success indicators
- ❌ Error indicators  
- 📊 Data displays (prices, balances, positions)
- ⏳ Progress indicators
- 🎯 Summary results

## Troubleshooting

1. **Connection Issues**: Check API credentials and network
2. **Balance Issues**: Ensure sufficient USDC balance
3. **Order Failures**: Check symbol format and market hours
4. **Permission Issues**: Verify API key has trading permissions

## Next Steps

After successful testing:
1. Integrate with signal parsing
2. Add risk management
3. Implement position sizing
4. Add monitoring and alerts
5. Deploy to production environment 