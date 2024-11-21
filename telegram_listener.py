import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import (
    AuthKeyUnregisteredError,
    ChannelPrivateError,
    FloodWaitError,
    SessionPasswordNeededError,
    UserDeactivatedError,
)
from termcolor import colored

import crud
import models
from database import SessionLocal
from openai_client import OpenAIClient
from schemas import TokenCreate
from utils import is_message_related_to_exchanges
from logging_config import setup_logging, logger

# Load environment variables
load_dotenv()


class TelegramListener:
    def __init__(self):
        self.logger = logger or setup_logging()
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.session_name = "data/telegram_session/telegram_session"
        self.client = None
        self.openai_client = OpenAIClient(os.getenv("OPENAI_API_KEY"))
        self.is_running = False

    def log_message(self, level: str, message: str):
        """Log a message with color and to file"""
        color_map = {
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
        }
        
        # Console output with color
        print(colored(f"{level}: {message}", color_map.get(level, "white")))
        
        # File logging
        if level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)

    async def handle_authentication(self):
        """Handle the complete Telegram authentication process"""
        try:
            if not await self.client.is_user_authorized():
                # Always ask for phone number
                phone = input(
                    "Please enter your phone number (with country code, e.g., +1234567890): "
                )

                # Send code request
                await self.client.send_code_request(phone)

                # Get verification code
                self.log_message("INFO", "Verification code required")
                verification_code = input(
                    "Please enter the verification code you received: "
                )

                try:
                    await self.client.sign_in(phone, verification_code)
                except SessionPasswordNeededError:
                    # Handle 2FA
                    self.log_message("INFO", "2FA password required")
                    password = input("Please enter your 2FA password: ")
                    await self.client.sign_in(password=password)

            self.log_message("INFO", "Successfully authenticated with Telegram")
            return True

        except Exception as e:
            self.log_message("ERROR", f"Authentication error: {e}")
            return False

    async def start(self):
        """Start the Telegram listener"""
        if self.is_running:
            return

        try:
            if not self.client:
                self.client = TelegramClient(
                    self.session_name, self.api_id, self.api_hash
                )

            await self.client.connect()
            if not await self.handle_authentication():
                raise Exception("Authentication failed")

            await self.update_monitored_channels()
            self.is_running = True

            self.log_message("INFO", "🚀 Telegram listener started successfully")
            await self.client.run_until_disconnected()

        except Exception as e:
            self.log_message("ERROR", f"❌ Error in Telegram listener: {str(e)}")
            self.is_running = False
            raise

    async def stop(self):
        """Stop the Telegram listener"""
        if self.client:
            await self.client.disconnect()
            self.is_running = False
            self.log_message("INFO", "Telegram listener stopped")

    async def process_message(self, event, db: SessionLocal):
        """Process incoming messages"""
        try:
            message = event.message.message
            if not message:
                return

            self.log_message("INFO", f"Message content preview: {message[:100]}")

            # Check for exchange names
            if not is_message_related_to_exchanges(message):
                return

            # Process with OpenAI
            self.log_message("INFO", "🤖 Processing with OpenAI...")
            tokens = self.openai_client.classify_message(message)

            # Log OpenAI's response
            self.log_message("INFO", f"🤖 OpenAI Response: {tokens}")

            if tokens:
                self.log_message("INFO", f"✅ Found token listing(s)! {tokens}")

                # Save tokens
                for token_data in tokens:
                    token_create = TokenCreate(
                        token=token_data["token"],
                        exchange=token_data["exchange"],
                        market=token_data["market"],
                        timestamp=datetime.utcnow(),
                    )
                    saved_token = crud.create_token(db, token_create)
                    self.log_message("INFO", f"💾 Saved token: {token_data['token']}")
            else:
                self.log_message("WARNING", "❌ No tokens found in OpenAI response")

        except Exception as e:
            self.log_message("ERROR", f"❌ Error processing message: {str(e)}")
            self.log_message("ERROR", f"❌ Error type: {type(e).__name__}")
            self.log_message("ERROR", f"❌ Error details: {str(e)}")
            self.log_message("ERROR", f"❌ Traceback: {traceback.format_exc()}")

    async def update_monitored_channels(self):
        """Update the list of monitored channels"""
        try:
            # Get monitored channel usernames from database
            db = SessionLocal()
            channels = crud.get_all_channels(db)
            
            # Get all dialogs (conversations) from Telegram
            dialogs = await self.client.get_dialogs()
            
            # Create a mapping of lowercase channel names to their actual names
            channel_map = {dialog.entity.username.lower(): dialog.entity.username 
                          for dialog in dialogs 
                          if hasattr(dialog.entity, 'username') and dialog.entity.username}
            
            # Match database channel names with actual Telegram channel names
            monitored_channels = []
            for ch in channels:
                if ch.name.lower() in channel_map:
                    monitored_channels.append(channel_map[ch.name.lower()])
            
            db.close()

            # Remove existing handler if it exists
            if hasattr(self, '_handler'):
                self.client.remove_event_handler(self._handler)

            # Set up new handler with updated channels
            @self.client.on(events.NewMessage(chats=monitored_channels))
            async def handler(event):
                db = SessionLocal()
                try:
                    chat = await event.get_chat()
                    username = chat.username if hasattr(chat, "username") else None

                    if username:  # Only process if we can get the username
                        self.log_message("INFO", f"📨 New message from @{username}")
                        await self.process_message(event, db)
                finally:
                    db.close()

            # Store reference to handler for future updates
            self._handler = handler
            
            self.log_message("INFO", f"📋 Now monitoring channels: {monitored_channels}")
            
        except Exception as e:
            self.log_message("ERROR", f"❌ Error updating monitored channels: {str(e)}")
            raise
