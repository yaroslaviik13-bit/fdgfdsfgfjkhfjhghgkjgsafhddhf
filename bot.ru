import json
import time
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = "8587220562:AAFKav1GMAcy8K195JUIcTHPDeLHxReU-rg"
ADMIN_ID = 8590016146

LINKS_FILE = Path("message_links.json")
message_links = {}
last_message_time = {}
ANTISPAM_SECONDS = 5


def save_links():
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(message_links, f)


def load_links():
    global message_links
    if LINKS_FILE.exists():
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            message_links = json.load(f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напишите сообщение — я передам его администратору 😊")


async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    now = time.time()

    # AntiSpam
    last = last_message_time.get(user_id, 0)
    if now - last < ANTISPAM_SECONDS:
        await update.message.reply_text("⏳ Не так быстро! Подождите немного.")
        return
    last_message_time[user_id] = now

    username = user.username or "без username"

    if update.message.text:
        sent = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 Сообщение от @{username} (ID: {user.id}):\n\n{update.message.text}"
        )
        message_links[str(sent.message_id)] = user.id
        save_links()
        await update.message.reply_text("✅ Сообщение отправлено администратору!")
        return

    forwarded = await update.message.forward(chat_id=ADMIN_ID)
    info = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 Сообщение от @{username} (ID: {user.id})",
        reply_to_message_id=forwarded.message_id
    )
    message_links[str(info.message_id)] = user.id
    save_links()
    await update.message.reply_text("✅ Ваше сообщение отправлено!")


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    admin_msg_id = str(update.message.reply_to_message.message_id)

    if admin_msg_id not in message_links:
        await update.message.reply_text("❌ Не смог найти пользователя.")
        return

    user_id = message_links[admin_msg_id]

    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=ADMIN_ID,
            message_id=update.message.message_id
        )
        await update.message.reply_text("✅ Отправлено пользователю!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


def main():
    load_links()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(~filters.User(user_id=ADMIN_ID), user_message))
    app.add_handler(MessageHandler(filters.User(user_id=ADMIN_ID), admin_reply))

    print("Бот запущен 🤖")

    # Для bothost.ru - используй run_webhook, а не run_polling
    # Но bothost.ru сам устанавливает вебхук, так что просто run_polling
    app.run_polling()


if __name__ == "__main__":
    main()
