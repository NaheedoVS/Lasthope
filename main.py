# main.py
"""
Lasthope Bot - Menu-based multimedia toolset
Requirements: pyrogram, tgcrypto, aiofiles, python-dotenv
Make sure 'ffmpeg' binary is available in the environment.
"""

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Optional, List

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from ffmpeg_tools import (
    compress_video,
    merge_videos,
    add_text_watermark,
    add_moving_watermark,
    trim_video,
    resize_video,
    extract_audio,
    extract_thumbnail,
    replace_audio,
    change_speed,
    rotate_video,
)

# ---- Configs via env ----
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TMP_ROOT = Path(os.getenv("TMP_DIR", "downloads"))
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")  # forwarded to ffmpeg_tools

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Set API_ID, API_HASH and BOT_TOKEN environment variables")

TMP_ROOT.mkdir(exist_ok=True, parents=True)

# ---- Logging ----
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("lasthope")

# ---- Bot ----
app = Client("lasthope_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir=".")

# ---- In-memory user session state ----
# WARNING: ephemeral — for persistent state across restarts use a DB
USER_STATE: Dict[int, Dict] = {}

# ---- Utility functions ----
def make_job_dir(user_id: int) -> Path:
    job = TMP_ROOT / f"{user_id}_{uuid.uuid4().hex[:10]}"
    job.mkdir(parents=True, exist_ok=True)
    return job

async def cleanup_dir(path: Path, delay: int = 30):
    await asyncio.sleep(delay)
    try:
        if path.exists():
            shutil.rmtree(path)
            logger.info("Cleaned up %s", path)
    except Exception as e:
        logger.exception("Failed to cleanup %s: %s", path, e)

# ---- Menu buttons ----
def main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Video Tools ▶️", callback_data="menu_video")],
            [InlineKeyboardButton("Audio Tools ▶️", callback_data="menu_audio")],
            [InlineKeyboardButton("Merge / Misc ▶️", callback_data="menu_misc")],
        ]
    )

def video_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Compress", callback_data="video_compress"),
             InlineKeyboardButton("Watermark (text)", callback_data="video_watermark")],
            [InlineKeyboardButton("Moving Watermark", callback_data="video_moving_wm"),
             InlineKeyboardButton("Trim", callback_data="video_trim")],
            [InlineKeyboardButton("Resize", callback_data="video_resize"),
             InlineKeyboardButton("Speed", callback_data="video_speed")],
            [InlineKeyboardButton("Rotate", callback_data="video_rotate"),
             InlineKeyboardButton("Thumbnail", callback_data="video_thumb")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")],
        ]
    )

def audio_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Extract audio (mp3)", callback_data="audio_extract"),
             InlineKeyboardButton("Replace / Mux audio", callback_data="audio_replace")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")],
        ]
    )

def misc_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Merge Videos", callback_data="misc_merge")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")],
        ]
    )

# ---- Commands ----
@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        "Welcome to Lasthope — multimedia toolset.\nUse /menu to open the tools."
    )

@app.on_message(filters.private & filters.command("menu"))
async def menu_handler(client: Client, message: Message):
    await message.reply_text("Choose a tool:", reply_markup=main_menu())

# ---- Callbacks ----
@app.on_callback_query()
async def cb_handler(client: Client, cq: CallbackQuery):
    data = cq.data or ""
    user_id = cq.from_user.id
    try:
        if data == "menu_video":
            await cq.edit_message_text("Video Tools — choose one:", reply_markup=video_menu())
        elif data == "menu_audio":
            await cq.edit_message_text("Audio Tools — choose one:", reply_markup=audio_menu())
        elif data == "menu_misc":
            await cq.edit_message_text("Merge / Misc — choose one:", reply_markup=misc_menu())
        elif data == "menu_back":
            await cq.edit_message_text("Choose a tool:", reply_markup=main_menu())

        # ---- VIDEO HANDLER NAV ----
        elif data == "video_compress":
            USER_STATE[user_id] = {"action": "compress"}
            await cq.edit_message_text("Reply to a video with /send to compress it.\nFormat: reply with /send <crf>\nExample: `/send 22`")
        elif data == "video_watermark":
            USER_STATE[user_id] = {"action": "watermark"}
            await cq.edit_message_text("Reply to a video with `/send TEXT | COLOR | SIZE | POSITION`\nExample: `/send Pgl | white | 48 | center`")
        elif data == "video_moving_wm":
            USER_STATE[user_id] = {"action": "moving_wm"}
            await cq.edit_message_text("Reply to a video with `/send TEXT | MODE`\nModes: `left-right`, `top-bottom`")
        elif data == "video_trim":
            USER_STATE[user_id] = {"action": "trim"}
            await cq.edit_message_text("Reply to a video with `/send START END`\nExample: `/send 00:00:05 00:00:12`")
        elif data == "video_resize":
            USER_STATE[user_id] = {"action": "resize"}
            await cq.edit_message_text("Reply to a video with `/send HEIGHT`\nExample: `/send 720`")
        elif data == "video_speed":
            USER_STATE[user_id] = {"action": "speed"}
            await cq.edit_message_text("Reply to a video with `/send FACTOR`\nExample: `/send 2.0` or `/send 0.5`")
        elif data == "video_rotate":
            USER_STATE[user_id] = {"action": "rotate"}
            await cq.edit_message_text("Reply to a video with `/send DEG`\nAllowed: 90,180,270")
        elif data == "video_thumb":
            USER_STATE[user_id] = {"action": "thumb"}
            await cq.edit_message_text("Reply to a video with `/send` to extract a thumbnail (frame at 3s).")

        # ---- AUDIO HANDLER NAV ----
        elif data == "audio_extract":
            USER_STATE[user_id] = {"action": "audio_extract"}
            await cq.edit_message_text("Reply to a video with `/send` to extract audio as mp3.")
        elif data == "audio_replace":
            USER_STATE[user_id] = {"action": "audio_replace"}
            await cq.edit_message_text("Step 1: Reply to a video with `/send` to select target video.\nThen upload an audio file and reply to it with `/send` to use as replacement audio.")

        # ---- MISC ----
        elif data == "misc_merge":
            USER_STATE[user_id] = {"action": "merge_collect", "collected": []}
            await cq.edit_message_text("Send multiple videos (one by one). Each time you send a video reply to the *menu message* with `/add` to add it. When ready, reply to this message with `/done` to merge them.")
        else:
            await cq.answer("Unknown action", show_alert=False)
    except Exception as e:
        logger.exception("Callback error: %s", e)
        await cq.answer("Internal error", show_alert=True)

# ---- Message handlers for /send and other control commands ----

@app.on_message(filters.private & filters.command("send"))
async def send_handler(client: Client, message: Message):
    """
    This command is used to trigger the current USER_STATE action.
    The user should reply to a video/document message with /send [params...]
    """
    user_id = message.from_user.id
    state = USER_STATE.get(user_id)
    if not state:
        await message.reply_text("No action selected. Use /menu to pick a tool.")
        return

    replied = message.reply_to_message
    if state["action"] == "merge_collect":
        await message.reply_text("Use /add and /done when merging multiple files. See /menu -> Merge.")
        return

    if not replied or not (replied.video or replied.document):
        await message.reply_text("Please reply to a video (or document) message with /send")
        return

    # Build job directory
    job_dir = make_job_dir(user_id)
    try:
        status = await message.reply_text("Downloading file...")
        input_path = await replied.download(file_name=str(job_dir))
        await status.edit_text("Downloaded. Processing...")

        action = state["action"]

        # compress: /send 22
        if action == "compress":
            parts = message.text.split(maxsplit=1)
            crf = int(parts[1].strip()) if len(parts) > 1 else 23
            out_path = job_dir / "compressed.mp4"
            await compress_video(str(input_path), str(out_path), crf=crf)
            await status.edit_text("Uploading compressed video...")
            await client.send_video(message.chat.id, str(out_path), caption=f"Compressed (crf={crf})")
            await status.delete()

        # watermark: /send TEXT | COLOR | SIZE | POSITION
        elif action == "watermark":
            # parse params
            params = (message.text.partition(" ")[2] or "").strip()
            if not params:
                await status.edit_text("Usage: reply with `/send TEXT | COLOR | SIZE | POSITION`")
            else:
                parts = [p.strip() for p in params.split("|")]
                text = parts[0] if len(parts) > 0 else "Watermark"
                color = parts[1] if len(parts) > 1 and parts[1] else "white"
                size = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 36
                position = parts[3] if len(parts) > 3 else "center"
                out_path = job_dir / "watermarked.mp4"
                await add_text_watermark(str(input_path), str(out_path), text=text, color=color, fontsize=size, position=position)
                await status.edit_text("Uploading watermarked video...")
                await client.send_video(message.chat.id, str(out_path), caption=f"Watermarked: {text}")
                await status.delete()

        elif action == "moving_wm":
            params = (message.text.partition(" ")[2] or "").strip()
            if not params:
                await status.edit_text("Usage: `/send TEXT | MODE` where MODE is left-right or top-bottom")
            else:
                parts = [p.strip() for p in params.split("|")]
                text = parts[0] if parts else "Watermark"
                mode = parts[1] if len(parts) > 1 else "left-right"
                out_path = job_dir / "moving_wm.mp4"
                await add_moving_watermark(str(input_path), str(out_path), text=text, mode=mode)
                await status.edit_text("Uploading moving watermark video...")
                await client.send_video(message.chat.id, str(out_path), caption="Moving watermark")
                await status.delete()

        elif action == "trim":
            parts = message.text.split()
            if len(parts) < 3:
                await status.edit_text("Usage: reply with `/send START END` like `00:00:05 00:00:12`")
            else:
                start, end = parts[1], parts[2]
                out_path = job_dir / "trimmed.mp4"
                await trim_video(str(input_path), str(out_path), start, end)
                await status.edit_text("Uploading trimmed video...")
                await client.send_video(message.chat.id, str(out_path), caption=f"Trimmed {start} -> {end}")
                await status.delete()

        elif action == "resize":
            parts = message.text.split()
            if len(parts) < 2:
                await status.edit_text("Usage: `/send HEIGHT` e.g. `/send 720`")
            else:
                height = int(parts[1])
                out_path = job_dir / "resized.mp4"
                await resize_video(str(input_path), str(out_path), height)
                await status.edit_text("Uploading resized video...")
                await client.send_video(message.chat.id, str(out_path), caption=f"Resized to height {height}")
                await status.delete()

        elif action == "speed":
            parts = message.text.split()
            if len(parts) < 2:
                await status.edit_text("Usage: `/send FACTOR` e.g. `/send 2.0`")
            else:
                factor = float(parts[1])
                out_path = job_dir / "speed.mp4"
                await change_speed(str(input_path), str(out_path), factor)
                await status.edit_text("Uploading speed-changed video...")
                await client.send_video(message.chat.id, str(out_path), caption=f"Speed x{factor}")
                await status.delete()

        elif action == "rotate":
            parts = message.text.split()
            if len(parts) < 2:
                await status.edit_text("Usage: `/send DEG` e.g. `/send 90`")
            else:
                deg = int(parts[1])
                out_path = job_dir / "rotated.mp4"
                await rotate_video(str(input_path), str(out_path), deg)
                await status.edit_text("Uploading rotated video...")
                await client.send_video(message.chat.id, str(out_path), caption=f"Rotated {deg}°")
                await status.delete()

        elif action == "thumb":
            out_path = job_dir / "thumb.jpg"
            await extract_thumbnail(str(input_path), str(out_path), at_time="00:00:03")
            await status.edit_text("Uploading thumbnail...")
            await client.send_photo(message.chat.id, str(out_path), caption="Thumbnail (frame at 3s)")
            await status.delete()

        elif action == "audio_extract":
            out_path = job_dir / "audio.mp3"
            await extract_audio(str(input_path), str(out_path))
            await status.edit_text("Uploading audio (mp3)...")
            await client.send_document(message.chat.id, str(out_path), caption="Extracted audio")
            await status.delete()

        elif action == "audio_replace":
            # Step flow: first the target video is selected, saved in state; user must upload audio and reply with /send to that audio (same action)
            if state.get("audio_target") is None:
                # save target video path and ask for audio
                state["audio_target"] = str(input_path)
                USER_STATE[user_id] = state
                await status.edit_text("Target video saved. Now upload or reply with the audio file and use `/send` (reply to audio) to replace audio.")
            else:
                # user replied with audio; perform replace_audio using stored target
                audio_path = str(input_path)
                out_path = job_dir / "replaced_audio.mp4"
                target = state.pop("audio_target")
                USER_STATE[user_id] = state
                await replace_audio(target, audio_path, str(out_path))
                await status.edit_text("Uploading muxed video...")
                await client.send_video(message.chat.id, str(out_path), caption="Replaced audio")
                await status.delete()

        else:
            await status.edit_text("Unknown action or not implemented yet.")
    except Exception as e:
        logger.exception("Processing error: %s", e)
        await message.reply_text(f"Error: {e}")
    finally:
        # schedule cleanup
        asyncio.create_task(cleanup_dir(job_dir, delay=30))

@app.on_message(filters.private & filters.command("add"))
async def add_for_merge(client: Client, message: Message):
    """
    Used during merge_collect flow. The user replies to the menu message with /add to add a video.
    """
    user_id = message.from_user.id
    state = USER_STATE.get(user_id)
    if not state or state.get("action") != "merge_collect":
        await message.reply_text("No merge session in progress. Use /menu -> Merge Videos.")
        return
    replied = message.reply_to_message
    if not replied or not (replied.video or replied.document):
        await message.reply_text("Reply to a video/document message with /add to include it in merge.")
        return

    job_dir = make_job_dir(user_id)
    try:
        status = await message.reply_text("Downloading...")
        fp = await replied.download(file_name=str(job_dir))
        state["collected"].append(fp)
        USER_STATE[user_id] = state
        await status.edit_text(f"Added. Total collected: {len(state['collected'])}")
    except Exception as e:
        logger.exception("Add error: %s", e)
        await message.reply_text(f"Failed to add video: {e}")
    finally:
        asyncio.create_task(cleanup_dir(job_dir, delay=20))

@app.on_message(filters.private & filters.command("done"))
async def done_merge(client: Client, message: Message):
    """
    Finalizes merge_collect flow: merges collected files and sends result.
    """
    user_id = message.from_user.id
    state = USER_STATE.get(user_id)
    if not state or state.get("action") != "merge_collect":
        await message.reply_text("No merge session in progress.")
        return
    files = state.get("collected", [])
    if len(files) < 2:
        await message.reply_text("Need at least 2 videos to merge.")
        return

    job_dir = make_job_dir(user_id)
    out_path = job_dir / "merged.mp4"
    status = await message.reply_text("Merging videos...")
    try:
        merged = await merge_videos(files, str(out_path), crf=22)
        await status.edit_text("Uploading merged video...")
        await client.send_video(message.chat.id, merged, caption="Merged video")
        await status.delete()
    except Exception as e:
        logger.exception("Merge failed: %s", e)
        await status.edit_text(f"Merge failed: {e}")
    finally:
        USER_STATE.pop(user_id, None)
        asyncio.create_task(cleanup_dir(job_dir, delay=30))

# ---- Start bot ----
if __name__ == "__main__":
    logger.info("Starting Lasthope bot...")
    app.run()
                
