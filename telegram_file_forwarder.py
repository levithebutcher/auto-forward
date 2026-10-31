import asyncio
import json
import logging
import os
import random
import re
import sys
from datetime import datetime
from telethon import TelegramClient, errors, custom
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    ChatInviteAlready,
    ChatInvite
)
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest
)

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("forwarder.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("TelegramForwarder")

CONFIG_FILE = "config.json"
PROGRESS_FILE = "progress.json"
LINKS_FILE = "generated_links.txt"

DEFAULT_CONFIG = {
    "api_id": 0,
    "api_hash": "",
    "phone_number": "",
    "source_channel": "https://t.me/+YourInviteHash",
    "target_bot": "@YourTargetBot",
    "batch_size": 100,
    "min_delay_seconds": 2.5,
    "max_delay_seconds": 4.5,
    "batch_wait_seconds": 20.0,
    "button_1_text_or_index": "Generate code",
    "button_2_text_or_index": "Generate"
}


def load_config() -> dict:
    """Loads configuration from config.json."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        logger.warning(f"Created template configuration file: '{CONFIG_FILE}'.")
        return None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not cfg.get("api_id") or not cfg.get("api_hash"):
            logger.error(f"Please fill in valid 'api_id' and 'api_hash' in '{CONFIG_FILE}'.")
            return None
        return cfg
    except Exception as e:
        logger.error(f"Error reading '{CONFIG_FILE}': {e}")
        return None


def load_progress() -> dict:
    """Loads progress from progress.json to resume state seamlessly."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read progress file: {e}. Starting fresh.")
    return {
        "processed_ids": [],
        "completed_batches": 0,
        "batch_records": []
    }


def save_progress(progress: dict):
    """Saves current state atomically to progress.json."""
    temp_file = PROGRESS_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    os.rename(temp_file, PROGRESS_FILE)


def save_link_to_file(batch_num: int, code: str, share_link: str, raw_text: str):
    """Appends newly generated links/codes to generated_links.txt."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"==================================================\n"
        f"Batch #{batch_num} | Completed at {timestamp}\n"
        f"Retrieval Code : {code}\n"
        f"Shareable Link : {share_link}\n"
        f"Raw Message:\n{raw_text.strip()}\n"
        f"==================================================\n\n"
    )
    with open(LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    logger.info(f"Saved Batch #{batch_num} details to '{LINKS_FILE}'")


async def resolve_peer_safely(client: TelegramClient, peer_str: str):
    """
    Resolves usernames, chat IDs, or private channel invite links (e.g. https://t.me/+...).
    """
    peer_str = str(peer_str).strip()

    invite_match = re.search(r"(?:t\.me/joinchat/|t\.me/\+)([a-zA-Z0-9_\-]+)", peer_str)
    if invite_match:
        invite_hash = invite_match.group(1)
        try:
            check = await client(CheckChatInviteRequest(invite_hash))
            if isinstance(check, ChatInviteAlready):
                return check.chat
            elif isinstance(check, ChatInvite):
                updates = await client(ImportChatInviteRequest(invite_hash))
                return updates.chats[0]
        except errors.UserAlreadyParticipantError:
            async for dialog in client.iter_dialogs():
                if dialog.is_channel:
                    return dialog.entity
        except Exception as e:
            logger.warning(f"Invite resolution note: {e}")

    return await client.get_entity(peer_str)


async def wait_for_message_with_buttons(client: TelegramClient, bot_entity, timeout: int = 40):
    """Waits for the target bot to send or update a message with inline buttons."""
    logger.info(f"Waiting up to {timeout}s for bot prompt with buttons...")
    start_time = asyncio.get_event_loop().time()
    
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        messages = await client.get_messages(bot_entity, limit=3)
        for msg in messages:
            if msg.buttons:
                return msg
        await asyncio.sleep(2)
        
    return None


async def click_button_safely(client: TelegramClient, message: custom.Message, selector, step_name: str):
    """
    Clicks an inline button on a message using either text matching or button index.
    Returns the updated or latest message after the click.
    """
    if not message or not message.buttons:
        logger.error(f"Cannot click {step_name}: Message has no buttons!")
        return None

    flat_buttons = []
    for row in message.buttons:
        for btn in row:
            flat_buttons.append(btn)

    logger.info(f"Available buttons for {step_name}:")
    for idx, btn in enumerate(flat_buttons):
        logger.info(f"  [{idx}] '{btn.text}'")

    target_idx = 0
    target_btn = flat_buttons[0]

    if isinstance(selector, int):
        if 0 <= selector < len(flat_buttons):
            target_idx = selector
            target_btn = flat_buttons[selector]
    elif isinstance(selector, str) and selector.strip():
        selector_str = selector.strip().lower()
        matched = False
        for idx, btn in enumerate(flat_buttons):
            btn_clean = re.sub(r"[^\w\s]", "", btn.text).strip().lower()
            sel_clean = re.sub(r"[^\w\s]", "", selector_str).strip().lower()
            if sel_clean in btn_clean or selector_str in btn.text.lower():
                target_idx = idx
                target_btn = btn
                matched = True
                break
        if not matched:
            logger.warning(f"No button matched '{selector}', falling back to button [0].")

    logger.info(f"Clicking {step_name}: [{target_idx}] '{target_btn.text}'...")

    try:
        await message.click(target_idx)
    except errors.FloodWaitError as e:
        logger.warning(f"Telegram FloodWait while clicking button: Sleeping {e.seconds}s...")
        await asyncio.sleep(e.seconds + 2)
        await message.click(target_idx)
    except Exception as e:
        logger.error(f"Error while clicking button: {e}")

    await asyncio.sleep(3.5)

    recent = await client.get_messages(message.chat_id, limit=2)
    if recent and recent[0].id != message.id:
        return recent[0]

    refreshed = await client.get_messages(message.chat_id, ids=message.id)
    return refreshed


def parse_bot_result(message: custom.Message, bot_username: str = "bot"):
    """
    Extracts the retrieval code and constructs the shareable link from Step 3 message.
    """
    if not message:
        return "Unknown_Code", "No_Link"

    text = message.text or ""
    retrieval_code = ""
    share_link = ""

    code_match = re.search(r"([a-zA-Z0-9]+_[a-zA-Z0-9_\-]+)", text)
    if code_match:
        retrieval_code = code_match.group(1)
    else:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            retrieval_code = lines[0]

    clean_bot = bot_username.lstrip("@")
    
    tme_links = re.findall(r"https?://t\.me/[^\s]+", text)
    if tme_links:
        share_link = tme_links[0]
    elif retrieval_code:
        share_link = f"https://t.me/{clean_bot}?start={retrieval_code}"

    return retrieval_code, share_link


async def process_batch_completion(client: TelegramClient, bot_entity, batch_num: int, cfg: dict, progress: dict):
    """
    Automates clicking the 2 buttons (Step 1 -> Step 2) and harvesting the Step 3 code/link.
    """
    logger.info(f"\n[Batch #{batch_num}] 100 files forwarded! Automating bot buttons...")

    bot_username = getattr(bot_entity, "username", "YourTargetBot") or "YourTargetBot"

    bot_msg = await wait_for_message_with_buttons(client, bot_entity, timeout=45)
    if not bot_msg:
        logger.error("Bot did not send a message with buttons within the timeout period!")
        return False

    btn1_sel = cfg.get("button_1_text_or_index", "Generate code")
    step2_msg = await click_button_safely(client, bot_msg, btn1_sel, step_name="Button 1 (Generate code)")

    if not step2_msg:
        logger.error("Could not proceed to Step 2.")
        return False

    if not step2_msg.buttons:
        logger.info("Waiting for Step 2 prompt ('Generate this code without a title?')...")
        step2_msg = await wait_for_message_with_buttons(client, bot_entity, timeout=20)

    btn2_sel = cfg.get("button_2_text_or_index", "Generate")
    step3_msg = await click_button_safely(client, step2_msg, btn2_sel, step_name="Button 2 (Generate)")

    await asyncio.sleep(3.0)
    recent = await client.get_messages(bot_entity, limit=2)
    final_msg = recent[0] if recent else step3_msg

    if final_msg and final_msg.buttons:
        for row in final_msg.buttons:
            for btn in row:
                if "share link" in btn.text.lower():
                    try:
                        logger.info(f"Clicking '{btn.text}' to fetch direct link...")
                        await final_msg.click(text=btn.text)
                        await asyncio.sleep(2.0)
                        recent = await client.get_messages(bot_entity, limit=2)
                        final_msg = recent[0]
                    except Exception:
                        pass
                    break

    raw_text = final_msg.text if final_msg else ""
    code, link = parse_bot_result(final_msg, bot_username)

    logger.info(f"\n==================================================")
    logger.info(f"Batch #{batch_num} Successfully Generated!")
    logger.info(f"Retrieval Code: {code}")
    logger.info(f"Shareable Link: {link}")
    logger.info(f"==================================================\n")

    save_link_to_file(batch_num, code, link, raw_text)

    progress["completed_batches"] += 1
    progress["batch_records"].append({
        "batch_number": batch_num,
        "timestamp": datetime.now().isoformat(),
        "code": code,
        "link": link,
        "raw_text": raw_text
    })
    save_progress(progress)
    return True


async def run_forwarder(client: TelegramClient, cfg: dict):
    """Executes the forwarder process with safety delays and auto-resume."""
    progress = load_progress()
    processed_set = set(progress.get("processed_ids", []))
    logger.info(f"Loaded progress: {len(processed_set)} media files previously forwarded. Completed batches: {progress.get('completed_batches', 0)}")

    source_channel = await resolve_peer_safely(client, cfg["source_channel"])
    target_bot = await resolve_peer_safely(client, cfg["target_bot"])
    logger.info(f"Source Channel: {getattr(source_channel, 'title', cfg['source_channel'])}")
    logger.info(f"Target Bot: {getattr(target_bot, 'first_name', cfg['target_bot'])} (@{getattr(target_bot, 'username', 'bot')})")

    logger.info("Scanning source channel for media (oldest to newest)...")
    media_messages = []
    async for msg in client.iter_messages(source_channel, reverse=True):
        if msg.media and not msg.action:
            media_messages.append(msg)

    total_media = len(media_messages)
    pending_messages = [m for m in media_messages if m.id not in processed_set]
    logger.info(f"Total media: {total_media} | Pending to forward: {len(pending_messages)}")

    if not pending_messages:
        logger.info("All media files have already been processed! Nothing to forward.")
        return

    batch_size = cfg.get("batch_size", 100)
    min_delay = cfg.get("min_delay_seconds", 2.5)
    max_delay = cfg.get("max_delay_seconds", 4.5)
    batch_wait = cfg.get("batch_wait_seconds", 20.0)

    # Check how many files are in current partial batch
    current_batch_count = len(processed_set) % batch_size
    batch_num = progress.get("completed_batches", 0) + 1

    logger.info(f"\nStarting forward loop (Batch #{batch_num}, Size: {batch_size}, Current in batch: {current_batch_count})...")
    logger.info(f"Safety Delay between files: {min_delay}s - {max_delay}s")

    for idx, msg in enumerate(pending_messages, 1):
        media_type = "Video/Document" if isinstance(msg.media, MessageMediaDocument) else "Photo"
        logger.info(f"[{idx}/{len(pending_messages)}] (Batch #{batch_num}: {current_batch_count + 1}/{batch_size}) Forwarding {media_type} (Msg ID: {msg.id})...")

        forward_success = False
        while not forward_success:
            try:
                await client.forward_messages(
                    entity=target_bot,
                    messages=msg.id,
                    from_peer=source_channel
                )
                forward_success = True
            except errors.FloodWaitError as e:
                logger.warning(f"Telegram FloodWait: Rate limit encountered. Sleeping for {e.seconds} seconds to protect account...")
                await asyncio.sleep(e.seconds + 3)
            except Exception as e:
                logger.error(f"Failed to forward message ID {msg.id}: {e}")
                break

        if forward_success:
            processed_set.add(msg.id)
            progress["processed_ids"].append(msg.id)
            save_progress(progress)
            current_batch_count += 1

            if current_batch_count >= batch_size:
                success = await process_batch_completion(client, target_bot, batch_num, cfg, progress)
                if not success:
                    logger.warning("Batch completion automation failed or was incomplete. State is saved.")
                
                logger.info(f"Batch #{batch_num} done. Pausing {batch_wait}s before next batch to protect account...\n")
                await asyncio.sleep(batch_wait)
                
                batch_num += 1
                current_batch_count = 0
            else:
                delay = random.uniform(min_delay, max_delay)
                await asyncio.sleep(delay)

    if current_batch_count > 0:
        logger.info(f"\nAll files sent! Processing final partial batch of {current_batch_count} files...")
        await process_batch_completion(client, target_bot, batch_num, cfg, progress)

    logger.info("\nAll media files have been successfully processed!")
    logger.info(f"Check '{LINKS_FILE}' for all your saved access links and codes.")


async def main():
    print("""
============================================================
       Telegram Batch Media Forwarder & Auto-Link Tool      
============================================================
    """)

    cfg = load_config()
    if not cfg:
        return

    # Initialize Telethon Client with Telegram Desktop profile
    client = TelegramClient(
        "user_session",
        cfg["api_id"],
        cfg["api_hash"],
        device_model="Desktop",
        app_version="5.5.0 x64",
        system_version="Windows 11"
    )

    logger.info("Connecting to Telegram...")
    await client.start(phone=cfg.get("phone_number") or None)
    logger.info("Successfully authenticated with Telegram!")

    await run_forwarder(client, cfg)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nProcess paused by user. Progress has been safely saved! Rerun anytime to resume.")
    except errors.AuthKeyUnregisteredError:
        logger.error("\nSession was revoked by Telegram. Please re-run to re-authenticate.")
