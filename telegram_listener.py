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
from database import get_db_session
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
        self.channel_handlers = {}  # Store handlers for each channel

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
            self.log_message("WARNING", "🚫 Telegram listener is already running")
            return

        try:
            if not self.client:
                self.log_message("INFO", "🔄 Creating new Telegram client...")
                self.client = TelegramClient(
                    self.session_name, self.api_id, self.api_hash
                )

            self.log_message("INFO", "🔌 Connecting to Telegram...")
            await self.client.connect()
            
            if not await self.handle_authentication():
                raise Exception("Authentication failed")

            self.log_message("INFO", "🔄 Updating monitored channels...")
            await self.update_monitored_channels()
            
            self.is_running = True
            self.log_message("INFO", "🚀 Telegram listener started successfully")
            
            await self.client.run_until_disconnected()

        except Exception as e:
            self.log_message("ERROR", f"❌ Error in Telegram listener: {str(e)}")
            self.log_message("ERROR", f"❌ Traceback: {traceback.format_exc()}")
            self.is_running = False
            raise

    async def stop(self):
        """Stop the Telegram listener"""
        if self.client:
            await self.client.disconnect()
            self.is_running = False
            self.log_message("INFO", "Telegram listener stopped")

    async def process_message(self, event):
        """Process incoming messages"""
        try:
            message = event.message.message
            if not message:
                return

            self.log_message("INFO", f"Message content preview: {message[:100]}")

            # Use context manager for database session
            with get_db_session() as db:
                # Check for exchange names
                if not is_message_related_to_exchanges(db, message):
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
            with get_db_session() as db:
                channels = crud.get_all_channels(db)
                
                # Get channel entities and their IDs
                for channel in channels:
                    try:
                        entity = await self.client.get_entity(channel.name)
                        channel_id = entity.id
                        self.log_message("INFO", f"Channel {channel.name} has ID: {channel_id}")
                        
                        # Remove old handler if exists
                        if channel.name in self.channel_handlers:
                            self.client.remove_event_handler(self.channel_handlers[channel.name])
                            del self.channel_handlers[channel.name]
                        
                        # Create new handler for this channel
                        @self.client.on(events.NewMessage(chats=[channel_id]))
                        async def handler(event):
                            await self.process_message(event)
                        
                        # Store handler reference
                        self.channel_handlers[channel.name] = handler
                        
                    except Exception as e:
                        self.log_message("ERROR", f"Failed to get entity for channel {channel.name}: {str(e)}")

        except Exception as e:
            self.log_message("ERROR", f"Error updating monitored channels: {str(e)}")
            raise

    async def remove_channel_handler(self, channel_name: str):
        """Remove event handler for a specific channel"""
        if channel_name in self.channel_handlers:
            self.client.remove_event_handler(self.channel_handlers[channel_name])
            del self.channel_handlers[channel_name]
            self.log_message("INFO", f"Removed handler for channel: {channel_name}")
