# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying

from pyrogram import Client, filters
from pyrogram.types import Message
from database.db import db

@Client.on_message(filters.command("set_thumb") & filters.private)
async def set_thumb(client: Client, message: Message):
    source_message = None
    if message.photo:
        source_message = message
    elif message.reply_to_message and (message.reply_to_message.photo or getattr(message.reply_to_message, "document", None)):
        source_message = message.reply_to_message

    if not source_message:
        return await message.reply_text(
            "**__Send a photo with /set_thumb or reply to a photo with /set_thumb.__**"
        )

    try:
        if getattr(source_message, "photo", None):
            file_id = source_message.photo.file_id
        elif getattr(source_message, "document", None) and getattr(source_message.document, "mime_type", "").startswith("image/"):
            file_id = source_message.document.file_id
        else:
            return await message.reply_text("**__Please use a normal photo or image file.__**")

        if not file_id:
            return await message.reply_text("**__Could not read the photo file_id. Try again with a normal photo message.__**")

        await db.set_thumbnail(message.from_user.id, file_id)
        await message.reply_text("**__Custom Thumbnail Set Successfully ✅__**")
    except Exception as e:
        await message.reply_text(f"**__Failed to set thumbnail: {e}__**")
# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying

@Client.on_message(filters.command(["view_thumb", "see_thumb"]) & filters.private)
async def view_thumb(client: Client, message: Message):
    thumb = await db.get_thumbnail(message.from_user.id)
    if thumb:
        await message.reply_photo(photo=thumb, caption="**__Your Custom Thumbnail__**")
    else:
        await message.reply_text("**__You haven't set any custom thumbnail.__**")

@Client.on_message(filters.command(["del_thumb", "delete_thumb"]) & filters.private)
async def del_thumb(client: Client, message: Message):
    thumb = await db.get_thumbnail(message.from_user.id)
    if not thumb:
        return await message.reply_text("**__You don't have a custom thumbnail to delete.__**")
    
    await db.del_thumbnail(message.from_user.id)
    await message.reply_text("**__Custom Thumbnail Deleted Successfully 🗑__**")

@Client.on_message(filters.command("thumb_mode") & filters.private)
async def thumb_mode(client: Client, message: Message):
    # This might be to toggle between default/custom/no thumbnail.
    # For now, just a placeholder explaining usage.
    await message.reply_text("**__Thumbnail Mode: Custom (Default if set).__**\nUse /set_thumb and /del_thumb to manage.")

# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying
