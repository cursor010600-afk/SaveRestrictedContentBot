# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying



import os
import asyncio
import random
import time
import shutil
import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    FloodWait, UserIsBlocked, InputUserDeactivated, UserAlreadyParticipant, 
    InviteHashExpired, UsernameNotOccupied, AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import API_ID, API_HASH, ERROR_MESSAGE
from database.db import db
import math
from Coursesbuying.strings import HELP_TXT, COMMANDS_TXT
from Coursesbuying.link_utils import parse_reference_text
from Coursesbuying.runtime_state import BATCH_WAITING_USERS, ACTIVE_BATCH_USERS
from logger import LOGGER

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "")
    
    if not tmp:
        tmp = ((str(milliseconds) + "ms, ") if milliseconds else "")
        
    return tmp[:-2] if tmp else "0s"

logger = LOGGER(__name__)

class batch_temp(object):
    IS_BATCH = {}


async def _resolve_reference(message: Message, text: str):
    """Resolve deep links, public/private Telegram links, and short bulk ranges."""
    last_chat = await db.get_last_chat(message.from_user.id)
    return parse_reference_text(text, last_chat=last_chat)


async def _get_user_word_rules(user_id: int):
    delete_words = await db.get_delete_words(user_id)
    replace_words = await db.get_replace_words(user_id)
    return delete_words or [], replace_words or {}


def _apply_word_rules(text: str, delete_words, replace_words):
    if not text:
        return text

    updated_text = text
    for word in delete_words:
        if word:
            updated_text = updated_text.replace(word, "")

    for target, replacement in replace_words.items():
        if target:
            updated_text = updated_text.replace(target, replacement)

    return updated_text


def _build_reply_markup(source_message: Message):
    reply_markup = getattr(source_message, 'reply_markup', None)
    if not reply_markup or not getattr(reply_markup, 'inline_keyboard', None):
        return None

    buttons = []
    for row in reply_markup.inline_keyboard:
        new_row = []
        for button in row:
            if getattr(button, 'url', None):
                new_row.append(InlineKeyboardButton(button.text, url=button.url))
            elif getattr(button, 'callback_data', None):
                new_row.append(InlineKeyboardButton(button.text, callback_data=button.callback_data))
        if new_row:
            buttons.append(new_row)

    return InlineKeyboardMarkup(buttons) if buttons else None


async def _get_custom_thumb_path(user_id: int, client: Client):
    thumb_file_id = await db.get_thumbnail(user_id)
    if not thumb_file_id:
        return None

    os.makedirs("thumbs", exist_ok=True)
    thumb_path = f"thumbs/{user_id}.jpg"
    try:
        await client.download_media(thumb_file_id, file_name=thumb_path)
        return thumb_path
    except Exception as e:
        logger.error(f"Failed to download custom thumbnail for {user_id}: {e}")
        return None


async def _process_reference(client: Client, message: Message, reference: dict):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)

    start_id = reference['start']
    end_id = reference['end']
    if start_id > end_id:
        start_id, end_id = end_id, start_id

    await db.set_last_chat(message.from_user.id, {'kind': reference['kind'], 'chat': reference['chat']})

    if message.from_user.id in ACTIVE_BATCH_USERS or batch_temp.IS_BATCH.get(message.from_user.id) is False:
        return await message.reply_text(
            'One Task Is Already Processing. Wait For Complete It. If You Want To Cancel This Task Then Use - /cancel'
        )

    delete_words, replace_words = await _get_user_word_rules(message.from_user.id)
    needs_login = reference['kind'] != 'public' or bool(delete_words) or bool(replace_words)
    user_data = await db.get_session(message.from_user.id)
    if needs_login and not user_data:
        return await message.reply_text('**__For Downloading Restricted Content You Have To /login First.__**')

    batch_temp.IS_BATCH[message.from_user.id] = False
    ACTIVE_BATCH_USERS.add(message.from_user.id)

    chat_ref = reference['chat']
    source_kind = reference['kind']
    total = end_id - start_id + 1
    sent_count = 0
    missing_count = 0
    error_count = 0
    cancelled_count = 0
    missing_ids = []
    error_ids = []

    status_message = await message.reply_text(
        f'<b>🚀 Batch Processing Started</b>\n\n'
        f'<b>Total:</b> <code>{total}</code>\n'
        f'<b>Done:</b> <code>0</code>\n'
        f'<b>Sent:</b> <code>0</code> | <b>Missing:</b> <code>0</code> | <b>Error:</b> <code>0</code>\n'
        f'<b>Range:</b> <code>{start_id}-{end_id}</code>',
        parse_mode=enums.ParseMode.HTML
    )

    acc = None
    try:
        if needs_login and user_data:
            acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID, in_memory=True)
            await acc.connect()

        for index, msgid in enumerate(range(start_id, end_id + 1), start=1):
            if batch_temp.IS_BATCH.get(message.from_user.id):
                cancelled_count = total - index + 1
                break

            result = await handle_private(
                client=client,
                acc=acc,
                message=message,
                chatid=chat_ref,
                msgid=msgid,
                source_kind=source_kind,
                delete_words=delete_words,
                replace_words=replace_words,
            )

            result_status = result.get('status')
            if result_status == 'sent':
                sent_count += 1
            elif result_status == 'missing':
                missing_count += 1
                missing_ids.append(msgid)
            elif result_status == 'error':
                error_count += 1
                error_ids.append(msgid)
            elif result_status == 'cancelled':
                cancelled_count = total - index + 1
                break

            await status_message.edit_text(
                f'<b>🚀 Batch Processing</b>\n\n'
                f'<b>Range:</b> <code>{start_id}-{end_id}</code>\n'
                f'<b>Progress:</b> <code>{index}/{total}</code>\n'
                f'<b>Sent:</b> <code>{sent_count}</code> | <b>Missing:</b> <code>{missing_count}</code> | <b>Error:</b> <code>{error_count}</code>',
                parse_mode=enums.ParseMode.HTML
            )

            await asyncio.sleep(1)

        if batch_temp.IS_BATCH.get(message.from_user.id):
            final_text = (
                f'<b>❌ Batch Cancelled</b>\n\n'
                f'<b>Processed:</b> <code>{sent_count + missing_count + error_count}</code>/{total}\n'
                f'<b>Sent:</b> <code>{sent_count}</code> | <b>Missing:</b> <code>{missing_count}</code> | <b>Error:</b> <code>{error_count}</code>'
            )
        else:
            final_text = (
                f'<b>✅ Batch Completed</b>\n\n'
                f'<b>Total:</b> <code>{total}</code>\n'
                f'<b>Sent:</b> <code>{sent_count}</code>\n'
                f'<b>Missing:</b> <code>{missing_count}</code>\n'
                f'<b>Error:</b> <code>{error_count}</code>'
            )

            if missing_ids:
                final_text += f"\n<b>Missing IDs:</b> <code>{', '.join(map(str, missing_ids[:15]))}</code>"
            if error_ids:
                final_text += f"\n<b>Error IDs:</b> <code>{', '.join(map(str, error_ids[:15]))}</code>"

        try:
            await status_message.delete()
        except Exception:
            pass

        await message.reply_text(final_text, parse_mode=enums.ParseMode.HTML)
        return {
            'status': 'cancelled' if batch_temp.IS_BATCH.get(message.from_user.id) else 'done',
            'sent': sent_count,
            'missing': missing_count,
            'errors': error_count,
            'total': total,
        }
    finally:
        ACTIVE_BATCH_USERS.discard(message.from_user.id)
        batch_temp.IS_BATCH[message.from_user.id] = True
        if acc:
            try:
                await acc.disconnect()
            except Exception:
                pass

# -------------------
# Supported Telegram Reactions
# -------------------

REACTIONS = [
    "🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩",
    "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡",
    "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"
]

PROGRESS_BAR_DASHBOARD  = """\
<blockquote>
✦ <code>{bar}</code> • <b>{percentage:.1f}%</b><br>
››  <b>Speed</b> • <code>{speed}/s</code><br>
››  <b>Size</b> • <code>{current} / {total}</code><br>
››  <b>ETA</b> • <code>{eta}</code><br>
››  <b>Elapsed</b> • <code>{elapsed}</code>
</blockquote>
"""



# -------------------
# Download status
# -------------------

async def downstatus(client, statusfile, message, chat):
    while not os.path.exists(statusfile):
        await asyncio.sleep(3)
    while os.path.exists(statusfile):
        try:
            with open(statusfile, "r", encoding='utf-8') as downread:
                txt = downread.read()
            await client.edit_message_text(chat, message.id, f"📥 **Downloading...**\n\n{txt}")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)

# -------------------
# Upload status
# -------------------

async def upstatus(client, statusfile, message, chat):
    while not os.path.exists(statusfile):
        await asyncio.sleep(3)
    while os.path.exists(statusfile):
        try:
            with open(statusfile, "r", encoding='utf-8') as upread:
                txt = upread.read()
            await client.edit_message_text(chat, message.id, f"📤 **Uploading...**\n\n{txt}")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)

# -------------------
# Progress writer
# -------------------

def progress(current, total, message, type):
    # Check for cancellation
    if batch_temp.IS_BATCH.get(message.from_user.id):
        raise Exception("Cancelled")

    # Initialize cache if not exists
    if not hasattr(progress, "cache"):
        progress.cache = {}
    
    now = time.time()
    task_id = f"{message.id}{type}"
    last_time = progress.cache.get(task_id, 0)
    
    # Track start time for speed calc
    if not hasattr(progress, "start_time"):
        progress.start_time = {}
    if task_id not in progress.start_time:
        progress.start_time[task_id] = now
        
    # Update only every 3 seconds or if completed
    if (now - last_time) > 3 or current == total:
        try:
            percentage = current * 100 / total
            speed = current / (now - progress.start_time[task_id])
            eta = (total - current) / speed if speed > 0 else 0
            elapsed = now - progress.start_time[task_id]
            
            # Progress Bar
            filled_length = int(percentage / 10) # 10 blocks for 100%
            bar = '▰' * filled_length + '▱' * (10 - filled_length)
            
            status = PROGRESS_BAR_DASHBOARD.format(
                bar=bar,
                percentage=percentage,
                current=humanbytes(current),
                total=humanbytes(total),
                speed=humanbytes(speed),
                eta=TimeFormatter(eta * 1000),
                elapsed=TimeFormatter(elapsed * 1000)
            )
            
            with open(f'{message.id}{type}status.txt', "w", encoding='utf-8') as fileup:
                fileup.write(status)
                
            progress.cache[task_id] = now
            
            if current == total:
                # Cleanup cache
                progress.start_time.pop(task_id, None)
                progress.cache.pop(task_id, None)
                
        except:
            pass

# -------------------
# Start command
# -------------------

@Client.on_message(filters.command(["start"]))
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)

    if len(message.command) > 1:
        payload = " ".join(message.command[1:]).strip()
        reference = await _resolve_reference(message, payload)
        if reference:
            processed = await _process_reference(client, message, reference)
            if processed:
                return

    buttons = [
        [
            InlineKeyboardButton("🆘 How To Use", callback_data="help_btn"),
            InlineKeyboardButton("ℹ️ About Bot", callback_data="about_btn"),
        ],
        [
             InlineKeyboardButton("⚙️ Settings", callback_data="settings_btn")
        ],
        [
            InlineKeyboardButton('📢 Official Channel', url='https://t.me/Coursesbuying'),
            InlineKeyboardButton('👨‍💻 Developer', url='https://t.me/Coursesbuying')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"<blockquote><b>👋 Welcome {message.from_user.mention}!</b></blockquote>\n\n"
            "<b>I am the Advanced Save Restricted Content Bot by Coursesbuying.</b>\n\n"
            "<blockquote><b>🚀 What I Can Do:</b>\n"
            "<b>‣ Save Restricted Post (Text, Media, Files)</b>\n"
            "<b>‣ Support Private & Public Channels</b>\n"
            f"<b>‣ Batch/Bulk Mode Supported</b>\n"
            f"<b>‣ Deep Link Support Enabled</b></blockquote>\n\n"
            "<blockquote><b>⚠️ Note:</b> <i>You must <code>/login</code> to your account to use the downloading features.</i></blockquote>"
        ),
        reply_markup=reply_markup,
        reply_to_message_id=message.id,
        parse_mode=enums.ParseMode.HTML
    )

    # try:
    #     await message.react(
    #         emoji=random.choice(REACTIONS),
    #         big=True
    #     )
    # except Exception as e:
    #     print(f"Reaction failed: {e}")

# -------------------
# Help command (standalone)
# -------------------

@Client.on_message(filters.command(["help"]))
async def send_help(client: Client, message: Message):
    await client.send_message(
        chat_id=message.chat.id,
        text=f"{HELP_TXT}"
    )

# -------------------
# Cancel command
# -------------------

@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in ACTIVE_BATCH_USERS or batch_temp.IS_BATCH.get(user_id) is False:
        batch_temp.IS_BATCH[user_id] = True
        await message.reply_text("❌ Batch Process Cancelled Successfully.")
    elif user_id in BATCH_WAITING_USERS:
        BATCH_WAITING_USERS.discard(user_id)
        await message.reply_text("❌ Batch prompt cancelled successfully.")
    else:
        await message.reply_text("❌ No Active Batch Process To Cancel.")

# -------------------
# Handle incoming messages
# -------------------

@Client.on_message(filters.text & filters.private & ~filters.regex("^/"))
async def save(client: Client, message: Message):
    if message.from_user and message.from_user.id in BATCH_WAITING_USERS:
        return

    reference = await _resolve_reference(message, message.text)
    if reference:
        await _process_reference(client, message, reference)

# -------------------
# Handle private content
# -------------------

async def handle_private(client: Client, acc, message: Message, chatid: int, msgid: int, source_kind: str, delete_words=None, replace_words=None):
    delete_words = delete_words or []
    replace_words = replace_words or {}
    try:
        if acc:
            msg: Message = await acc.get_messages(chatid, msgid)
        else:
            msg: Message = await client.get_messages(chatid, msgid)
    except (AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan) as e:
        batch_temp.IS_BATCH[message.from_user.id] = True
        await db.set_session(message.from_user.id, None)
        await client.send_message(message.chat.id, f"Session Token Invalid/Expired. Please /login again.\nError: {e}")
        return {"status": "error"}
    except Exception as e:
        # Handle PeerIdInvalid (which might come as generic Exception or RPCError)
        # We try to refresh dialogs to learn about the peer.
        logger.warning(f"Error fetching message: {e}. Refreshing dialogs...")
        try:
            async for dialog in acc.get_dialogs(limit=None):
                if dialog.chat.id == chatid:
                    break
            msg: Message = await acc.get_messages(chatid, msgid)
        except (AuthKeyUnregistered, UserDeactivated, UserDeactivatedBan) as e:
            batch_temp.IS_BATCH[message.from_user.id] = True
            await db.set_session(message.from_user.id, None)
            await client.send_message(message.chat.id, f"Session Token Invalid/Expired. Please /login again.\nError: {e}")
            return
        except Exception as e2:
            logger.error(f"Retry failed: {e2}")
            return {"status": "error"}
# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying

    if msg.empty:
        return {"status": "missing"}

    msg_type = get_message_type(msg)
    if not msg_type:
        return {"status": "missing"}

    chat = message.chat.id
    if batch_temp.IS_BATCH.get(message.from_user.id):
        return {"status": "cancelled"}

    if source_kind == 'public' and not acc:
        try:
            await client.copy_message(chat, msg.chat.id, msg.id, reply_to_message_id=message.id)
            return {"status": "sent"}
        except Exception as e:
            logger.error(f"Error copying public message: {e}")
            if ERROR_MESSAGE:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id,
                                          parse_mode=enums.ParseMode.HTML)
            return {"status": "error"}

    if "Text" == msg_type:
        try:
            text = _apply_word_rules(msg.text or "", delete_words, replace_words)
            if not text.strip():
                return {"status": "missing"}
            reply_markup = _build_reply_markup(msg)
            if text == (msg.text or "") and getattr(msg, 'entities', None):
                await client.send_message(
                    chat,
                    text,
                    entities=msg.entities,
                    reply_to_message_id=message.id,
                    reply_markup=reply_markup,
                )
            else:
                await client.send_message(
                    chat,
                    text,
                    reply_to_message_id=message.id,
                    reply_markup=reply_markup,
                )
            return {"status": "sent"}
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            if ERROR_MESSAGE:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id,
                                          parse_mode=enums.ParseMode.HTML)
            return {"status": "error"}

    smsg = await client.send_message(message.chat.id, '**__Downloading 🚀__**', reply_to_message_id=message.id)
    
    # ----------------------------------------
    # Create unique temp directory for this task
    # ----------------------------------------
    temp_dir = f"downloads/{message.id}"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    try:
        asyncio.create_task(downstatus(client, f'{message.id}downstatus.txt', smsg, chat))
    except Exception as e:
        logger.error(f"Error creating download status task: {e}")
        
    try:
        # Download into unique directory (folder path must end with / for Pyrogram)
        source_client = acc if acc else client
        file = await source_client.download_media(msg, file_name=f"{temp_dir}/", progress=progress, progress_args=[message, "down"])
        if os.path.exists(f'{message.id}downstatus.txt'):
            os.remove(f'{message.id}downstatus.txt')
    except Exception as e:
        # Check if cancelled (flag is True) or exception message contains "Cancelled"
        if batch_temp.IS_BATCH.get(message.from_user.id) or "Cancelled" in str(e):
            if os.path.exists(f'{message.id}downstatus.txt'):
                try:
                    os.remove(f'{message.id}downstatus.txt')
                except:
                    pass
            
            # Robust Cleanup: Delete the entire temp directory
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
            return await smsg.edit("❌ **Task Cancelled**")
            
        logger.error(f"Error downloading media: {e}")
        
        # Cleanup on error
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
                
        if ERROR_MESSAGE:
            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id,
                                      parse_mode=enums.ParseMode.HTML)
        await smsg.delete()
        return {"status": "error"}

    if batch_temp.IS_BATCH.get(message.from_user.id):
        # Cleanup if cancelled during gap
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        return {"status": "cancelled"}

    try:
        asyncio.create_task(upstatus(client, f'{message.id}upstatus.txt', smsg, chat))
    except Exception as e:
        logger.error(f"Error creating upload status task: {e}")
    caption = msg.caption if msg.caption else None
    caption = _apply_word_rules(caption or "", delete_words, replace_words) or None
    custom_thumb_path = await _get_custom_thumb_path(message.from_user.id, acc if acc else client)
    
    if batch_temp.IS_BATCH.get(message.from_user.id):
         # Cleanup if cancelled during gap
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        return

    try:
        if "Document" == msg_type:
            try:
                ph_path = await (acc if acc else client).download_media(msg.document.thumbs[0].file_id)
            except:
                ph_path = None
            thumb_for_upload = custom_thumb_path or ph_path
            await client.send_document(chat, file, thumb=thumb_for_upload, caption=caption, reply_to_message_id=message.id,
                                       parse_mode=enums.ParseMode.HTML, reply_markup=_build_reply_markup(msg),
                                       progress=progress, progress_args=[message, "up"])
            if custom_thumb_path and os.path.exists(custom_thumb_path):
                os.remove(custom_thumb_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)

        elif "Video" == msg_type:
            try:
                ph_path = await (acc if acc else client).download_media(msg.video.thumbs[0].file_id)
            except:
                ph_path = None
            thumb_for_upload = custom_thumb_path or ph_path
            await client.send_video(chat, file, duration=msg.video.duration, width=msg.video.width,
                                    height=msg.video.height, thumb=thumb_for_upload, caption=caption,
                                    reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML,
                                    reply_markup=_build_reply_markup(msg), progress=progress,
                                    progress_args=[message, "up"])
            if custom_thumb_path and os.path.exists(custom_thumb_path):
                os.remove(custom_thumb_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)

        elif "Animation" == msg_type:
            await client.send_animation(chat, file, caption=caption, reply_to_message_id=message.id,
                                        parse_mode=enums.ParseMode.HTML, reply_markup=_build_reply_markup(msg))

        elif "Sticker" == msg_type:
            await client.send_sticker(chat, file, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML,
                                       reply_markup=_build_reply_markup(msg))

        elif "Voice" == msg_type:
            await client.send_voice(chat, file, caption=caption,
                                    reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML,
                                    reply_markup=_build_reply_markup(msg), progress=progress,
                                    progress_args=[message, "up"])

        elif "Audio" == msg_type:
            try:
                ph_path = await (acc if acc else client).download_media(msg.audio.thumbs[0].file_id)
            except:
                ph_path = None
            thumb_for_upload = custom_thumb_path or ph_path
            await client.send_audio(chat, file, thumb=thumb_for_upload, caption=caption, reply_to_message_id=message.id,
                                    parse_mode=enums.ParseMode.HTML, reply_markup=_build_reply_markup(msg),
                                    progress=progress, progress_args=[message, "up"])
            if custom_thumb_path and os.path.exists(custom_thumb_path):
                os.remove(custom_thumb_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)

        elif "Photo" == msg_type:
            await client.send_photo(chat, file, caption=caption, reply_to_message_id=message.id,
                                    parse_mode=enums.ParseMode.HTML, reply_markup=_build_reply_markup(msg))
    except Exception as e:
        # Check if cancelled (flag is True) or exception message contains "Cancelled"
        if batch_temp.IS_BATCH.get(message.from_user.id) or "Cancelled" in str(e):
            if os.path.exists(f'{message.id}upstatus.txt'):
                try:
                    os.remove(f'{message.id}upstatus.txt')
                except:
                    pass
            
            # Robust Cleanup: Delete the entire temp directory
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            await smsg.edit("❌ **Task Cancelled**")
            return {"status": "cancelled"}

        logger.error(f"Error sending media: {e}")
        if ERROR_MESSAGE:
            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id,
                                      parse_mode=enums.ParseMode.HTML)

    if os.path.exists(f'{message.id}upstatus.txt'):
        os.remove(f'{message.id}upstatus.txt')
        
    # Final cleanup of temp directory
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

    await client.delete_messages(message.chat.id, [smsg.id])
    return {"status": "sent"}

#-------------------
# Get message type
# -------------------

def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    try:
        msg.document.file_id
        return "Document"
    except:
        pass
    try:
        msg.video.file_id
        return "Video"
    except:
        pass
    try:
        msg.animation.file_id
        return "Animation"
    except:
        pass
    try:
        msg.sticker.file_id
        return "Sticker"
    except:
        pass
    try:
        msg.voice.file_id
        return "Voice"
    except:
        pass
    try:
        msg.audio.file_id
        return "Audio"
    except:
        pass
    try:
        msg.photo.file_id
        return "Photo"
    except:
        pass
    try:
        msg.text
        return "Text"
    except:
        pass

# -------------------
# Inline button callback
# -------------------

@Client.on_callback_query()
async def button_callbacks(client: Client, callback_query):
    data = callback_query.data
    message = callback_query.message

    # Help button  
    if data == "help_btn":
        help_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Cʟᴏsᴇ ❌", callback_data="close_btn"),
                InlineKeyboardButton("⬅️ Bᴀᴄᴋ", callback_data="start_btn")
            ]
        ])
        await client.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=HELP_TXT,
            reply_markup=help_buttons,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        await callback_query.answer()

    # About button
    elif data == "about_btn":
        me = await client.get_me()
        about_text = (
            "<b><blockquote>‣ ℹ️ 𝐁𝐎𝐓 𝐈𝐍𝐅𝐎𝐑𝐌𝐀𝐓𝐈𝐎𝐍</blockquote>\n\n"
            "<i>• 🤖 𝐍𝐚𝐦𝐞 : 𝐒𝐚𝐯𝐞 𝐑𝐞𝐬𝐭𝐫𝐢𝐜𝐭𝐞𝐝 𝐂𝐨𝐧𝐭𝐞𝐧𝐭\n"
            "• 👨‍💻 𝐎𝐰𝐧𝐞𝐫 : <a href='https://t.me/Coursesbuying'>�𝐨𝐮𝐫�𝐬�𝐬�𝐛𝐮𝐲𝐢𝐧𝐠</a>\n"
            "• 📡 𝐔𝐩𝐝𝐚𝐭𝐞𝐬 : <a href='https://t.me/Coursesbuying'>𝐂𝐨𝐮𝐫𝐬𝐞𝐬𝐛𝐮𝐲𝐢𝐧𝐠</a>\n"
            "• 🐍 𝐋𝐚𝐧𝐠𝐮𝐚𝐠𝐞 : <a href='https://www.python.org/'>𝐏𝐲𝐭𝐡𝐨𝐧 𝟑</a>\n"
            "• 📚 𝐋𝐢𝐛𝐫𝐚𝐫𝐲 : <a href='https://docs.pyrogram.org/'>𝐏𝐲𝐫𝐨𝐠𝐫𝐚𝐦</a>\n"
            "• 🗄 𝐃𝐚𝐭𝐚𝐛𝐚𝐬𝐞 : <a href='https://www.mongodb.com/'>𝐌𝐨𝐧𝐠𝐨𝐃𝐁</a>\n"
            "• 📊 𝐕𝐞𝐫𝐬𝐢𝐨𝐧 : 𝟐.𝟎.𝟏 [𝐒𝐭𝐚𝐛𝐥𝐞]</i></b>"
        )

        about_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📢 Join Channel", url="https://t.me/Coursesbuying")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_btn"),
                InlineKeyboardButton("🔙 Back", callback_data="start_btn")
            ]
        ])

        await client.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=about_text,
            reply_markup=about_buttons,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        await callback_query.answer()

    # Home / Start button
    elif data == "start_btn":
        start_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🆘 How To Use", callback_data="help_btn"),
                InlineKeyboardButton("ℹ️ About Bot", callback_data="about_btn")
            ],
            [
                InlineKeyboardButton('📢 Official Channel', url='https://t.me/Coursesbuying'),
                InlineKeyboardButton('👨‍💻 Developer', url='https://t.me/Coursesbuying')
            ]
        ])
        await client.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=(
                f"<blockquote><b>👋 Welcome {callback_query.from_user.mention}!</b></blockquote>\n\n"
                "<b>I am the Advanced Save Restricted Content Bot by Coursesbuying.</b>\n\n"
                "<blockquote><b>🚀 What I Can Do:</b>\n"
                "<b>‣ Save Restricted Post (Text, Media, Files)</b>\n"
                "<b>‣ Support Private & Public Channels</b>\n"
                "<b>‣ Batch/Bulk Mode Supported</b></blockquote>\n\n"
                "<blockquote><b>⚠️ Note:</b> <i>You must <code>/login</code> to your account to use the downloading features.</i></blockquote>"
            ),
            reply_markup=start_buttons,
            parse_mode=enums.ParseMode.HTML
        )
        await callback_query.answer()

    # Settings button (Command List)
    elif data == "settings_btn":
        settings_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❌ Close", callback_data="close_btn"),
                InlineKeyboardButton("🔙 Back", callback_data="start_btn")
            ]
        ])
        await client.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=COMMANDS_TXT,
            reply_markup=settings_buttons,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        await callback_query.answer()

    # Close button
    elif data == "close_btn":
        await client.delete_messages(message.chat.id, [message.id])
        await callback_query.answer()


# Don't remove Credits
# Coursesbuying
# Developer Telegram @Coursesbuying
# Update channel - @Coursesbuying

# Coursesbuying
# Don't Remove Credit
# Telegram Channel @Coursesbuying
