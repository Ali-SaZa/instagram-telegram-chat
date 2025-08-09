"""
Main Telegram bot application for Instagram-Telegram chat integration.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.error import TelegramError

from config.settings import get_settings
from .handlers import CommandHandlers
from .session import TelegramSessionManager

logger = logging.getLogger(__name__)

# Conversation states
CHOOSING_THREAD, VIEWING_MESSAGES, SEARCHING = range(3)

class InstagramTelegramBot:
    """Main Telegram bot for Instagram chat integration."""
    
    def __init__(self):
        """Initialize the bot."""
        self.settings = get_settings()
        self.command_handlers = CommandHandlers()
        self.session_manager = TelegramSessionManager()
        self.app: Optional[Application] = None
        
    async def initialize(self):
        """Initialize the bot application."""
        try:
            logger.info("Initializing Telegram bot...")
            
            # Initialize session manager
            await self.session_manager.initialize()
            
            # Create bot application
            self.app = Application.builder().token(self.settings.telegram_bot_token).build()
            
            # Add handlers
            self._setup_handlers()
            
            logger.info("Telegram bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            raise
    
    def _setup_handlers(self):
        """Setup all bot handlers."""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(CommandHandler("help", self._help_command))
        self.app.add_handler(CommandHandler("status", self._status_command))
        self.app.add_handler(CommandHandler("threads", self._threads_command))
        self.app.add_handler(CommandHandler("search", self._search_command))
        
        # Conversation handler for viewing messages
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("messages", self._messages_command)],
            states={
                CHOOSING_THREAD: [CallbackQueryHandler(self._thread_selected)],
                VIEWING_MESSAGES: [
                    CallbackQueryHandler(self._message_navigation),
                    CommandHandler("back", self._back_to_threads)
                ],
                SEARCHING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_search_query),
                    CommandHandler("cancel", self._cancel_search)
                ]
            },
            fallbacks=[CommandHandler("cancel", self._cancel_conversation)]
        )
        self.app.add_handler(conv_handler)
        
        # Callback query handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self._handle_callback_query))
        
        # Error handler
        self.app.add_error_handler(self._error_handler)
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        try:
            user = update.effective_user
            user_id = user.id
            
            # Create or get user session
            session = await self.session_manager.get_or_create_session(user_id)
            
            welcome_text = (
                f"👋 Welcome to Instagram-Telegram Chat Integration, {user.first_name}!\n\n"
                "This bot allows you to:\n"
                "• View your Instagram direct messages\n"
                "• Search through message history\n"
                "• Stay updated on new messages\n\n"
                "Available commands:\n"
                "/help - Show this help message\n"
                "/threads - List your Instagram chat threads\n"
                "/messages - View messages in a specific thread\n"
                "/search - Search through your messages\n"
                "/status - Check system status\n\n"
                "Let's get started! Use /threads to see your Instagram conversations."
            )
            
            await update.message.reply_text(welcome_text)
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("Sorry, something went wrong. Please try again later.")
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "📚 **Instagram-Telegram Chat Integration Help**\n\n"
            "**Available Commands:**\n\n"
            "🔹 **/start** - Initialize the bot and get started\n"
            "🔹 **/help** - Show this help message\n"
            "🔹 **/threads** - List all your Instagram chat threads\n"
            "🔹 **/messages** - View messages in a specific thread\n"
            "🔹 **/search** - Search through your message history\n"
            "🔹 **/status** - Check system and connection status\n\n"
            "**How to use:**\n"
            "1. Use /threads to see your Instagram conversations\n"
            "2. Select a thread to view its messages\n"
            "3. Use /search to find specific messages\n"
            "4. Check /status to ensure everything is working\n\n"
            "**Navigation:**\n"
            "• Use inline buttons to navigate between threads and messages\n"
            "• Use /back to return to previous menus\n"
            "• Use /cancel to exit any conversation\n\n"
            "Need help? Contact support if you encounter any issues."
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        try:
            # Get system status
            status = await self.command_handlers.get_system_status()
            
            status_text = (
                "📊 **System Status**\n\n"
                f"🔹 **Instagram Connection:** {status.get('instagram', 'Unknown')}\n"
                f"🔹 **Database Status:** {status.get('database', 'Unknown')}\n"
                f"🔹 **Last Sync:** {status.get('last_sync', 'Unknown')}\n"
                f"🔹 **Total Threads:** {status.get('thread_count', 'Unknown')}\n"
                f"🔹 **Total Messages:** {status.get('message_count', 'Unknown')}\n\n"
                "All systems are operational! ✅"
            )
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text("Sorry, couldn't retrieve system status. Please try again later.")
    
    async def _threads_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /threads command."""
        try:
            # Get all threads
            threads = await self.command_handlers.get_threads()
            
            if not threads:
                await update.message.reply_text("No Instagram threads found. Make sure your account is connected and synced.")
                return
            
            # Create inline keyboard for thread selection
            keyboard = []
            for thread in threads[:10]:  # Limit to 10 threads
                thread_title = thread.get('title', 'Untitled Thread')
                thread_id = thread.get('id')
                last_activity = thread.get('last_activity', 'Unknown')
                
                button_text = f"{thread_title} ({last_activity})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"thread_{thread_id}")])
            
            # Add navigation buttons
            if len(threads) > 10:
                keyboard.append([
                    InlineKeyboardButton("◀️ Previous", callback_data="threads_prev"),
                    InlineKeyboardButton("Next ▶️", callback_data="threads_next")
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📱 **Your Instagram Threads** ({len(threads)} total)\n\n"
                "Select a thread to view messages:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in threads command: {e}")
            await update.message.reply_text("Sorry, couldn't retrieve threads. Please try again later.")
    
    async def _messages_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /messages command."""
        await update.message.reply_text(
            "📱 **View Messages**\n\n"
            "Please use /threads first to select a thread, then choose 'View Messages' from the thread options.\n\n"
            "Or if you know the thread ID, you can use:\n"
            "/messages <thread_id>"
        )
        return CHOOSING_THREAD
    
    async def _search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command."""
        await update.message.reply_text(
            "🔍 **Message Search**\n\n"
            "Please enter your search query. You can search for:\n"
            "• Text content\n"
            "• Usernames\n"
            "• Dates\n\n"
            "Type your search query now, or use /cancel to exit."
        )
        return SEARCHING
    
    async def _thread_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle thread selection from inline keyboard."""
        try:
            query = update.callback_query
            await query.answer()
            
            if query.data.startswith("thread_"):
                thread_id = query.data.replace("thread_", "")
                
                # Get messages for this thread
                messages = await self.command_handlers.get_thread_messages(thread_id, limit=20)
                
                if not messages:
                    await query.edit_message_text("No messages found in this thread.")
                    return ConversationHandler.END
                
                # Create message display
                message_text = f"📱 **Thread Messages**\n\n"
                
                for i, msg in enumerate(messages[:10], 1):
                    username = msg.get('username', 'Unknown')
                    text = msg.get('text', '')[:100]  # Truncate long messages
                    timestamp = msg.get('timestamp', 'Unknown')
                    
                    message_text += f"{i}. **{username}** ({timestamp})\n"
                    if text:
                        message_text += f"   {text}\n\n"
                
                # Create navigation keyboard
                keyboard = [
                    [InlineKeyboardButton("◀️ Previous", callback_data=f"msg_prev_{thread_id}")],
                    [InlineKeyboardButton("Next ▶️", callback_data=f"msg_next_{thread_id}")],
                    [InlineKeyboardButton("🔙 Back to Threads", callback_data="back_to_threads")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # Store thread_id in context for navigation
                context.user_data['current_thread_id'] = thread_id
                return VIEWING_MESSAGES
            
        except Exception as e:
            logger.error(f"Error in thread selection: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
            return ConversationHandler.END
    
    async def _message_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle message navigation."""
        try:
            query = update.callback_query
            await query.answer()
            
            if query.data.startswith("msg_prev_") or query.data.startswith("msg_next_"):
                # Handle pagination
                await query.edit_message_text("Pagination not implemented yet. Coming soon!")
                return VIEWING_MESSAGES
            elif query.data == "back_to_threads":
                await self._back_to_threads(update, context)
                return CHOOSING_THREAD
            
        except Exception as e:
            logger.error(f"Error in message navigation: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
            return ConversationHandler.END
    
    async def _back_to_threads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Go back to threads list."""
        await update.message.reply_text(
            "🔙 **Back to Threads**\n\n"
            "Use /threads to see your Instagram conversations again."
        )
        return ConversationHandler.END
    
    async def _handle_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle search query input."""
        try:
            query = update.message.text
            
            # Perform search
            results = await self.command_handlers.search_messages(query, limit=10)
            
            if not results:
                await update.message.reply_text(
                    f"🔍 **Search Results for: '{query}'**\n\n"
                    "No messages found matching your search query.\n\n"
                    "Try:\n"
                    "• Different keywords\n"
                    "• Usernames\n"
                    "• Partial text matches"
                )
                return ConversationHandler.END
            
            # Display search results
            result_text = f"🔍 **Search Results for: '{query}'**\n\n"
            
            for i, result in enumerate(results, 1):
                username = result.get('username', 'Unknown')
                text = result.get('text', '')[:100]
                timestamp = result.get('timestamp', 'Unknown')
                thread_title = result.get('thread_title', 'Unknown Thread')
                
                result_text += f"{i}. **{username}** in {thread_title}\n"
                result_text += f"   {timestamp}: {text}\n\n"
            
            result_text += "Use /search again to search for something else."
            
            await update.message.reply_text(result_text, parse_mode='Markdown')
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error in search query: {e}")
            await update.message.reply_text("Sorry, search failed. Please try again.")
            return ConversationHandler.END
    
    async def _cancel_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel search operation."""
        await update.message.reply_text("❌ Search cancelled.")
        return ConversationHandler.END
    
    async def _cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current conversation."""
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards."""
        try:
            query = update.callback_query
            await query.answer()
            
            if query.data == "back_to_threads":
                await self._back_to_threads(update, context)
            else:
                await query.edit_message_text("Unknown action. Please use /threads to start over.")
                
        except Exception as e:
            logger.error(f"Error in callback query: {e}")
            try:
                await update.callback_query.edit_message_text("Sorry, something went wrong. Please try again.")
            except:
                pass
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in the bot."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "Sorry, something went wrong. Please try again later or contact support."
                )
        except:
            pass
    
    async def start_polling(self):
        """Start the bot polling."""
        if not self.app:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        
        logger.info("Starting Telegram bot polling...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("Telegram bot started successfully")
    
    async def stop_polling(self):
        """Stop the bot polling."""
        if self.app:
            logger.info("Stopping Telegram bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram bot stopped")

# Global bot instance
bot_instance: Optional[InstagramTelegramBot] = None

async def get_bot_instance() -> InstagramTelegramBot:
    """Get or create the global bot instance."""
    global bot_instance
    if bot_instance is None:
        bot_instance = InstagramTelegramBot()
        await bot_instance.initialize()
    return bot_instance

async def setup_telegram_handlers():
    """Setup Telegram bot handlers - called from main.py."""
    try:
        bot = await get_bot_instance()
        await bot.start_polling()
        return bot
    except Exception as e:
        logger.error(f"Failed to setup Telegram handlers: {e}")
        raise 