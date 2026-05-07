import os
import re
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import RequestAppWebViewRequest
from telethon.tl.types import InputBotAppShortName
from dotenv import load_dotenv
import requests
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SOURCE_GROUP_ID = int(os.getenv('SOURCE_GROUP_ID'))
TARGET_GROUP_ID = int(os.getenv('TARGET_GROUP_ID'))

client = TelegramClient('session_name', API_ID, API_HASH)

async def extract_string_from_url(url, message_id):
    """
    Tries to extract a CC string by handling Refresh/Open buttons in a loop.
    """
    if not url: return None
    print(f"Debug: Opening WebApp URL: {url}")
    
    cc_pattern = r'(\d{15,16})[|/ ](\d{2})[|/ ](\d{2,4})[|/ ](\d{3,4})'
    
    # 1. Quick check in URL first
    match = re.search(cc_pattern, url)
    if match:
        num, mm, yy, cvv = match.groups()
        if len(yy) == 4: yy = yy[-2:]
        return f"{num}|{mm}|{yy}|{cvv}"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 360, 'height': 640},
                user_agent='Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36'
            )
            page = await context.new_page()
            
            print("Navigating to page...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # We try for up to 30 seconds to find the data, clicking any buttons along the way
            for attempt in range(6): # 6 attempts x 5 seconds = 30 seconds
                print(f"Attempt {attempt + 1}: Checking for buttons or data...")
                # Wait and check for data
                await asyncio.sleep(4)
                
                # Check for data first
                content = await page.content()
                text_content = await page.evaluate("() => document.body.innerText")
                match = re.search(cc_pattern, content) or re.search(cc_pattern, text_content)
                if match:
                    # Normalize to Number|MM|YY|CVV
                    num, mm, yy, cvv = match.groups()
                    if len(yy) == 4: yy = yy[-2:]
                    normalized = f"{num}|{mm}|{yy}|{cvv}"
                    print(f"Success! Found CC string: {normalized}")
                    await browser.close()
                    return normalized
                
                # If no data, look for buttons to click
                buttons_to_click = ["Refresh", "Open", "View", "Launch"]
                clicked = False
                for btn_text in buttons_to_click:
                    try:
                        btn = page.get_by_text(re.compile(btn_text, re.IGNORECASE))
                        if await btn.count() > 0:
                            print(f"Found '{btn_text}' button, clicking...")
                            await btn.first.click()
                            clicked = True
                            await asyncio.sleep(2)
                            break
                    except:
                        continue
                
                if not clicked:
                    print("No known buttons found. Waiting...")
            
            # Final check in frames
            for frame in page.frames:
                try:
                    frame_content = await frame.content()
                    match = re.search(cc_pattern, frame_content)
                    if match:
                        await browser.close()
                        return match.group(1)
                except:
                    continue
            
            print("Debug: Failed to extract data after 30 seconds.")
            await browser.close()
    except Exception as e:
        print(f"Error using Playwright: {e}")
    
    return None

async def resolve_webapp_url(bot_username, start_param, source_peer):
    try:
        print(f"Resolving WebApp for {bot_username} from group with param {start_param}...")
        bot_peer = await client.get_input_entity(bot_username)
        res = await client(RequestAppWebViewRequest(
            peer=source_peer,
            app=InputBotAppShortName(bot_peer, "webapp"),
            platform='android',
            start_param=start_param,
            write_allowed=True
        ))
        return res.url
    except Exception as e:
        print(f"Failed to resolve WebApp URL via RPC: {e}")
        return None

@client.on(events.NewMessage(chats=SOURCE_GROUP_ID))
async def handler(event):
    print(f"New message detected in Source Group: {event.id}")
    if not event.reply_markup:
        return

    for row_index, row in enumerate(event.reply_markup.rows):
        for col_index, button in enumerate(row.buttons):
            button_text = button.text.lower()
            if "view" in button_text or "drop" in button_text:
                print(f"Found button: {button.text}")
                
                try:
                    result = await event.click(row_index, col_index)
                    initial_url = None
                    if hasattr(result, 'url'):
                        initial_url = result.url
                    elif hasattr(button, 'url'):
                        initial_url = button.url
                    
                    final_url = initial_url
                    start_param = ""
                    
                    if initial_url:
                        if "startapp=" in initial_url:
                            start_param = initial_url.split("startapp=")[1].split("&")[0]
                        elif "tgWebAppStartParam=" in initial_url:
                            start_param = initial_url.split("tgWebAppStartParam=")[1].split("&")[0]
                    
                    resolved_url = await resolve_webapp_url("xForceDropsBot", start_param, await event.get_input_chat())
                    if resolved_url:
                        final_url = resolved_url
                    elif start_param:
                        final_url = f"https://drops.xforce.group/?tgWebAppStartParam={start_param}"
                    
                    if not final_url:
                        return

                    # Extract string
                    drop_string = await extract_string_from_url(final_url, event.id)
                    
                    if drop_string:
                        print(f"Extracted string: {drop_string}")
                        await client.send_message(TARGET_GROUP_ID, f"/sp {drop_string}")
                        print(f"Sent /sp {drop_string} to {TARGET_GROUP_ID}")
                    else:
                        print("Could not extract string automatically.")

                except Exception as e:
                    print(f"Error clicking button: {e}")

async def main():
    await client.start(phone=PHONE_NUMBER)
    print("Userbot is running...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
