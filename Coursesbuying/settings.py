# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db
from Coursesbuying.strings import COMMANDS_TXT

@Client.on_message(filters.command("settings") & filters.private)
async def settings(client: Client, message: Message):
    settings_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📜 Commands List", callback_data="cmd_list_btn"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_btn")
        ]
    ])
    await message.reply_text(
        "**⚙️ Settings Menu**\n\nChoose an option below:",
        reply_markup=settings_buttons
    )

@Client.on_message(filters.command("commands") & filters.private)
async def commands_list(client: Client, message: Message):
    # Reuse the callback logic for consistency, or send fresh
    settings_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Close", callback_data="close_btn")
        ]
    ])
    await message.reply_text(
        COMMANDS_TXT,
        reply_markup=settings_buttons,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

@Client.on_message(filters.command("setchat") & filters.private)
async def setchat(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:** `/setchat chat_id` or `/setchat @channel_username`\n\n"
            "Set the chat where your saved content will be sent.\n"
            "You can use a numeric chat ID or a @username for public channels/groups."
        )
    
    raw = message.command[1]
    
    # If it's a @username, resolve it
    if raw.startswith('@'):
        username = raw[1:]
        try:
            chat = await client.get_chat(username)
            chat_id = chat.id
            chat_title = chat.title or chat.first_name or username
            chat_type = "channel" if chat.type in (enums.ChatType.CHANNEL,) else "group"
            await db.set_dump_chat(message.from_user.id, chat_id)
            await message.reply_text(
                f"**Dump Chat Set Successfully ✅**\n\n"
                f"**{chat_type.title()}:** {chat_title}\n"
                f"**Username:** @{username}\n"
                f"**Chat ID:** `{chat_id}`"
            )
        except Exception as e:
            await message.reply_text(f"**Could not resolve @{username}.**\n\nMake sure the bot is a member of that chat.\nError: {e}")
        return
    
    # Numeric chat ID
    try:
        chat_id = int(raw)
        await db.set_dump_chat(message.from_user.id, chat_id)
        await message.reply_text(f"**Dump Chat Set Successfully ✅**\n\n**Chat ID:** `{chat_id}`")
    except ValueError:
        await message.reply_text(
            "**Invalid input.**\n\n"
            "Use a numeric chat ID like `-100123456789` or a @username like `@mychannel`."
        )
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@Client.on_callback_query(filters.regex("cmd_list_btn"))
async def cmd_list_callback(client: Client, callback_query):
    settings_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back", callback_data="settings_back_btn"),
            InlineKeyboardButton("❌ Close", callback_data="close_btn")
        ]
    ])
    await callback_query.edit_message_text(
        COMMANDS_TXT,
        reply_markup=settings_buttons,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex("settings_back_btn"))
async def settings_back_callback(client: Client, callback_query):
    settings_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📜 Commands List", callback_data="cmd_list_btn"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_btn")
        ]
    ])
    await callback_query.edit_message_text(
        "**⚙️ Settings Menu**\n\nChoose an option below:",
        reply_markup=settings_buttons
    )

# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying
