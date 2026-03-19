from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import json
import os
from dotenv import load_dotenv

load_dotenv()

DB = "state.json"
bot_token = os.getenv("BOT_TOKEN")  # BotFather token

# ================== STATE ==================
def load_state():
    if os.path.exists(DB):
        with open(DB, "r") as f:
            data = json.load(f)
        if "settings" not in data:
            data["settings"] = {
                "allow_text": True,
                "allow_photo": False,
                "allow_voice": False,
                "allow_video": False,
                "allow_document": False,
                "allow_sticker": False
            }
        if "allowed" not in data:
            data["allowed"] = []
        return data
    return {
        "users": {},
        "settings": {
            "allow_text": True,
            "allow_photo": False,
            "allow_voice": False,
            "allow_video": False,
            "allow_document": False,
            "allow_sticker": False
        },
        "allowed": []
    }

def save_state(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=4)

state = load_state()
settings = state["settings"]
allowed_users = state["allowed"]

# ================== START ==================
async def start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("📝 Matn", callback_data="allow_text"),
         InlineKeyboardButton("🖼️ Rasm", callback_data="allow_photo")],
        [InlineKeyboardButton("🎤 Ovoz", callback_data="allow_voice"),
         InlineKeyboardButton("🎥 Video/GIF", callback_data="allow_video")],
        [InlineKeyboardButton("📄 PDF/Fayl", callback_data="allow_document"),
         InlineKeyboardButton("🤩 Sticker", callback_data="allow_sticker")]
    ]
    await update.message.reply_text(
        "⚙️ Xabar turlarini boshqarish:\nTanlangan bo‘lsa ruxsat beriladi, bekor qilinsa o‘chiriladi.\n\n"
        "🔹 Ruxsat berish uchun: /allow <ID>\n🔹 Ruxsat olib tashlash: /deny <ID>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================== TUGMALAR ==================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    state_data = load_state()
    settings = state_data["settings"]

    if data in settings:
        # Toggle ruxsat
        settings[data] = not settings[data]
        save_state(state_data)
        status = "✅ Ruxsat berildi" if settings[data] else "❌ Ruxsat o‘chirildi"
        await query.edit_message_text(f"{status} {data.replace('allow_', '').capitalize()}")
    else:
        await query.edit_message_text("❌ Noma’lum tugma.")

# ================== ID BERISH ==================
async def allow_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(context.args[0])
        state_data = load_state()
        allowed_users = state_data.get("allowed", [])
        if user_id not in allowed_users:
            allowed_users.append(user_id)
            state_data["allowed"] = allowed_users
            save_state(state_data)
            await update.message.reply_text(f"✅ ID {user_id} ruxsat oldi")
        else:
            await update.message.reply_text(f"⚠️ ID {user_id} allaqachon ruxsatli")
    except:
        await update.message.reply_text("❌ /allow <ID> formatida kiriting")

# ================== ID OLIB TASHLASH ==================
async def deny_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(context.args[0])
        state_data = load_state()
        allowed_users = state_data.get("allowed", [])
        if user_id in allowed_users:
            allowed_users.remove(user_id)
            state_data["allowed"] = allowed_users
            save_state(state_data)
            await update.message.reply_text(f"❌ ID {user_id} ruxsati olib tashlandi")
        else:
            await update.message.reply_text(f"⚠️ ID {user_id} ro‘yxatda yo‘q")
    except:
        await update.message.reply_text("❌ /deny <ID> formatida kiriting")

# ================== APPLICATION ==================
app = Application.builder().token(bot_token).build()
app.add_handler(CommandHandler("start", start_admin))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(CommandHandler("allow", allow_id))
app.add_handler(CommandHandler("deny", deny_id))

print("🔥 AdminBot ishga tushdi...")
app.run_polling()