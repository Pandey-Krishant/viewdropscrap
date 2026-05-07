import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    print("Error: Please set API_ID and API_HASH in your .env file first.")
else:
    print("Connecting to Telegram...")
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_str = client.session.save()
        print("\n" + "="*50)
        print("YOUR SESSION STRING (COPY THIS):")
        print("="*50)
        print(session_str)
        print("="*50)
        print("\nNow add this to Railway environment variables as SESSION_STRING")
