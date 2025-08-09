"""
Configuration fix for MongoDB and Telegram bot token.
This file overrides environment variables to fix configuration issues.
"""

import os
from pathlib import Path

# Load .env file first
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)
    print(f"✅ .env file loaded from {env_file}")
else:
    print(f"⚠️  .env file not found at {env_file}")

# Override the MongoDB URI to use the correct authentication source
# This must happen before any other modules are imported
# Using credentials from docker-compose-localhost.yml
os.environ['MONGODB_URI'] = 'mongodb://admin:admin@127.0.0.1:27017/instagram_telegram_chat?authSource=admin'

# Ensure Telegram bot token is properly set
telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
if telegram_token:
    print(f"Telegram bot token verified: {telegram_token[:10]}...{telegram_token[-10:]}")
    # Ensure the environment variable is set
    os.environ['TELEGRAM_BOT_TOKEN'] = telegram_token
else:
    print("⚠️  TELEGRAM_BOT_TOKEN not found in environment")

print("MongoDB URI overridden with correct authentication source")
print(f"New MONGODB_URI: {os.environ['MONGODB_URI']}")

# Verify the environment variables are set
print(f"Environment check - MONGODB_URI: {os.getenv('MONGODB_URI')}")
print(f"Environment check - TELEGRAM_BOT_TOKEN: {os.getenv('TELEGRAM_BOT_TOKEN')[:10] if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT SET'}...") 