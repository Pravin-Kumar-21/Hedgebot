from email.mime import application
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime
import asyncio
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from dotenv import load_dotenv
from hedge_logger import log_hedge
from hedge_engine import execute_hedge
from data_fetcher import update_cache 
from greeks import calculate_greeks
from data_fetcher import update_cache, load_cached_data

# Make utils accessible even if you run from bot/

# Load .env variables
load_dotenv()

# Global dictionaries for active monitoring
active_monitors = {}
user_tasks = {}

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



async def hedge_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    asset = args[0].upper() if args else None

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

    # Filter by asset (if provided)
    if asset:
        history = [h for h in history if h.get("asset") == asset]

    if not history:
        await update.message.reply_text("📭 No hedge records found.")
        return

    # Show last 5 entries (most recent first)
    recent = history[-5:][::-1]  # Get last 5 and reverse order
    msg = f"📜 Hedge History {'for ' + asset if asset else ''}:\n\n"
    for h in recent:
        msg += (
            f"📌 {h.get('timestamp', 'Unknown time')}\n"
            f"• Asset: {h.get('asset', 'N/A')}\n"
            f"• Size: {h.get('size', 0):.4f}\n"
            f"• Price: ${h.get('price', 0):,.2f}\n"
            f"• Mode: {h.get('mode', 'N/A')}\n\n"
        )

    await update.message.reply_text(msg)


# ----------------------------- #
# Helper: Get latest price from cache
def get_latest_price(asset: str, source_priority=None):
    if source_priority is None:
        source_priority = ["bybit", "deribit", "coingecko"]

    try:
        if not os.path.exists(CACHE_FILE):
            logger.warning(f"Cache file not found: {CACHE_FILE}")
            return None
            
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        
        asset_data = data.get(asset.upper(), {})
        for source in source_priority:
            price = asset_data.get(source)
            if price:
                return float(price)
                
        logger.warning(f"No price found for {asset} in sources: {source_priority}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to load live data: {str(e)}", exc_info=True)
        return None

# ----------------------------- #
# /start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I am your Risk Monitoring Bot.\n"
        "Use /monitor_risk <asset> <size> <threshold> to get started.\n"
        "Use /stop_monitoring to stop active monitoring.\n"
        "Use /hedge_history [asset] to view hedge history."
    )

# /monitor_risk Command
async def monitor_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("❗ Usage: /monitor_risk <asset> <size> <threshold>\nExample: /monitor_risk BTC 1.5 50000")
        return

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

        # Create buttons with proper callback data
        keyboard = [
            [
                InlineKeyboardButton("💥 Hedge Now", callback_data=f"hedge_now|{asset}|{position_size}|{price}"),
                InlineKeyboardButton("⚙️ Adjust Threshold", callback_data=f"adjust_threshold|{asset}")
            ],
            [
                InlineKeyboardButton("📊 View Analytics", callback_data=f"view_analytics|{asset}")
            ]
        ]

        message = await update.message.reply_text(
            reply,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        # Stop existing monitoring if any
        if user_id in user_tasks:
            user_tasks[user_id].cancel()
            logger.info(f"Stopped previous monitoring for user {user_id}")

        # Store monitoring parameters
        active_monitors[user_id] = {
            "asset": asset,
            "size": position_size,
            "threshold": risk_threshold,
            "chat_id": chat_id
        }

        # Start new monitoring task
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
                if not data:
                    break
                    
                asset = data["asset"]
                size = data["size"]
                threshold = data["threshold"]
                chat_id = data["chat_id"]
                
                update_cache(asset)
                
                price = get_latest_price(asset)
                if price is None:
                    await asyncio.sleep(30)
                    continue

                exposure = price * size
                if exposure > threshold:
                    text = (
                        f"🚨 [Auto Alert] {asset} Risk Breach!\n"
                        f"📈 Price: ${price:,.2f}\n"
                        f"📉 Exposure: ${exposure:,.2f}\n"
                        f"❗ Threshold: ${threshold:,.2f}\n"
                        f"💥 Execution Auto: Hedging Now"
                    )
                    await context.bot.send_message(chat_id=chat_id, text=text)
                    
                    # Log auto hedge
                    log_hedge(asset, size, price, mode="auto")
                    
                    # Remove after alert to prevent spamming
                    if user_id in active_monitors:
                        active_monitors[user_id]["breached"] = True
                        logger.info(f"Risk breach detected for user {user_id}, but monitor preserved for updates.")
                    break

            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}", exc_info=True)
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
    except asyncio.CancelledError:
        logger.info(f"🛑 Monitoring cancelled for user {user_id}")
    finally:
        # Just stop the background loop, but preserve the monitor
        if user_id in user_tasks:
            del user_tasks[user_id]
        logger.info(f"⏹️ Monitoring loop ended for user {user_id}, monitor retained.")



# Stop monitoring command
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
        
        

# ----------------------------- #
# /threshold Command
async def threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Check if user has an active monitor
    if active_monitors[user_id].get("breached"):
      await update.message.reply_text("⚠️ Note: Previous risk was breached. Update your threshold or restart monitoring.")
    # Get arguments
    args = context.args
    if not args:
        await update.message.reply_text("❗ Usage: /threshold <new_value>\nExample: /threshold 60000")
        return

    try:
        # Parse and validate new threshold
        new_threshold = float(args[0])
        if new_threshold <= 0:
            await update.message.reply_text("❌ Threshold must be a positive number.")
            return
            
        # Update threshold in active monitor
        active_monitors[user_id]["threshold"] = new_threshold
        
        # Get current position details
        asset = active_monitors[user_id]["asset"]
        size = active_monitors[user_id]["size"]
        
        # Get current price for exposure calculation
        price = get_latest_price(asset)
        if price is None:
            await update.message.reply_text(f"⚠️ Could not fetch current price for {asset}.")
            return
            
        exposure = size * price
        
        # Create response message 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@
        response = (
            f"✅ Threshold updated to ${new_threshold:,.2f}\n\n"
            f"🧠 Updated monitoring for {asset}:\n"
            f"📦 Position Size: {size}\n"
            f"📈 Current Price: ${price:,.2f}\n"
            f"📉 Exposure: ${exposure:,.2f}\n"
        )
        
        # Add risk status
        if exposure > new_threshold:
            response += "🚨 Risk exceeds threshold!\n"
        else:
            response += "✅ Risk within safe threshold.\n"
            
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

    # Step 2: Get price and convert to float
    price_str = cached[asset].get("bybit") or cached[asset].get("deribit")
    if not price_str:
        await update.message.reply_text(f"⚠️ No live price available for {asset}.")
        return
    
    try:
        price = float(price_str)
    except (TypeError, ValueError):
        await update.message.reply_text(f"⚠️ Invalid price format for {asset}.")
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

# ----------------------------- #
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
        hedge_result = execute_hedge(asset, size, price)

        # FIXED: Use "manual" mode for user-initiated hedges
        log_hedge(asset, size, price, "manual")

        msg = (
            f"🚀 [Simulated] Hedge order executed!\n\n"
            f"• Asset: {hedge_result['asset']}\n"
            f"• Size: {hedge_result['size']}\n"
            f"• Original Price: ${hedge_result['original_price']:.2f}\n"
            f"• Execution Price: ${hedge_result['execution_price']:.2f}\n"
            f"• Slippage: {hedge_result['slippage_pct']:.2f}%\n"
            f"• Estimated Cost: ${hedge_result['cost']:.2f}\n"
        )
        await query.edit_message_text(msg)

    elif action == "adjust_threshold":
        user_id = query.from_user.id
        
        if user_id not in active_monitors:
            await query.edit_message_text(
                "⚠️ You don't have an active monitoring session.\n"
                "Please start monitoring first with /monitor_risk"
            )
            return
            
        current_threshold = active_monitors[user_id]["threshold"]
        
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
        
        if user_id in active_monitors:
            active_monitors[user_id]["threshold"] = new_threshold
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
            "<code>/threshold &lt;value&gt;</code>\n\n"
            "Example: <code>/threshold 75000</code>",
            parse_mode="HTML"
        )
        
        
    elif action == "view_analytics":
        # In a real bot, you would fetch analytics data here
        await query.edit_message_text(
            f"📊 Analytics for {asset}:\n\n"
            "• 24h Exposure: $1.2M\n"
            "• Risk Profile: Aggressive\n"
            "• Correlation: 0.87 with SP500\n\n"
            "🔒 VaR (95%): $45,000"
        )

# ----------------------------- #
# Main bot setup
def main():
    # Create application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("monitor_risk", monitor_risk))
    application.add_handler(CommandHandler("threshold", threshold))
    application.add_handler(CommandHandler("stop_monitoring", stop_monitoring))
    application.add_handler(CommandHandler("hedge_history", hedge_history)) 
    application.add_handler(CommandHandler("greeks", greeks_handler))
    application.add_handler(CommandHandler("greeks_auto", greeks_auto))

    # Add callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start bot
    logger.info("🚀 Bot is running... Press Ctrl+C to stop")
    application.run_polling()

# ----------------------------- #


if __name__ == "__main__":
    main()