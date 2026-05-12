# 🚀 Spot Exposure Hedging Bot

An advanced **real-time crypto risk management and automated hedging system** built using **Python** and **Telegram Bot API**.

This project continuously monitors spot exposure, calculates portfolio risk metrics, computes option Greeks, performs stress testing, tracks PnL, and executes manual or automated hedging strategies when risk thresholds are breached.

The bot is designed as a lightweight yet powerful exposure hedging engine for crypto derivatives and spot trading systems.

---

# ✨ Features

## 📈 Real-Time Risk Monitoring

Monitor live exposure for crypto assets using:

- Position size
- Live spot prices
- Delta exposure
- Threshold-based alerts

### Exposure Formula

```python
Exposure = Position Size × Live Price
```

If:

```python
Exposure > Risk Threshold
```

Then the bot automatically alerts the user to hedge the position.

---

# 🤖 Automated Hedging Engine

Supports:

- ✅ Manual Hedging
- ✅ Auto Hedging
- ✅ Threshold-Based Hedging
- ✅ Delta Neutral Strategies
- ✅ Real-Time Notifications

The bot can automatically reduce exposure whenever portfolio risk exceeds the configured threshold.

---

# 🧮 Greeks Calculation Engine

The system calculates:

- Delta
- Gamma
- Theta
- Vega

Supports:

- Manual Greeks Calculation
- Automatic Greeks Calculation using live market data

Used for:

- Portfolio sensitivity analysis
- Options risk management
- Volatility tracking
- Exposure estimation

---

# 📊 Portfolio Analytics

Provides:

- Total Delta Exposure
- Portfolio Gamma
- Portfolio Theta
- Portfolio Vega
- Simulated VaR (Value at Risk)
- Risk Threshold Monitoring

---

# 📉 Stress Testing System

Simulates market crash scenarios including:

- Spot price drops
- Volatility spikes
- Time decay
- Combined stress conditions

Used for evaluating:

- Portfolio survivability
- Derivatives sensitivity
- Market shock impact

---

# 🔗 Correlation Engine

Calculates rolling correlation between exchanges.

Current implementation:

- Bybit vs Deribit Correlation

Useful for:

- Arbitrage analysis
- Portfolio diversification
- Market behavior analysis

---

# 💰 Real-Time PnL Tracking

Tracks:

- Entry Price
- Current Price
- Unrealized Profit/Loss
- PnL Percentage

---

# 📲 Telegram Bot Integration

Fully interactive Telegram bot with:

- Inline keyboard controls
- Real-time alerts
- Monitoring dashboard
- Automated hedge execution
- Portfolio analytics

Built using:

- `python-telegram-bot`
- Async Python
- Callback handlers
- Background monitoring tasks

---

# ⚙️ Supported Commands

| Command                                    | Description                 |
| ------------------------------------------ | --------------------------- |
| `/start`                                   | Start the bot               |
| `/monitor_risk <asset> <size> <threshold>` | Start monitoring risk       |
| `/view_dashboard`                          | View risk dashboard         |
| `/threshold <asset> <value>`               | Update threshold            |
| `/stop_monitoring`                         | Stop monitoring             |
| `/hedge_now <asset> <size>`                | Execute manual hedge        |
| `/auto_hedge`                              | Configure auto hedging      |
| `/hedge_status <asset>`                    | View hedge status           |
| `/hedge_history`                           | View hedge history          |
| `/greeks`                                  | Manual Greeks calculation   |
| `/greeks_auto <asset>`                     | Auto Greeks calculation     |
| `/portfolio_metrics`                       | View portfolio analytics    |
| `/correlation <asset>`                     | Compute rolling correlation |
| `/stress_test`                             | Run stress testing          |
| `/pnl_report`                              | View PnL report             |

---

# 🏗️ Project Architecture

```text
├── hedgebot
│   ├── bot
│   │   ├── correlation_engine.py
│   │   ├── greeks.py
│   │   ├── hedge_logger.py
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   ├── stress_tester.py
│   │   └── telegram_bot.py
│   ├── cache
│   │   ├── hedge_history.json
│   │   └── live_data.json
│   ├── data_fetcher.py
│   ├── hedge_engine.py
│   ├── logger.py
│   ├── logs
│   │   └── hedgebot.log
│   ├── __pycache__
│   ├── Readme.md
│   ├── requirements.txt
│   └── utils
│       ├── __init__.py
│       └── __pycache__
├── hedgebot.zip
├── log.txt
├── requirements.txt
└── venv
└── README.md
```

---

# 🧠 Core Components

## `telegrambot.py`

Main application controller.

Handles:

- Telegram commands
- Background monitoring loops
- Risk calculations
- Notifications
- Hedging execution
- Analytics

---

## `data_fetcher.py`

Responsible for:

- Fetching live market prices
- Updating cache
- Managing live data

---

## `hedge_engine.py`

Executes hedge operations.

Calculates:

- Execution price
- Slippage
- Estimated fees
- Effective hedge cost

---

## `hedge_logger.py`

Stores hedge execution history.

Tracks:

- Asset
- Size
- Price
- Hedge mode
- Timestamp

---

## `greeks.py`

Implements mathematical models for:

- Delta
- Gamma
- Theta
- Vega

Used for options risk calculations.

---

## `stress_tester.py`

Runs simulated stress scenarios.

Supports:

- Spot crashes
- Volatility spikes
- Time decay analysis

---

## `correlation_engine.py`

Computes rolling exchange correlations.

---

# 🔄 Auto Hedging Workflow

```python
if exposure > threshold:
    execute_hedge()
```

Workflow:

1. Monitor live exposure
2. Detect threshold breach
3. Trigger hedge execution
4. Send Telegram notification
5. Update portfolio metrics
6. Log hedge activity

---

# 📋 Dashboard Features

The dashboard provides:

- Live Spot Price
- Position Size
- Threshold Status
- Delta Exposure
- Greeks Analytics
- Simulated VaR
- Portfolio Risk Summary

---

# 📦 Example Usage

## Monitor ETH Risk

```bash
/monitor_risk ETH 1.5 8000
```

---

## Update Threshold

```bash
/threshold ETH 5000
```

---

## Execute Manual Hedge

```bash
/hedge_now ETH 0.5
```

---

## Configure Auto Hedge

```bash
/auto_hedge delta_neutral 10000
```

---

## Calculate Greeks Automatically

```bash
/greeks_auto ETH
```

---

## View Portfolio Metrics

```bash
/portfolio_metrics
```

---

## Run Stress Test

```bash
/stress_test ETH 2975 2975 0.35 7 call
```

---

# 🛠️ Technologies Used

## Backend

- Python

## Libraries

- python-telegram-bot
- asyncio
- pandas
- dotenv
- logging
- json

## Financial Concepts

- Spot Exposure Hedging
- Futures Hedging
- Options Pricing
- Greeks Calculations
- VaR Simulation
- Delta Neutral Strategies
- Correlation Analysis
- Stress Testing

---

# 📊 Sample Outputs

## 🚨 Risk Alert

```text
Risk exceeds threshold!
Suggested Action: Hedge Now
```

---

## ✅ Hedge Execution

```text
Hedge Executed Successfully

Asset: ETH
Size: 0.5
Price: $2972
Mode: Manual
```

---

## 📈 Greeks Output

```text
Delta: 0.52
Gamma: 0.14
Theta: -4.30
Vega: 0.25
```

---

# 🔐 Environment Variables

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

---

# ⚡ Installation

## Clone Repository

```bash
git clone https://github.com/Hedgebot
```

---

## Navigate to Project

```bash
cd Hedgebot
```

---

## Install Dependencies

```bash
python3.13 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
```

---

# ▶️ Run The Bot

```bash
python telegram_bot.py
```

---

---

# ▶️ Output Updates 
![alt text](https://github.com/Pravin-Kumar-21/Hedgebot/blob/update/Outputs/Screenshot%20From%202025-08-23%2004-19-52.png)
<br>
<br>


![alt text](https://github.com/Pravin-Kumar-21/Hedgebot/blob/update/Outputs/Screenshot%20From%202025-08-23%2004-20-03.png)
<br>
<br>


![alt text](https://github.com/Pravin-Kumar-21/Hedgebot/blob/update/Outputs/Screenshot%20From%202025-08-23%2004-20-16.png)
<br>
<br>


![alt text](https://github.com/Pravin-Kumar-21/Hedgebot/blob/update/Outputs/Screenshot%20From%202025-08-23%2004-20-34.png)
<br>
<br>


![alt text](https://github.com/Pravin-Kumar-21/Hedgebot/blob/update/Outputs/Screenshot%20From%202025-08-23%2004-20-52.png)
<br>
<br>


![alt text](https://github.com/Pravin-Kumar-21/Hedgebot/blob/update/Outputs/Screenshot%20From%202025-08-23%2004-21-39.png)
<br>
<br>

---




# 📈 Future Improvements

- Live exchange order execution
- Web dashboard
- Multi-asset portfolio optimization
- Machine learning hedge prediction
- WebSocket market feeds
- Cloud deployment
- Kubernetes scaling
- Real-time charting
- Advanced Black-Scholes pricing models

---

# 🔒 Disclaimer

This project is built for:

- Educational purposes
- Risk management simulations
- Exposure monitoring demonstrations

Do not use directly in live financial markets without proper testing and auditing.

---

# 👨‍💻 Author

## Pravin Kumar

---
