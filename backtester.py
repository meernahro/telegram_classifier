import re
from datetime import datetime
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Message

class TelegramMessageClassifier:
    def __init__(self):
        # Key phrases indicating a listing
        self.exchange_phrases = {
            'Binance': ['Binance Will List', 'Binance Futures Will Launch', 'Introducing'],
            'Coinbase': ['Coinbase Will List', 'Coinbase will add support for', 'Assets added to the roadmap today'],
            'OKX': ['OKX to list', 'OKX will list', 'OKX announces the listing of'],
            'Bybit': ['Bybit to list', 'Bybit will list', 'Bybit announces the listing of'],
            'Upbit': ['Upbit Will List', 'Upbit announces the listing of'],
            'Bithumb': ['Bithumb Will List', 'Bithumb announces the listing of'],
        }

    def classify_message(self, message):
        for exchange, phrases in self.exchange_phrases.items():
            for phrase in phrases:
                if phrase.lower() in message.lower():
                    listing_info = self.extract_listing_info(exchange, message)
                    if listing_info:
                        return listing_info
        return None  # Not a listing announcement

    def extract_listing_info(self, exchange, message):
        # Normalize the message to lower case for consistent matching
        message_lower = message.lower()
        tokens = []
        market_type = 'Unknown'

        if exchange == 'Binance':
            tokens = self.extract_tokens_binance(message)
            market_type = self.determine_market_type_binance(message_lower)
        elif exchange == 'Coinbase':
            tokens = self.extract_tokens_coinbase(message)
            market_type = 'Spot'
        elif exchange == 'OKX':
            tokens = self.extract_tokens_generic(message, exchange)
            market_type = self.determine_market_type_okx(message_lower)
        elif exchange == 'Bybit':
            tokens = self.extract_tokens_generic(message, exchange)
            market_type = self.determine_market_type_bybit(message_lower)
        elif exchange == 'Upbit':
            tokens = self.extract_tokens_generic(message, exchange)
            market_type = 'Spot'
        elif exchange == 'Bithumb':
            tokens = self.extract_tokens_generic(message, exchange)
            market_type = 'Spot'
        else:
            return None  # Unknown exchange

        if tokens:
            # Remove duplicates
            tokens = list(set(tokens))
            return {'exchange': exchange, 'tokens': tokens, 'market': market_type, 'message': message}
        else:
            return None

    def extract_tokens_binance(self, message):
        tokens = []

        # Patterns to match tokens in Binance messages
        patterns = [
            r'Introducing\s+([^\s]+)\s+\((\w+)\)',
            r'Binance Will List\s+([^\s]+)\s+\((\w+)\)',
            r'Binance Futures Will Launch.*?(\w+) Perpetual Contract',
            r'Binance Futures Will Launch.*?(\w+USDT)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    tokens.extend(match)
                else:
                    tokens.append(match)
        return tokens

    def extract_tokens_coinbase(self, message):
        tokens = []

        # Patterns to match tokens in Coinbase messages
        patterns = [
            r'Assets added to the roadmap today:.*?\((\w+)\)',
            r'Coinbase will add support for\s+([^\s]+)\s+\((\w+)\)',
            r'Coinbase will add support for\s+(\w+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    tokens.extend(match)
                else:
                    tokens.append(match)
        return tokens

    def extract_tokens_generic(self, message, exchange):
        tokens = []

        # Patterns to match tokens in generic exchange messages
        patterns = [
            r'\b([A-Z0-9]{2,10})\b(?:\s+\([^\)]*\))?',  # Matches token symbols like ACT, FLOKI, etc.
            r'\$([A-Z0-9]{2,10})',  # Matches tokens prefixed with $
        ]
        for pattern in patterns:
            matches = re.findall(pattern, message)
            tokens.extend(matches)

        # Additional filtering to remove common words that are not tokens
        common_words = {'WILL', 'LIST', 'SPOT', 'FUTURES', 'TRADING', 'PERPETUAL', 'CONTRACT', 'LAUNCH', 'UPBIT', 'OKX', 'BYBIT'}
        tokens = [token for token in tokens if token.upper() not in common_words]

        return tokens

    def determine_market_type_binance(self, message_lower):
        if 'futures' in message_lower:
            return 'Futures'
        elif 'spot' in message_lower:
            return 'Spot'
        elif 'launchpool' in message_lower:
            return 'Launchpool'
        else:
            return 'Unknown'

    def determine_market_type_okx(self, message_lower):
        if 'spot trading' in message_lower:
            return 'Spot'
        elif 'perpetual' in message_lower or 'futures' in message_lower:
            return 'Futures'
        else:
            return 'Unknown'

    def determine_market_type_bybit(self, message_lower):
        if 'perpetual contract' in message_lower or 'futures' in message_lower:
            return 'Futures'
        elif 'spot' in message_lower:
            return 'Spot'
        else:
            return 'Unknown'

# Async function to backtest messages from a public Telegram channel
async def backtest_channel_messages(api_id, api_hash, channel_username, start_date):
    classifier = TelegramMessageClassifier()
    client = TelegramClient('session_name', api_id, api_hash)

    await client.start()
    print(f"Connected to Telegram as {await client.get_me()}")

    start_date = datetime.strptime(start_date, '%Y-%m-%d')

    messages = []
    classified_results = []

    async for message in client.iter_messages(channel_username, reverse=True, offset_date=start_date):
        if isinstance(message, Message) and message.text:
            msg_text = message.text.strip()
            messages.append(msg_text)
            result = classifier.classify_message(msg_text)
            if result:
                result['date'] = message.date.strftime('%Y-%m-%d %H:%M:%S')
                classified_results.append(result)

    await client.disconnect()

    # Output all messages and their classification (if any)
    for idx, msg in enumerate(messages, 1):
        print(f"Message {idx}:")
        print(msg)
        classification = classifier.classify_message(msg)
        if classification:
            print("Classification:")
            print(classification)
        else:
            print("No classification.")
        print("-" * 50)

    return classified_results

# Main function to run the async function
def run_backtester(api_id, api_hash, channel_username, start_date):
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(backtest_channel_messages(api_id, api_hash, channel_username, start_date))
    return results

if __name__ == "__main__":
    # Replace with your own Telegram API credentials
    api_id = '20230787'      # Replace with your actual API ID
    api_hash = '74fa79ff4aa438ccfbbc5be9254d7b1a'  # Replace with your actual API Hash

    # The public channel username
    channel_username = 'BWEnews'  # Replace with the actual channel username

    # Start date in 'YYYY-MM-DD' format
    start_date = '2024-11-1'    # Adjust the date as needed

    results = run_backtester(api_id, api_hash, channel_username, start_date)

    # Process the results
    print("\nClassified Listing Announcements:")
    for res in results:
        print(res)

