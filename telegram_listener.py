import asyncio
import logging
from datetime import datetime
from typing import Optional, List
import os
from dotenv import load_dotenv
import sys
import json
import traceback
from termcolor import colored

from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    ChannelPrivateError,
    UserDeactivatedError
)

from database import SessionLocal
import models
import crud
from utils import is_message_related_to_exchanges
from schemas import TokenCreate
from openai_client import OpenAIClient

# Load environment variables
load_dotenv()

class TelegramListener:
    def __init__(self):
        self.setup_logging()
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.session_name = 'data/telegram_session/telegram_session'
        self.client = None
        self.openai_client = OpenAIClient(os.getenv('OPENAI_API_KEY'))
        self.is_running = False

    def setup_logging(self):
        """Setup console logging with colors"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )

    def log_message(self, message: str, level: str = "info", extra_data: dict = None):
        """Formatted console logging"""
        colors = {
            "info": "green",
            "warning": "yellow",
            "error": "red",
            "debug": "blue"
        }
        
        # Format the message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} - {message}"
        if extra_data:
            log_message += f"\nDetails: {json.dumps(extra_data, indent=2, ensure_ascii=False)}"
        
        # Print with color
        print(colored(log_message, colors.get(level, "white")))

    async def handle_authentication(self):
        """Handle the complete Telegram authentication process"""
        try:
            if not await self.client.is_user_authorized():
                # Always ask for phone number
                phone = input('Please enter your phone number (with country code, e.g., +1234567890): ')
                
                # Send code request
                await self.client.send_code_request(phone)
                
                # Get verification code
                self.log_message("Verification code required", "info")
                verification_code = input('Please enter the verification code you received: ')
                
                try:
                    await self.client.sign_in(phone, verification_code)
                except SessionPasswordNeededError:
                    # Handle 2FA
                    self.log_message("2FA password required", "info")
                    password = input('Please enter your 2FA password: ')
                    await self.client.sign_in(password=password)
                
            self.log_message("Successfully authenticated with Telegram", "info")
            return True
            
        except Exception as e:
            self.log_message(f"Authentication error: {e}", "error")
            return False

    async def start(self):
        """Start the Telegram listener"""
        if self.is_running:
            return

        try:
            if not self.client:
                self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

            await self.client.connect()
            if not await self.handle_authentication():
                raise Exception("Authentication failed")

            # Get monitored channel usernames from database
            db = SessionLocal()
            channels = crud.get_all_channels(db)
            monitored_channels = [ch.name for ch in channels]  # Channel usernames like 'BWEnews'
            db.close()

            self.log_message(f"📋 Monitoring channels: {monitored_channels}", "info")
            self.is_running = True

            @self.client.on(events.NewMessage(chats=monitored_channels))
            async def handler(event):
                db = SessionLocal()
                try:
                    chat = await event.get_chat()
                    username = chat.username if hasattr(chat, 'username') else None
                    
                    if username:  # Only process if we can get the username
                        self.log_message(f"📨 New message from @{username}", "info")
                        await self.process_message(event, db)
                finally:
                    db.close()

            self.log_message("🚀 Telegram listener started successfully", "info")
            await self.client.run_until_disconnected()

        except Exception as e:
            self.log_message(f"❌ Error in Telegram listener: {str(e)}", "error")
            self.is_running = False
            raise

    async def stop(self):
        """Stop the Telegram listener"""
        if self.client:
            await self.client.disconnect()
            self.is_running = False
            self.log_message("Telegram listener stopped", "info")

    async def process_message(self, event, db: SessionLocal):
        """Process incoming messages"""
        try:
            message = event.message.message
            if not message:
                return

            self.log_message(
                "Message content preview:",
                "info",
                {"first_100_chars": message[:100]}
            )

            # Check for exchange names
            if not is_message_related_to_exchanges(message):
                return

            # Process with OpenAI
            self.log_message("🤖 Processing with OpenAI...", "info")
            tokens = self.openai_client.classify_message(message)
            
            # Log OpenAI's response
            self.log_message(
                "🤖 OpenAI Response:",
                "info",
                {"response": tokens}
            )
            
            if tokens:
                self.log_message(
                    "✅ Found token listing(s)!",
                    "info",
                    {"tokens": tokens}
                )
                
                # Save tokens
                for token_data in tokens:
                    token_create = TokenCreate(
                        token=token_data['token'],
                        exchange=token_data['exchange'],
                        market=token_data['market'],
                        timestamp=datetime.utcnow()
                    )
                    saved_token = crud.create_token(db, token_create)
                    self.log_message(f"💾 Saved token: {token_data['token']}", "info")
            else:
                self.log_message("❌ No tokens found in OpenAI response", "warning")
                    
        except Exception as e:
            self.log_message(
                f"❌ Error processing message: {str(e)}", 
                "error",
                {
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                    "traceback": traceback.format_exc()
                }
            )
