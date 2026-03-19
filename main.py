import os
import json
import asyncio
import time
import random
from pathlib import Path

from dotenv import load_dotenv

from telethon import TelegramClient, events, errors
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeFilename

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

# ────────────────────────────────────────────────
#                     SOZLAMALAR
# ────────────────────────────────────────────────

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
OWNER_ID = int(os.getenv("OWNER_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = "state.json"
CONVERSATIONS_DIR = "conversations"

DEFAULT_PERMS = {
    "text": True, "photo": False, "voice": False,
    "video": False, "document": False, "sticker": True,
    "welcomed": False
}

DEFAULT_BLOCK_TEXT = "⛔ Bu turdagi narsa qabul qilinmaydi!\nFaqat ruxsat etilgan turlardan foydalaning."
DEFAULT_WELCOME_TEXT = "Assalomu alaykum! Qanday yordam bera olaman?"

RATE_LIMIT_SECONDS = 1.8
FORWARD_DELAY_MIN = 0.3
FORWARD_DELAY_MAX = 0.9
DELETE_DELAY = 0.07
OWNER_REPLY_DELAY_MIN = 1.8
OWNER_REPLY_DELAY_MAX = 3.5
WELCOME_DELAY_MIN = 0.5
WELCOME_DELAY_MAX = 1.4

# ────────────────────────────────────────────────
#                     DATABASE
# ────────────────────────────────────────────────

db_lock = asyncio.Lock()

async def load_db() -> dict:
    async with db_lock:
        if not os.path.exists(DB_FILE):
            return initialize_empty_db()
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("conversations", {})
            data.setdefault("media_files", {})
            data.setdefault("global_mode", False)
            data.setdefault("block_text", DEFAULT_BLOCK_TEXT)
            data.setdefault("welcome_text", DEFAULT_WELCOME_TEXT)
            return data
        except Exception:
            return initialize_empty_db()

def initialize_empty_db():
    return {
        "users": {}, "conversations": {}, "media_files": {},
        "global_mode": False, "block_text": DEFAULT_BLOCK_TEXT,
        "welcome_text": DEFAULT_WELCOME_TEXT
    }

async def save_db(data: dict):
    async with db_lock:
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[DB ERROR] {e}")

user_rate_limit = {}

# ────────────────────────────────────────────────
#                     USERBOT – REAL QOROVUL
# ────────────────────────────────────────────────

userbot = TelegramClient("user_session", API_ID, API_HASH)

def get_media_category(event) -> tuple[str, str]:
    if event.photo: return "photo", "Rasm"
    if event.voice: return "voice", "Ovozli xabar"
    if event.video: return "video", "Video"
    if event.sticker: return "sticker", "Sticker"
    if event.audio: return "voice", "Audio"
    if event.document:
        attrs = event.document.attributes or []
        if any(isinstance(a, DocumentAttributeAudio) for a in attrs):
            return "voice", "Audio fayl"
        return "document", "Fayl / PDF"
    if event.text and not event.media: return "text", "Matn"
    return "unknown", "Noma'lum"

@userbot.on(events.NewMessage(incoming=True))
async def user_handler(event):
    if not event.is_private or event.sender_id == OWNER_ID:
        return

    uid = str(event.sender_id)
    now = time.time()
    if now - user_rate_limit.get(uid, 0) < RATE_LIMIT_SECONDS:
        return
    user_rate_limit[uid] = now

    db = await load_db()
    db["users"].setdefault(uid, DEFAULT_PERMS.copy())

    perms = db["users"][uid]
    is_global = db.get("global_mode", False)
    effective_perms = {k: True for k in DEFAULT_PERMS if k != "welcomed"} if is_global else perms

    media_type, blocked_label = get_media_category(event)
    is_blocked = not effective_perms.get(media_type, False)

    # Salomlashuv (bir marta)
    if not perms.get("welcomed", False) and effective_perms.get("text", True):
        try:
            await asyncio.sleep(random.uniform(WELCOME_DELAY_MIN, WELCOME_DELAY_MAX))
            welcome = db.get("welcome_text", DEFAULT_WELCOME_TEXT)
            sent = await event.reply(welcome)
            db["conversations"].setdefault(uid, []).append({
                "time": sent.date.isoformat(), "from": "owner", "content": welcome
            })
            db["users"][uid]["welcomed"] = True
            await save_db(db)
        except:
            pass

    # Suhbatni saqlash
    content = event.text or f"[{media_type.upper()}]"
    db["conversations"].setdefault(uid, []).append({
        "time": event.date.isoformat(),
        "from": "user",
        "content": content,
        "has_media": bool(event.media),
        "media_type": media_type,
        "blocked": is_blocked
    })
    await save_db(db)

    # Ownerga yuborish (Copy — Izbrannoye ga tushmaydi!)
    try:
        sender = await event.get_sender()
        name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        username = f"@{sender.username}" if sender.username else "yo‘q"

        header = f"📥 {name} | {username} | {uid}"
        if is_blocked:
            header += f"  🚫 {blocked_label} — Ruxsatnoma kerak"
        header += "\n━━━━━━━━━━\n"

        await asyncio.sleep(random.uniform(FORWARD_DELAY_MIN, FORWARD_DELAY_MAX))
        await userbot.send_message(OWNER_ID, header)
        await event.copy(OWNER_ID)   # ← Copy! (muhim)

    except Exception as e:
        print(f"[SEND ERROR] {uid}: {e}")

    # Bloklangan bo‘lsa — javob berish + o‘chirish
    if is_blocked:
        try:
            block_msg = db.get("block_text", DEFAULT_BLOCK_TEXT)
            await asyncio.sleep(0.1)
            await event.reply(block_msg)
            await asyncio.sleep(DELETE_DELAY)
            await event.delete()
        except Exception as e:
            print(f"[BLOCK ERROR] {uid}: {e}")

    if media_type != "text":
        print(f"[{'BLOCKED' if is_blocked else 'ALLOWED'} {media_type.upper()}] {uid}")


# Owner javobi (tuzatildi)
@userbot.on(events.NewMessage(from_users=OWNER_ID))
async def owner_handler(event):
    if not event.is_reply:
        return
    replied = await event.get_reply_message()
    if not replied or not replied.forward or not replied.forward.sender_id:
        return

    uid = str(replied.forward.sender_id)

    await asyncio.sleep(random.uniform(OWNER_REPLY_DELAY_MIN, OWNER_REPLY_DELAY_MAX))

    try:
        # Forward emas — copy qilamiz (foydalanuvchiga toza yetib borishi uchun)
        await event.copy(int(uid))
    except Exception as e:
        print(f"[OWNER→USER ERROR] {uid}: {e}")

    # Media saqlash
    if event.media:
        asyncio.create_task(save_media(event, uid))

    content = event.text or "[Media]"
    db = await load_db()
    db["conversations"].setdefault(uid, []).append({
        "time": event.date.isoformat(),
        "from": "owner",
        "content": content,
        "has_media": bool(event.media)
    })
    await save_db(db)


async def save_media(event, uid: str):
    try:
        user_dir = Path(CONVERSATIONS_DIR) / uid
        user_dir.mkdir(parents=True, exist_ok=True)

        media_type, _ = get_media_category(event)

        # Fayl kengaytmasini aniqlash
        ext = ".bin"
        if media_type == "photo": ext = ".jpg"
        elif media_type == "video": ext = ".mp4"
        elif media_type == "voice":
            ext = ".ogg" if getattr(event, 'voice', None) else ".mp3"
        elif media_type == "document":
            for attr in event.document.attributes or []:
                if isinstance(attr, DocumentAttributeFilename) and "." in attr.file_name:
                    ext = os.path.splitext(attr.file_name)[1]
                    break
        elif media_type == "sticker": ext = ".webp"

        filename = f"{event.id}_{media_type}_{int(time.time())}{ext}"
        file_path = user_dir / filename

        downloaded = await event.download_media(file=str(file_path))
        if downloaded:
            real_path = Path(downloaded).resolve()
            size = real_path.stat().st_size

            db = await load_db()
            db["media_files"].setdefault(uid, []).append({
                "time": event.date.isoformat(),
                "message_id": event.id,
                "path": str(real_path),
                "type": media_type,
                "size": size,
                "extension": ext
            })
            await save_db(db)
            print(f"[MEDIA SAVED] {uid} → {media_type} ({size} bayt)")
    except Exception as e:
        print(f"[MEDIA SAVE ERROR] {uid}: {e}")


# ────────────────────────────────────────────────
#                     ADMIN BOT
# ────────────────────────────────────────────────

admin_app = Application.builder().token(BOT_TOKEN).build()
USER_STATES = {}

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Ruxsat berish", callback_data="allow"),
         InlineKeyboardButton("➖ Taqiqlash", callback_data="deny")],
        [InlineKeyboardButton("📊 Tekshirish", callback_data="check"),
         InlineKeyboardButton("📜 Matn tarixi", callback_data="history_text")],
        [InlineKeyboardButton("🖼 Barcha media", callback_data="all_media")],
        [InlineKeyboardButton("🌍 Global rejim", callback_data="global")],
        [InlineKeyboardButton("✏️ Blok matn", callback_data="edit_block"),
         InlineKeyboardButton("✏️ Salomlashuv", callback_data="edit_welcome")],
    ])

def type_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Matn", callback_data="text"), InlineKeyboardButton("Rasm", callback_data="photo")],
        [InlineKeyboardButton("Ovoz/Audio", callback_data="voice"), InlineKeyboardButton("Video", callback_data="video")],
        [InlineKeyboardButton("Fayl/PDF", callback_data="document"), InlineKeyboardButton("Sticker", callback_data="sticker")],
        [InlineKeyboardButton("🔙 Ortga", callback_data="back")],
    ])

def global_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yoqish", callback_data="global_on"),
         InlineKeyboardButton("❌ O‘chirish", callback_data="global_off")],
        [InlineKeyboardButton("🔙 Ortga", callback_data="back")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text("👑 ADMIN PANEL", reply_markup=main_menu())

async def show_media_list(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str, page=0):
    db = await load_db()
    media_list = db["media_files"].get(uid, [])
    if not media_list:
        await context.bot.send_message(OWNER_ID, f"🆔 {uid} uchun hech qanday media topilmadi.", reply_markup=main_menu())
        return

    media_list = sorted(media_list, key=lambda x: x["time"], reverse=True)
    per_page = 8
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current = media_list[start_idx:end_idx]

    text = f"🖼 {uid} — Media fayllar ({len(media_list)} ta)\n\n"
    keyboard = []

    for m in current:
        size_mb = round(m["size"] / (1024*1024), 2)
        text += f"• {m['time'][:19]} | {m['type'].upper()} | {size_mb} MB\n"
        keyboard.append([InlineKeyboardButton(
            f"📎 {m['type'].upper()} — {m['time'][11:16]}",
            callback_data=f"media_{uid}_{m['message_id']}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"media_page_{uid}_{page-1}"))
    if end_idx < len(media_list):
        nav.append(InlineKeyboardButton("➡️ Keyingi", callback_data=f"media_page_{uid}_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔙 Asosiy menyuga", callback_data="back")])

    await context.bot.send_message(OWNER_ID, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID: return
    data = query.data

    try:
        await query.message.delete()
    except:
        pass

    if data == "back":
        await context.bot.send_message(OWNER_ID, "👑 ADMIN PANEL", reply_markup=main_menu())
        USER_STATES.pop(OWNER_ID, None)
        return

    if data == "global":
        await context.bot.send_message(OWNER_ID, "Global rejimni tanlang:", reply_markup=global_menu())
        return

    if data in ("global_on", "global_off"):
        db = await load_db()
        db["global_mode"] = (data == "global_on")
        await save_db(db)
        st = "yoqildi ✅" if data == "global_on" else "o‘chirildi ❌"
        await context.bot.send_message(OWNER_ID, f"🌍 Global rejim {st}", reply_markup=main_menu())
        return

    if data in ("edit_block", "edit_welcome"):
        t = "blok matn" if data == "edit_block" else "salomlashuv matn"
        await context.bot.send_message(OWNER_ID, f"Yangi {t} kiriting:")
        USER_STATES[OWNER_ID] = {"action": data}
        return

    if data in ("allow", "deny"):
        USER_STATES[OWNER_ID] = {"action": data}
        await context.bot.send_message(OWNER_ID, "Qaysi tur uchun?", reply_markup=type_menu())
        return

    if data in DEFAULT_PERMS and data != "welcomed":
        state = USER_STATES.get(OWNER_ID, {})
        if state.get("action") not in ("allow", "deny"):
            await context.bot.send_message(OWNER_ID, "Avval ruxsat/taqiqlashni tanlang.", reply_markup=main_menu())
            return
        USER_STATES[OWNER_ID]["type"] = data
        await context.bot.send_message(OWNER_ID, "Foydalanuvchi ID sini yozing:")
        return

    if data in ("check", "history_text", "all_media"):
        names = {"check": "tekshirish", "history_text": "matn tarixi", "all_media": "media"}
        await context.bot.send_message(OWNER_ID, f"{names[data]} uchun ID kiriting:")
        USER_STATES[OWNER_ID] = {"action": data}
        return

    # Media pagination
    if data.startswith("media_page_"):
        _, uid, page = data.split("_")
        await show_media_list(update, context, uid, int(page))
        return

    # Bitta media ochish
    if data.startswith("media_"):
        _, uid, msg_id = data.split("_")
        db = await load_db()
        media_list = db["media_files"].get(uid, [])
        media = next((m for m in media_list if str(m["message_id"]) == msg_id), None)
        if not media or not os.path.exists(media["path"]):
            await context.bot.send_message(OWNER_ID, "❌ Media topilmadi yoki fayl o‘chirilgan.")
            return

        keyboard = [
            [InlineKeyboardButton("📥 Yuklab olish", callback_data=f"download_{uid}_{msg_id}")],
            [InlineKeyboardButton("🗑 O‘chirish", callback_data=f"delmedia_{uid}_{msg_id}")],
            [InlineKeyboardButton("🔙 Ro‘yxatga", callback_data=f"media_page_{uid}_0")]
        ]

        caption = f"🆔 {uid}\n📁 {media['type'].upper()} | {media['time'][:19]} | {round(media['size']/1024/1024, 2)} MB"

        path = media["path"]
        if media["type"] == "photo":
            await context.bot.send_photo(OWNER_ID, open(path, "rb"), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        elif media["type"] == "video":
            await context.bot.send_video(OWNER_ID, open(path, "rb"), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        elif media["type"] == "voice":
            await context.bot.send_voice(OWNER_ID, open(path, "rb"), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_document(OWNER_ID, open(path, "rb"), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("download_"):
        _, uid, msg_id = data.split("_")
        db = await load_db()
        media = next((m for m in db["media_files"].get(uid, []) if str(m["message_id"]) == msg_id), None)
        if media and os.path.exists(media["path"]):
            await context.bot.send_document(OWNER_ID, open(media["path"], "rb"), caption="📥 Yuklab olindi")
        return

    if data.startswith("delmedia_"):
        _, uid, msg_id = data.split("_")
        db = await load_db()
        media_list = db["media_files"].get(uid, [])
        for m in media_list[:]:
            if str(m["message_id"]) == msg_id:
                try:
                    os.remove(m["path"])
                except:
                    pass
                media_list.remove(m)
                break
        await save_db(db)
        await context.bot.send_message(OWNER_ID, "✅ Media fayl o‘chirildi.", reply_markup=main_menu())
        return


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    text = update.message.text.strip()
    state = USER_STATES.get(OWNER_ID, {})
    action = state.get("action")

    if not action:
        await update.message.reply_text("Noma'lum buyruq.", reply_markup=main_menu())
        return

    db = await load_db()

    if action in ("edit_block", "edit_welcome"):
        key = "block_text" if action == "edit_block" else "welcome_text"
        db[key] = text
        await save_db(db)
        await update.message.reply_text(f"✅ Yangilandi!\n\n{text}", reply_markup=main_menu())
        USER_STATES.pop(OWNER_ID, None)
        return

    if not text.isdigit():
        await update.message.reply_text("❌ Faqat raqamli ID kiriting.", reply_markup=main_menu())
        return

    uid = text

    if action == "check":
        perms = db["users"].get(uid, DEFAULT_PERMS.copy())
        res = "\n".join(f"{k:<10}: {'✅' if v else '❌'}" for k, v in perms.items() if k != "welcomed")
        await update.message.reply_text(f"🆔 {uid}\n\n{res}", reply_markup=main_menu())

    elif action == "history_text":
        conv = db["conversations"].get(uid, [])
        if not conv:
            await update.message.reply_text("Tarix bo‘sh.", reply_markup=main_menu())
            return
        lines = [f"{m['time'][:19]} {'👤' if m['from']=='user' else '👑'}: {m['content'][:120]}"
                 for m in sorted(conv, key=lambda x: x["time"])[-30:]]
        await update.message.reply_text("📜 So‘nggi 30 ta xabar:\n\n" + "\n".join(lines), reply_markup=main_menu())

    elif action == "all_media":
        await show_media_list(update, context, uid, page=0)

    elif state.get("type"):
        mtype = state["type"]
        db["users"].setdefault(uid, DEFAULT_PERMS.copy())
        db["users"][uid][mtype] = (action == "allow")
        await save_db(db)
        st = "ruxsat berildi ✅" if action == "allow" else "taqiqlandi ❌"
        await update.message.reply_text(f"{mtype.upper()} → {st}\nID: {uid}", reply_markup=main_menu())

    USER_STATES.pop(OWNER_ID, None)


# ────────────────────────────────────────────────
#                     ISHGA TUSHIRISH
# ────────────────────────────────────────────────

async def main():
    try:
        await userbot.start(phone=PHONE)
        print("✅ REAL QOROVUL TIZIMI MUVOFAQQIYATLI ISHGA TUSHDI!")
        print("   (Izbrannoye ga hech narsa tushmaydi)")
    except errors.PhoneNumberBannedError:
        print("❌ HISOB BAN QILINGAN!")
        return
    except Exception as e:
        print(f"[START ERROR] {e}")
        return

    admin_app.add_handler(CommandHandler("start", start))
    admin_app.add_handler(CallbackQueryHandler(callback_handler))
    admin_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    await admin_app.initialize()
    await admin_app.start()
    await admin_app.updater.start_polling(drop_pending_updates=True)

    print("🚀 Tizim to‘liq ishlamoqda! /start buyrug‘i bilan admin panelni oching.")
    await userbot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())