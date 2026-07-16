import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from config import API_ID, API_HASH
from database.db import db
from Coursesbuying.link_utils import parse_reference_text
from Coursesbuying.runtime_state import BATCH_WAITING_USERS, ACTIVE_BATCH_USERS
from Coursesbuying.start import _process_reference, batch_temp
from logger import LOGGER

logger = LOGGER(__name__)

@Client.on_message(filters.command("batch") & filters.private)
async def batch_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    BATCH_WAITING_USERS.add(user_id)
    await message.reply_text(
        "<b>Send the bulk range in this format:</b>\n"
        "<code>t.me/firstID-lastID</code>\n\n"
        "<b>Example:</b> <code>t.me/123-130</code>\n"
        "<i>The bot will process messages in sequence from first ID to last ID.</i>\n\n"
        "<i>If you send only <code>123-130</code>, it will reuse the last resolved chat context.</i>",
        parse_mode=enums.ParseMode.HTML
    )

async def is_batch_waiting(_, __, message):
    return message.from_user.id in BATCH_WAITING_USERS

batch_filter = filters.create(is_batch_waiting)

@Client.on_message(filters.private & batch_filter & ~filters.command(["batch", "start", "cancel"]))
async def handle_batch_responses(client: Client, message: Message):
    user_id = message.from_user.id
    last_chat = await db.get_last_chat(user_id)
    reference = parse_reference_text(message.text, last_chat=last_chat)

    if not reference:
        return await message.reply_text(
            "<b>❌ Invalid bulk format.</b>\n\n"
            "Use: <code>t.me/firstID-lastID</code>\n"
            "Example: <code>t.me/123-130</code>",
            parse_mode=enums.ParseMode.HTML
        )

    BATCH_WAITING_USERS.discard(user_id)

    start_id = reference["start"]
    end_id = reference["end"]
    if start_id > end_id:
        start_id, end_id = end_id, start_id

    if start_id == end_id:
        sequence_text = f"{start_id}"
    else:
        sequence_text = f"{start_id}-{end_id}"

    await message.reply_text(
        f"<b>🚀 Bulk sequence accepted:</b> <code>{sequence_text}</code>\n"
        f"<i>Messages will be processed from first ID to last ID in order.</i>",
        parse_mode=enums.ParseMode.HTML
    )

    await _process_reference(client, message, reference)

@Client.on_message(filters.command(["cancel", "cancell"]) & filters.private)
async def cancel_batch_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in BATCH_WAITING_USERS:
        BATCH_WAITING_USERS.discard(user_id)
        batch_temp.IS_BATCH[user_id] = True
        await message.reply_text("<b>❌ Batch Process Cancelled Successfully.</b>", parse_mode=enums.ParseMode.HTML)
    elif user_id in ACTIVE_BATCH_USERS or batch_temp.IS_BATCH.get(user_id) is False:
        batch_temp.IS_BATCH[user_id] = True
        await message.reply_text("<b>❌ Running batch cancelled successfully.</b>", parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text("<b>❌ No Active Batch Process To Cancel.</b>", parse_mode=enums.ParseMode.HTML)
