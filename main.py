# main.py
# Minimal Pyrogram bot that supports receiving multiple videos and merging them.
# Usage: user sends multiple video files in one message (media group) or separate files,
# then replies to the message containing those files with the command /merge
# (this is a simple example flow; adapt to your UX).

import logging
import os
import asyncio
from pathlib import Path
from typing import List

from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaVideo
import aiofiles

import configs
from merge import merge_videos, TMP_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Validate configs
configs.validate()

# Make sure downloads folder exists
TMP_DIR.mkdir(exist_ok=True)

# Pyrogram client
app = Client(
    "lasthope_bot",
    api_id=configs.API_ID,
    api_hash=configs.API_HASH,
    bot_token=configs.BOT_TOKEN,
    workdir="."
)


async def _download_media(message: Message, target_dir: Path) -> List[str]:
    """Download all video/document media from a message (or media group) to target_dir.
    Returns a list of file paths."""
    saved = []
    # If it's a media group, message.media_group_id will be set and separate messages might be in same group
    # For simplicity, handle single message files and captions with multiple attachments manually.
    # If message contains a video/document: download it.
    if message.video or message.document:
        file_name = await message.download(file_name=str(target_dir))
        saved.append(file_name)
        return saved

    # No direct video/document found
    return saved


@app.on_message(filters.private & filters.command("start"))
async def cmd_start(client: Client, message: Message):
    await message.reply_text(
        "Hi! Send multiple videos (or a media group). Then reply to any one of the video messages with /merge to merge them into a single file."
    )


@app.on_message(filters.private & filters.reply & filters.command("merge"))
async def cmd_merge(client: Client, message: Message):
    """
    Expectation: user replies to a message that contains the video(s).
    If reply points to a single message that is a media_group (other messages exist),
    we try to fetch all messages in that media group. Otherwise we try to merge attachments found in the replied message only.
    """
    replied = message.reply_to_message
    if not replied:
        await message.reply_text("Please reply to the message that contains the videos you want to merge.")
        return

    # Collect file message objects to download
    media_messages = []

    # If replied message is part of a media_group, we fetch recent messages in same chat and filter by media_group_id.
    if replied.media_group_id:
        # fetch last 50 messages in chat and pick same media_group_id
        msgs = await client.get_history(replied.chat.id, limit=100)
        for m in msgs:
            if m.media_group_id == replied.media_group_id and (m.video or m.document):
                media_messages.append(m)
        # sort by message_id to preserve order
        media_messages.sort(key=lambda x: x.message_id)
    else:
        # single message - if it has a video/document, use that; otherwise ask user to send multiple files or media group
        if replied.video or replied.document:
            media_messages = [replied]
        else:
            await message.reply_text("The replied message doesn't contain any video/document. Send the videos first and reply to one of them with /merge.")
            return

    if len(media_messages) < 2:
        await message.reply_text("Need at least 2 videos in the same media group (or multiple files) to merge. Found: {}".format(len(media_messages)))
        return

    status_msg = await message.reply_text("Downloading videos...")

    download_dir = TMP_DIR / f"{message.from_user.id}_{message.message_id}"
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        downloaded_files: List[str] = []
        for m in media_messages:
            file_path = await m.download(file_name=str(download_dir))
            downloaded_files.append(file_path)
        await status_msg.edit_text(f"Downloaded {len(downloaded_files)} files. Merging now...")

        output_file = download_dir / "merged_output.mp4"
        # You can adjust crf or make it configurable
        merged_path = await merge_videos(downloaded_files, str(output_file), crf=22)

        await status_msg.edit_text("Upload starting...")
        await client.send_video(
            chat_id=message.chat.id,
            video=str(merged_path),
            caption="Here is your merged video!",
            supports_streaming=True,
        )
        await status_msg.delete()
    except Exception as e:
        logger.exception("Merge failed")
        await status_msg.edit_text(f"Operation failed: {e}")
    finally:
        # cleanup - remove downloaded_dir after some delay to allow upload to finish
        async def _cleanup(p: Path, delay: int = 10):
            await asyncio.sleep(delay)
            try:
                for f in p.iterdir():
                    try:
                        f.unlink()
                    except Exception:
                        pass
                p.rmdir()
            except Exception:
                pass
        asyncio.create_task(_cleanup(download_dir, delay=30))


if __name__ == "__main__":
    app.run()
    
