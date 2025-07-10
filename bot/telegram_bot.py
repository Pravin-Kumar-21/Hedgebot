from email.mime import application
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime
import asyncio
import json
import logging
logger = logging.getLogger("telegram")
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from dotenv import load_dotenv
from hedge_logger import get_hedge_history, log_hedge
from hedge_engine import execute_hedge
from data_fetcher import update_cache 
from greeks import calculate_greeks
from data_fetcher import update_cache, load_cached_data


# Load .env variables
load_dotenv()

# Global dictionaries for active monitoring
active_monitors = {}
user_tasks = {}

# Global dictionary for auto hedge configurations
auto_hedge_config = {}

# Logger setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from .env
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in .env file!")
    sys.exit(1)

# Ensure cache directory exists
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "live_data.json")
HEDGE_HISTORY_FILE = os.path.join(CACHE_DIR, "hedge_history.json")  # Fixed path


def get_max_price_from_asset_data(asset_data: dict) -> float:
    """Get the maximum price from available sources, handling both formats"""
    if not asset_data:
        return None
        
    # Handle both old and new formats
    prices = asset_data.get("latest", asset_data)
    
    sources = ["bybit", "deribit"]
    max_price = 0
    
    for source in sources:
        price_val = prices.get(source)
        if price_val:
            try:
                price_float = float(price_val)
                if price_float > max_price:
                    max_price = price_float
            except (TypeError, ValueError):
                continue
                
    return max_price if max_price > 0 else None


async def send_notification(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
    """Send real-time notification to user"""
    try:
        if user_id in active_monitors:
            chat_id = active_monitors[user_id]["chat_id"]
            await context.bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

# Enhanced hedge execution with notifications
async def execute_and_notify_hedge(context: ContextTypes.DEFAULT_TYPE, user_id: int, asset: str, size: float, mode: str = "manual"):
    """Execute hedge and send notifications with performance metrics"""
    try:
        price = get_latest_price(asset)
        if price is None:
            return None, "⚠️ Failed to fetch live price."

        # Execute hedge
        hedge_result = execute_hedge(asset, size, price)
        
        # Log and notify
        log_hedge(asset, size, price, mode)
        
        # Prepare performance metrics
        prev_exposure = None
        new_size = None
        new_exposure = None
        risk_reduction = None
        
        # Only calculate if we have active monitoring
        if user_id in active_monitors and asset in active_monitors[user_id]["assets"]:
            prev_exposure = active_monitors[user_id]["assets"][asset]["exposure"]
            new_size = active_monitors[user_id]["assets"][asset]["size"] - size
            new_exposure = new_size * price if new_size > 0 else 0
            risk_reduction = prev_exposure - new_exposure if prev_exposure else 0
        
        # Confirmation message
        confirmation_msg = (
            f"✅ Hedge Executed Successfully!\n\n"
            f"• Asset: {asset}\n"
            f"• Size: {size:.4f}\n"
            f"• Price: ${price:,.2f}\n"
            f"• Mode: {mode.capitalize()}\n"
            f"• Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        )
        
        if prev_exposure is not None:
            confirmation_msg += (
                f"\n📉 Risk Reduction: ${risk_reduction:,.2f}\n"
                f"📦 New Position: {new_size:.4f}"
            )
        
        # Cost analysis
        cost_msg = (
            f"💰 Cost Analysis\n\n"
            f"• Execution Price: ${hedge_result['execution_price']:,.2f}\n"
            f"• Slippage: {hedge_result['slippage_pct']:.2f}%\n"
            f"• Estimated Fees: ${hedge_result['cost']:,.2f}\n"
            f"• Effective Price: ${hedge_result['execution_price'] * (1 + hedge_result['slippage_pct']/100):,.2f}"
        )
        
        # Performance tracking
        perf_msg = ""
        if prev_exposure is not None:
            perf_msg = (
                f"📊 Performance Tracking\n\n"
                f"• Pre-Hedge Exposure: ${prev_exposure:,.2f}\n"
                f"• Post-Hedge Exposure: ${new_exposure:,.2f}\n"
                f"• Exposure Reduction: {risk_reduction/prev_exposure*100:.1f}%\n"
                f"• Cost/Reduction Ratio: {hedge_result['cost']/risk_reduction*100:.2f}%"
            )
        else:
            perf_msg = "📊 Performance Tracking: Position not monitored"
        
        # Send notifications
        await send_notification(context, user_id, confirmation_msg)
        await asyncio.sleep(1)
        await send_notification(context, user_id, cost_msg)
        await asyncio.sleep(1)
        await send_notification(context, user_id, perf_msg)
        
        # Update position size
        if user_id in active_monitors and asset in active_monitors[user_id]["assets"]:
            active_monitors[user_id]["assets"][asset]["size"] = new_size
            active_monitors[user_id]["assets"][asset]["exposure"] = new_exposure
            
        return hedge_result, None
    
    except Exception as e:
        logger.error(f"Hedge execution failed: {str(e)}")
        return None, f"❌ Hedge failed: {str(e)}"


async def auto_hedge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure automated hedging strategy"""
    args = context.args
    user_id = update.effective_user.id
    
    if not args:
        # Show current configuration
        config = auto_hedge_config.get(user_id, {})
        if not config:
            await update.message.reply_text("🤖 Auto Hedge: Not configured\n\n"
                                           "Usage: /auto_hedge <strategy> <threshold>\n"
                                           "Example: /auto_hedge delta_neutral 50000")
            return
        
        strategy = config.get("strategy", "Not set")
        threshold = config.get("threshold", "Not set")
        status = "✅ Active" if config.get("enabled", False) else "❌ Inactive"
        
        await update.message.reply_text(
            f"⚙️ Auto Hedge Configuration\n\n"
            f"• Strategy: {strategy}\n"
            f"• Threshold: ${threshold:,.2f}\n"
            f"• Status: {status}\n\n"
            f"Use '/auto_hedge enable' to activate\n"
            f"Use '/auto_hedge disable' to deactivate"
        )
        return
    
    # Handle enable/disable commands
    if args[0].lower() == "enable":
        if user_id not in auto_hedge_config:
            await update.message.reply_text("⚠️ Configure strategy first: /auto_hedge <strategy> <threshold>")
            return
            
        auto_hedge_config[user_id]["enabled"] = True
        await update.message.reply_text("✅ Auto hedging ENABLED")
        return
        
    if args[0].lower() == "disable":
        if user_id in auto_hedge_config:
            auto_hedge_config[user_id]["enabled"] = False
        await update.message.reply_text("🛑 Auto hedging DISABLED")
        return
    
    # Set new configuration
    if len(args) < 2:
        await update.message.reply_text("❗ Usage: /auto_hedge <strategy> <threshold>\n"
                                       "Example: /auto_hedge delta_neutral 50000")
        return
        
    try:
        strategy = args[0]
        threshold = float(args[1])
        
        auto_hedge_config[user_id] = {
            "strategy": strategy,
            "threshold": threshold,
            "enabled": True
        }
        
        await update.message.reply_text(
            f"🤖 Auto Hedge Configured\n\n"
            f"• Strategy: {strategy}\n"
            f"• Threshold: ${threshold:,.2f}\n"
            f"• Status: ✅ Active\n\n"
            f"Notifications will be sent for automated hedging actions."
        )
        
    except ValueError:
        await update.message.reply_text("❌ Threshold must be a valid number")


async def hedge_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current hedging status and performance"""
    args = context.args
    if not args:
        await update.message.reply_text("❗ Usage: /hedge_status <asset>\nExample: /hedge_status BTC")
        return
        
    asset = args[0].upper()
    user_id = update.effective_user.id
    
    # Check if asset is being monitored
    if user_id not in active_monitors or asset not in active_monitors[user_id]["assets"]:
        await update.message.reply_text(f"⚠️ No active monitoring for {asset}\nUse /monitor_risk first")
        return
        
    # Get current position data
    position = active_monitors[user_id]["assets"][asset]
    size = position["size"]
    threshold = position["threshold"]
    exposure = position.get("exposure", 0)
    
    # Get current price
    price = get_latest_price(asset)
    if not price:
        await update.message.reply_text(f"⚠️ Failed to fetch price for {asset}")
        return
        
    # Calculate status
    status = "🟢 Within Threshold" if exposure <= threshold else "🔴 Threshold Breached"
    
    # Get auto-hedge config
    auto_config = auto_hedge_config.get(user_id, {})
    auto_status = "✅ Enabled" if auto_config.get("enabled", False) else "❌ Disabled"
    auto_strategy = auto_config.get("strategy", "Not configured")
    
    # Prepare message
    msg = (
        f"📊 Hedging Status: {asset}\n\n"
        f"• Current Price: ${price:,.2f}\n"
        f"• Position Size: {size:.4f}\n"
        f"• Exposure: ${exposure:,.2f}\n"
        f"• Threshold: ${threshold:,.2f}\n"
        f"• Status: {status}\n\n"
        f"🤖 Auto Hedge:\n"
        f"• Status: {auto_status}\n"
        f"• Strategy: {auto_strategy}\n"
        f"• Threshold: ${auto_config.get('threshold', 'N/A')}"
    )
    
    await update.message.reply_text(msg)


async def hedge_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show historical hedging performance"""
    args = context.args
    asset = args[0].upper() if args else None
    timeframe = args[1].lower() if len(args) > 1 else "all"

    try:
        # Create file if it doesn't exist
        if not os.path.exists(HEDGE_HISTORY_FILE):
            with open(HEDGE_HISTORY_FILE, "w") as f:
                json.dump([], f)
                
        with open(HEDGE_HISTORY_FILE, "r") as f:
            history = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read hedge history: {e}")
        await update.message.reply_text("⚠️ Failed to load hedge history.")
        return

    # Show message if no records exist
    if not history:
        await update.message.reply_text("📭 No hedge records found.")
        return

    # Filter by asset if provided
    if asset:
        history = [h for h in history if h.get("asset") == asset.upper()]
    
    # If no records after asset filtering
    if not history:
        await update.message.reply_text(f"📭 No hedge records found for {asset}.")
        return

    # Apply timeframe filtering
    now = datetime.utcnow()
    filtered_history = []
    
    for record in history:
        try:
            # Parse ISO format timestamp: "2025-07-09T21:35:47.728181Z"
            timestamp_str = record["timestamp"]
            
            # Remove microseconds and 'Z' if present
            if '.' in timestamp_str:
                timestamp_str = timestamp_str.split('.')[0]
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1]
                
            # Parse the cleaned timestamp
            record_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            time_diff = now - record_time
            
            # Convert to total hours for more precise filtering
            total_hours = time_diff.total_seconds() / 3600
            
            if timeframe == "1d" and total_hours <= 24:
                filtered_history.append(record)
            elif timeframe == "2d" and total_hours <= 48:
                filtered_history.append(record)
            elif timeframe == "7d" and total_hours <= 168:  # 7*24
                filtered_history.append(record)
            elif timeframe == "30d" and total_hours <= 720:  # 30*24
                filtered_history.append(record)
            elif timeframe == "all":
                filtered_history.append(record)
        except (KeyError, ValueError) as e:
            logger.warning(f"Error parsing timestamp in record: {record} - {e}")
            continue

    # If no records after timeframe filtering
    if not filtered_history:
        time_msg = {
            "1d": "last 24 hours",
            "2d": "last 48 hours",
            "7d": "last 7 days",
            "30d": "last 30 days",
            "all": "all time"
        }.get(timeframe, timeframe)
        
        await update.message.reply_text(
            f"📭 No hedge records found for {asset or 'all assets'} in {time_msg}."
        )
        return

    # Sort by timestamp (newest first)
    filtered_history.sort(key=lambda x: datetime.strptime(
        x["timestamp"].split('.')[0].replace('Z', ''), "%Y-%m-%dT%H:%M:%S"
    ), reverse=True)

    # Show last 5 entries
    recent = filtered_history[:5]
    msg = f"📜 Hedge History{f' for {asset}' if asset else ''}:\n\n"
    
    for h in recent:
        # Format timestamp to be more readable
        raw_timestamp = h["timestamp"]
        formatted_time = raw_timestamp.replace('T', ' ').replace('Z', ' UTC').split('.')[0]
        
        msg += (
            f"📌 {formatted_time}\n"
            f"• Asset: {h.get('asset', 'N/A')}\n"
            f"• Size: {float(h.get('size', 0)):.4f}\n"
            f"• Price: ${float(h.get('price', 0)):,.2f}\n"
            f"• Mode: {h.get('mode', 'N/A')}\n\n"
        )

    # Add summary stats
    total_size = sum(float(h.get('size', 0)) for h in filtered_history)
    total_cost = sum(float(h.get('size', 0)) * float(h.get('price', 0)) * 0.002 for h in filtered_history)
    time_msg = {
        "1d": "last 24 hours",
        "2d": "last 48 hours",
        "7d": "last 7 days",
        "30d": "last 30 days",
        "all": "all time"
    }.get(timeframe, timeframe)
    
    msg += (
        f"📊 Summary ({time_msg}):\n"
        f"• Total Hedges: {len(filtered_history)}\n"
        f"• Total Size: {total_size:.4f}\n"
        f"• Est. Total Fees: ${total_cost:.2f}"
    )

    await update.message.reply_text(msg)


async def greeks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 5:
        await update.message.reply_text(
            "❗ Usage: /greeks <spot> <strike> <days_to_expiry> <volatility> <call|put>\n"
            "Example: /greeks 2000 2100 30 0.25 call"
        )
        return

    try:
        spot = float(args[0])
        strike = float(args[1])
        days = int(args[2])
        vol = float(args[3])
        opt_type = args[4].lower()

        result = calculate_greeks(
            spot_price=spot,
            strike_price=strike,
            time_to_expiry_days=days,
            volatility=vol,
            option_type=opt_type
        )

        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
            return

        msg = (
            f"📊 *Option Greeks* ({opt_type.upper()}):\n\n"
            f"• Spot Price: ${spot}\n"
            f"• Strike Price: ${strike}\n"
            f"• Days to Expiry: {days} days\n"
            f"• Volatility: {vol*100:.1f}%\n\n"
            f"🧮 Calculated Greeks:\n"
            f"• Delta: {result['delta']}\n"
            f"• Gamma: {result['gamma']}\n"
            f"• Theta: {result['theta']}\n"
            f"• Vega: {result['vega']}"
        )

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def view_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("📋 view_dashboard called")
        user_id = update.effective_user.id
        monitor = active_monitors.get(user_id)

        if not monitor or "assets" not in monitor:
            await update.message.reply_text("⚠️ No active monitoring found.\nUse /monitor_risk to start tracking.")
            return

        assets = monitor["assets"]
        cached = load_cached_data()
        logger.info(f"Cached data: {cached}")

        for asset, data in assets.items():
            size = data["size"]
            threshold = data["threshold"]
            asset_data = cached.get(asset.upper(), {})
            price = get_max_price_from_asset_data(asset_data)
          
            
            logger.info(f"[{asset}] Max price: {price}")

            if not price:
                await update.message.reply_text(f"⚠️ Failed to fetch live price for {asset}.")
                continue

            spot = round(price, 2)
            strike = round(price)
            days = 7
            volatility = 0.35

            greeks = calculate_greeks(spot, strike, days, volatility)
            logger.info(f"[{asset}] Greeks: {greeks}")

            delta_exposure = round(size * spot * greeks["delta"], 2)
            status = "✅ Within Threshold" if delta_exposure <= threshold else "🚨 Breached Threshold"

            msg = (
                f"📋 *Your Risk Dashboard* for *{asset}*\n\n"
                f"• Spot Price: ${spot}\n"
                f"• Position Size: {size}\n"
                f"• Risk Threshold: ${threshold:,.2f}\n"
                f"• Delta Exposure: ${delta_exposure:,.2f}\n"
                f"• Status: {status}\n\n"
                f"🧮 *Greeks* (7-day, 35% IV):\n"
                f"• Delta: {greeks['delta']}\n"
                f"• Gamma: {greeks['gamma']}\n"
                f"• Theta: {greeks['theta']}\n"
                f"• Vega: {greeks['vega']}\n\n"
                f"🔒 Simulated VaR: ${round(0.1 * delta_exposure, 2)}"
            )

            await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.exception("❌ Error in /view_dashboard")
        await update.message.reply_text(f"❗ Internal error: {e}")


async def portfolio_metrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    monitor = active_monitors.get(user_id)
    
    if not monitor or "assets" not in monitor:
        await update.message.reply_text("⚠️ No active portfolio found.\nUse /monitor_risk to start tracking.")
        return

    cached = load_cached_data()
    total_exposure = 0
    total_var = 0
    total_gamma = 0
    total_theta = 0
    total_vega = 0
    msg = "📊 Your Portfolio Risk Summary\n\n"

    for asset, info in monitor["assets"].items():
        size = info["size"]
        threshold = info["threshold"]

        asset_data = cached.get(asset, {})
        price = get_max_price_from_asset_data(asset_data)

        if not price:
            msg += f"⚠️ {asset}: Live price unavailable.\n\n"
            continue

        spot = round(price, 2)
        strike = round(price)
        days = 7
        volatility = 0.35

        # Calculate Greeks first
        greeks = calculate_greeks(spot, strike, days, volatility)
        delta = greeks["delta"]
        gamma = greeks["gamma"]
        theta = greeks["theta"]
        vega = greeks["vega"]
        
        # Add to total exposures (scaled by position size)
        total_gamma += gamma * size
        total_theta += theta * size
        total_vega += vega * size

        delta_exposure = round(size * spot * delta, 2)
        var = round(0.1 * delta_exposure, 2)
        status = "✅" if delta_exposure <= threshold else "🚨"

        msg += (
            f"{status} {asset}\n"
            f"• Size: {size} @ ${spot}\n"
            f"• Delta: {delta}, Exposure: ${delta_exposure:,.2f}\n"
            f"• Threshold: ${threshold:,.2f}, VaR: ${var:,.2f}\n\n"
        )

        total_exposure += delta_exposure
        total_var += var

    # Add portfolio Greeks after the loop
    msg += (
        f"📐 Portfolio Greeks:\n"
        f"• Gamma: {total_gamma:.4f}\n"
        f"• Theta: {total_theta:.2f}\n"
        f"• Vega: {total_vega:.2f}\n\n"
    )
    
    msg += (
        f"📦 Total Delta Exposure: ${total_exposure:,.2f}\n"
        f"🔒 Total VaR (Simulated): ${total_var:,.2f}"
    )

    await update.message.reply_text(msg)
    
    

# Get latest price from cache
def get_latest_price(asset: str, source_priority=None):
    if source_priority is None:
        source_priority = ["bybit", "deribit"]

    try:
        if not os.path.exists(CACHE_FILE):
            logger.warning(f"Cache file not found: {CACHE_FILE}")
            return None
            
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        
        asset_data = data.get(asset.upper(), {})
        if not asset_data:
            return None
            
        # Handle both old and new formats
        if "latest" in asset_data:
            prices = asset_data["latest"]
        else:
            prices = asset_data
            
        # Check sources in priority order
        for source in source_priority:
            price = prices.get(source)
            if price:
                return float(price)
                
        return None
        
    except Exception as e:
        logger.error(f"Failed to load live data: {str(e)}", exc_info=True)
        return None      
      

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I am your Risk Monitoring Bot.\n"
        "Use /monitor_risk <asset> <size> <threshold> to get started.\n"
        "Use /stop_monitoring to stop active monitoring.\n"
        "Use /hedge_history [asset] to view hedge history."
    )


async def monitor_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("❗ Usage: /monitor_risk <asset> <size> <threshold>\nExample: /monitor_risk BTC 1.5 50000")
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    asset, size_str, threshold_str = args
    
    try:
        position_size = float(size_str)
        risk_threshold = float(threshold_str)
        asset = asset.upper()
        
        update_cache(asset)
        price = get_latest_price(asset)
        if price is None:
            await update.message.reply_text(f"⚠️ Could not fetch live price for {asset}. Please try again later.")
            return

        exposure = position_size * price

        # Setup monitor storage
        if user_id not in active_monitors:
            active_monitors[user_id] = {
                "chat_id": chat_id,
                "assets": {}
            }

        # Add/Update specific asset
        active_monitors[user_id]["assets"][asset] = {
            "size": position_size,
            "threshold": risk_threshold,
            "exposure": exposure
        }

        reply = (
            f"🧠 Monitoring {asset}\n"
            f"📈 Price: ${price:,.2f}\n"
            f"📦 Position Size: {position_size}\n"
            f"📉 Delta Exposure: ${exposure:,.2f}\n\n"
        )

        if exposure > risk_threshold:
            reply += f"🚨 Risk exceeds threshold ${risk_threshold:,.2f}\n❗ Suggested Action: Hedge Now"
        else:
            reply += "✅ Risk within safe threshold."

        keyboard = [
            [
                InlineKeyboardButton("💥 Hedge Now", callback_data=f"hedge_now|{asset}|{position_size}|{price}"),
                InlineKeyboardButton("⚙️ Adjust Threshold", callback_data=f"adjust_threshold|{asset}")
            ],
            [
                InlineKeyboardButton("📊 View Analytics", callback_data=f"view_analytics|{asset}")
            ]
        ]

        await update.message.reply_text(reply, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Stop existing monitoring loop
        if user_id in user_tasks:
            user_tasks[user_id].cancel()
            logger.info(f"Stopped previous monitoring for user {user_id}")

        # Start monitoring loop
        task = asyncio.create_task(risk_monitor_loop(user_id, context))
        user_tasks[user_id] = task
        logger.info(f"Started monitoring for user {user_id}")

    except ValueError:
        await update.message.reply_text("❗ Invalid input. Size and threshold must be numbers.\nExample: /monitor_risk BTC 1.5 50000")


# Risk monitoring background task
async def risk_monitor_loop(user_id, context):
    logger.info(f"🔁 Starting monitoring loop for user {user_id}")

    try:
        while user_id in active_monitors:
            try:
                data = active_monitors.get(user_id)
                if not data or "assets" not in data:
                    break

                chat_id = data["chat_id"]
                for asset, info in data["assets"].items():
                    size = info["size"]
                    threshold = info["threshold"]

                    update_cache(asset)
                    price = get_latest_price(asset)
                    if price is None:
                        logger.warning(f"No price for {asset}")
                        continue
                      
                    exposure = price * size
                    # Update exposure in monitor
                    active_monitors[user_id]["assets"][asset]["exposure"] = exposure

                    if exposure > threshold:
                        text = (
                            f"🚨 [Auto Alert] {asset} Risk Breach!\n"
                            f"📈 Price: ${price:,.2f}\n"
                            f"📉 Exposure: ${exposure:,.2f}\n"
                            f"❗ Threshold: ${threshold:,.2f}\n"
                        )
                        
                        auto_config = auto_hedge_config.get(user_id, {})
                        if auto_config.get("enabled", False) and exposure > auto_config.get("threshold", float('inf')):
                            # Auto-hedge logic
                            hedge_size = min(size, (exposure - auto_config["threshold"]) / price)
                            if hedge_size > 0:
                                # Execute hedge with notifications
                                await execute_and_notify_hedge(
                                    context, 
                                    user_id, 
                                    asset, 
                                    hedge_size, 
                                    "auto"
                                )
                                
                                # Notify about auto-hedge
                                await send_notification(
                                    context,
                                    user_id,
                                    f"🤖 AUTO-HEDGE TRIGGERED!\n\n"
                                    f"• Asset: {asset}\n"
                                    f"• Strategy: {auto_config['strategy']}\n"
                                    f"• Size: {hedge_size:.4f}\n"
                                    f"• Threshold: ${auto_config['threshold']:,.2f}"
                                )
                        else:
                            text += "💥 Suggested Action: Hedge Now"
                            
                        await context.bot.send_message(chat_id=chat_id, text=text)

                await asyncio.sleep(30)  # Wait before next loop

            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(30)

    except asyncio.CancelledError:
        logger.info(f"🛑 Monitoring cancelled for user {user_id}")
    finally:
        if user_id in user_tasks:
            del user_tasks[user_id]
        logger.info(f"⏹️ Monitoring loop ended for user {user_id}")


async def stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_tasks:
        # Cancel the monitoring task
        user_tasks[user_id].cancel()
        del user_tasks[user_id]
        
        # Remove from active monitors
        if user_id in active_monitors:
            del active_monitors[user_id]
        
        await update.message.reply_text("🛑 Monitoring stopped.")
    else:
        await update.message.reply_text("⚠️ No active monitoring to stop.")


async def hedge_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger hedging action with immediate feedback"""
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❗ Usage: /hedge_now <asset> <size>\nExample: /hedge_now BTC 0.5")
        return
        
    asset = args[0].upper()
    try:
        size = float(args[1])
    except ValueError:
        await update.message.reply_text("❌ Size must be a valid number")
        return
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Immediate response that hedge is being processed
    processing_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔄 Processing manual hedge for {asset}, size: {size}..."
    )
    
    # Check if position exists
    warning = ""
    if user_id in active_monitors and asset in active_monitors[user_id]["assets"]:
        current_size = active_monitors[user_id]["assets"][asset]["size"]
        if size > current_size:
            warning = f"⚠️ Warning: Hedging more ({size}) than current position ({current_size})\n"
    
    try:
        # Execute hedge with notifications
        _, error = await execute_and_notify_hedge(context, user_id, asset, size, "manual")
        
        if error:
            await processing_msg.edit_text(f"❌ Hedge failed: {error}")
        else:
            # Success confirmation
            price = get_latest_price(asset)
            if price:
                exposure_reduction = size * price
                await processing_msg.edit_text(
                    f"✅ Manual Hedge Executed!\n\n"
                    f"{warning}"
                    f"• Asset: {asset}\n"
                    f"• Size: {size}\n"
                    f"• Price: ${price:,.2f}\n"
                    f"• Exposure Reduced: ${exposure_reduction:,.2f}\n\n"
                    f"📊 View updated position with /hedge_status {asset}"
                )
            else:
                await processing_msg.edit_text(
                    f"✅ Hedge executed!\n\n"
                    f"{warning}"
                    f"• Asset: {asset}\n"
                    f"• Size: {size}\n\n"
                    f"📊 View updated position with /hedge_status {asset}"
                )
                
    except Exception as e:
        logger.error(f"Hedge failed: {str(e)}")
        await processing_msg.edit_text(f"❌ Critical error during hedge: {str(e)}")


async def threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("❗ Usage: /threshold <asset> <new_value>\nExample: /threshold BTC 60000")
        return

    if len(args) < 2:
        await update.message.reply_text("❗ Usage: /threshold <asset> <new_value>\nExample: /threshold BTC 60000")
        return

    asset = args[0].upper()
    new_threshold_str = args[1]

    try:
        # Parse and validate new threshold
        new_threshold = float(new_threshold_str)
        if new_threshold <= 0:
            await update.message.reply_text("❌ Threshold must be a positive number.")
            return
            
        # Update threshold in active monitor
        if user_id in active_monitors and asset in active_monitors[user_id]["assets"]:
            active_monitors[user_id]["assets"][asset]["threshold"] = new_threshold
        
        # Get current position details
        if user_id in active_monitors and asset in active_monitors[user_id]["assets"]:
            size = active_monitors[user_id]["assets"][asset]["size"]
            exposure = active_monitors[user_id]["assets"][asset].get("exposure", 0)
            
            response = (
                f"✅ Threshold updated to ${new_threshold:,.2f} for {asset}\n\n"
                f"🧠 Updated monitoring:\n"
                f"📦 Position Size: {size}\n"
                f"📉 Exposure: ${exposure:,.2f}\n"
            )
            
            # Add risk status
            if exposure > new_threshold:
                response += "🚨 Risk exceeds threshold!\n"
            else:
                response += "✅ Risk within safe threshold.\n"
        else:
            response = f"✅ Threshold updated to ${new_threshold:,.2f} for {asset}"
            
        await update.message.reply_text(response)
        logger.info(f"User {user_id} updated threshold to {new_threshold} for {asset}")

    except ValueError:
        await update.message.reply_text("❌ Invalid threshold value. Please enter a valid number.")


async def greeks_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❗ Usage: /greeks_auto <asset>\nExample: /greeks_auto ETH")
        return

    asset = args[0].upper()

    # Step 1: Fetch real-time data
    update_cache(asset)
    cached = load_cached_data()
    if not cached or asset not in cached:
        await update.message.reply_text(f"⚠️ Failed to fetch live data for {asset}.")
        return

    # Step 2: Get max price
    asset_data = cached.get(asset, {})
    price = get_max_price_from_asset_data(asset_data)

    if not price:
        await update.message.reply_text(f"⚠️ No live price available for {asset}.")
        return

    # Step 3: Set default assumptions
    spot = round(price, 2)
    strike = round(price)  # ATM strike
    days = 7
    volatility = 0.35  # 35% implied volatility
    option_type = "call"
    risk_free_rate = 0.05  # 5% risk-free rate

    # Add detailed logging
    logger.info(f"Calculating Greeks for {asset}: spot={spot}, strike={strike}, "
              f"days={days}, vol={volatility}, rate={risk_free_rate}")

    # Step 4: Calculate Greeks with proper parameters
    greeks = calculate_greeks(
        spot_price=spot,
        strike_price=strike,
        time_to_expiry_days=days,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        option_type=option_type
    )

    # Enhanced error handling
    if "error" in greeks:
        error_msg = greeks.get("error", "Unknown calculation error")
        logger.error(f"Greek calculation failed for {asset}: {error_msg}")
        await update.message.reply_text(
            f"⚠️ Failed to calculate Greeks for {asset}:\n\n{error_msg}"
        )
        return
    elif not all(key in greeks for key in ['delta', 'gamma', 'theta', 'vega']):
        logger.error(f"Malformed greeks response for {asset}: {greeks}")
        await update.message.reply_text(
            f"⚠️ Received incomplete Greek data for {asset}. Please check logs."
        )
        return

    # Format success message
    msg = (
        f"📊 Option Greeks (Auto - CALL):\n\n"
        f"• Spot Price: ${spot}\n"
        f"• Strike Price (ATM): ${strike}\n"
        f"• Days to Expiry: {days} days\n"
        f"• Volatility: {volatility*100:.1f}%\n"
        f"• Risk-Free Rate: {risk_free_rate*100:.1f}%\n\n"
        f"🧮 Calculated Greeks:\n"
        f"• Delta: {greeks['delta']}\n"
        f"• Gamma: {greeks['gamma']}\n"
        f"• Theta: {greeks['theta']}\n"
        f"• Vega: {greeks['vega']}"
    )
    await update.message.reply_text(msg)


# Handle button callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Important to prevent loading indicators
    
    data = query.data
    parts = data.split('|')
    action = parts[0]
    asset = parts[1]
    
    if action == "hedge_now":
        size = float(parts[2])
        price = float(parts[3])
        user_id = query.from_user.id
        
        # Execute hedge with notifications
        _, error = await execute_and_notify_hedge(context, user_id, asset, size, "manual")
        if error:
            await query.edit_message_text(error)
        else:
            await query.edit_message_text("✅ Manual hedge executed successfully!")

    elif action == "adjust_threshold":
        user_id = query.from_user.id
        
        if user_id not in active_monitors or asset not in active_monitors[user_id]["assets"]:
            await query.edit_message_text(
                "⚠️ You don't have an active monitoring session for this asset.\n"
                "Please start monitoring first with /monitor_risk"
            )
            return
            
        current_threshold = active_monitors[user_id]["assets"][asset]["threshold"]
        
        # Create a new keyboard with threshold adjustment options
        keyboard = [
            [
                InlineKeyboardButton("+10%", callback_data=f"threshold_adjust|{asset}|{current_threshold}|1.1"),
                InlineKeyboardButton("-10%", callback_data=f"threshold_adjust|{asset}|{current_threshold}|0.9")
            ],
            [
                InlineKeyboardButton("+25%", callback_data=f"threshold_adjust|{asset}|{current_threshold}|1.25"),
                InlineKeyboardButton("-25%", callback_data=f"threshold_adjust|{asset}|{current_threshold}|0.75")
            ],
            [
                InlineKeyboardButton("Custom...", callback_data=f"threshold_custom|{asset}")
            ]
        ]
        
        await query.edit_message_text(
            f"⚙️ Adjust risk threshold for {asset}\n"
            f"Current threshold: ${current_threshold:,.2f}\n\n"
            "Choose an adjustment:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif action == "threshold_adjust":
        # Handle percentage-based adjustments
        _, asset, current_threshold_str, multiplier_str = parts
        current_threshold = float(current_threshold_str)
        multiplier = float(multiplier_str)
        
        new_threshold = current_threshold * multiplier
        user_id = query.from_user.id
        
        if user_id in active_monitors and asset in active_monitors[user_id]["assets"]:
            active_monitors[user_id]["assets"][asset]["threshold"] = new_threshold
            await query.edit_message_text(
                f"✅ Threshold updated to ${new_threshold:,.2f}\n\n"
                f"New value is {multiplier*100:.0f}% of previous threshold."
            )
            logger.info(f"User {user_id} updated threshold to {new_threshold} for {asset}")
        else:
            await query.edit_message_text("⚠️ Monitoring session expired. Please start a new session.")
            
    elif action == "threshold_custom":
        # Prompt for custom threshold value
        await query.edit_message_text(
            f"✏️ Enter new threshold value for {asset}:\n\n"
            "Send message in format:\n"
            "<code>/threshold {asset} &lt;value&gt;</code>\n\n"
            "Example: <code>/threshold BTC 75000</code>",
            parse_mode="HTML"
        )
        
    elif action == "view_analytics":
        user_id = query.from_user.id
        if user_id not in active_monitors or asset not in active_monitors[user_id]["assets"]:
            await query.edit_message_text("⚠️ No active monitoring found for this asset.")
            return

        size = active_monitors[user_id]["assets"][asset]["size"]
        threshold = active_monitors[user_id]["assets"][asset]["threshold"]
        cached = load_cached_data()

        asset_data = cached.get(asset, {})
        price = get_max_price_from_asset_data(asset_data)

        if not price:
            await query.edit_message_text(f"⚠️ Failed to fetch live price for {asset}.")
            return

        spot = round(price, 2)
        strike = round(price)
        days = 7
        volatility = 0.35

        greeks = calculate_greeks(spot, strike, days, volatility)

        delta_exposure = round(size * spot * greeks["delta"], 2)
        status = "✅ Within Threshold" if delta_exposure <= threshold else "🚨 Breached Threshold"

        # Start building the message
        msg = (
            f"📊 Real-Time Risk Analytics for {asset}\n\n"
            f"• Spot Price: ${spot}\n"
            f"• Position Size: {size}\n"
            f"• Threshold: ${threshold:,.2f}\n\n"
            f"🧮 Greeks (7-day, 35% IV):\n"
            f"• Delta: {greeks['delta']}\n"
            f"• Gamma: {greeks['gamma']}\n"
            f"• Theta: {greeks['theta']}\n"
            f"• Vega: {greeks['vega']}\n\n"
            f"📉 Delta Exposure: ${delta_exposure:,.2f}\n"
            f"• Status: {status}\n\n"
            f"🔒 VaR (Simulated): ${round(0.1 * delta_exposure, 2)}\n"
        )

        await query.edit_message_text(msg)


# Main bot setup
def main():
    # Create application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("monitor_risk", monitor_risk))
    application.add_handler(CommandHandler("view_dashboard", view_dashboard))
    application.add_handler(CommandHandler("threshold", threshold))
    application.add_handler(CommandHandler("stop_monitoring", stop_monitoring))
    application.add_handler(CommandHandler("hedge_now", hedge_now))
    application.add_handler(CommandHandler("greeks", greeks_handler))
    application.add_handler(CommandHandler("greeks_auto", greeks_auto))
    application.add_handler(CommandHandler("portfolio_metrics", portfolio_metrics))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("auto_hedge", auto_hedge))
    application.add_handler(CommandHandler("hedge_status", hedge_status))
    application.add_handler(CommandHandler("hedge_history", hedge_history))

    # Start bot
    logger.info("🚀 Bot is running... Press Ctrl+C to stop")
    application.run_polling()


if __name__ == "__main__":
    main()