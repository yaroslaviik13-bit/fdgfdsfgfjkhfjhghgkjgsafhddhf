import json
import time
import os
import sys
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6904586409  # Замени на свой ID если нужно

if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не установлен!")
    print("Добавьте в переменные окружения на bothost.ru:")
    print("Ключ: BOT_TOKEN")
    print("Значение: 8587220562:AAFKav1GMAcy8K195JUIcTHPDeLHxReU-rg")
    sys.exit(1)

LINKS_FILE = Path("data/message_links.json")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

message_links = {}
last_message_time = {}
ANTISPAM_SECONDS = 5


def save_links():
    try:
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(message_links, f, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")


def load_links():
    global message_links
    try:
        if LINKS_FILE.exists():
            with open(LINKS_FILE, "r", encoding="utf-8") as f:
                message_links = json.load(f)
                print(f"✅ Загружено {len(message_links)} связей")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        message_links = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"🟢 Команда /start от {update.effective_user.id}")
    await update.message.reply_text(
        "👋 Привет! Напишите мне сообщение, и я передам его администратору!"
    )


async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    now = time.time()

    print(f"📨 Сообщение от пользователя {user_id}")

    # AntiSpam
    last = last_message_time.get(user_id, 0)
    if now - last < ANTISPAM_SECONDS:
        print(f"⚠️ Антиспам для {user_id}")
        await update.message.reply_text("⏳ Подождите немного перед следующим сообщением.")
        return
    last_message_time[user_id] = now

    username = user.username or "без username"

    try:
        if update.message.text:
            print(f"📝 Текст от {user_id}: {update.message.text[:50]}...")
            sent = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📩 Сообщение от @{username} (ID: {user_id}):\n\n{update.message.text}"
            )
            message_links[str(sent.message_id)] = user_id
            save_links()
            await update.message.reply_text("✅ Сообщение отправлено администратору!")
        else:
            print(f"📎 Медиа от {user_id}")
            forwarded = await update.message.forward(chat_id=ADMIN_ID)
            info = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📩 Сообщение от @{username} (ID: {user_id})",
                reply_to_message_id=forwarded.message_id
            )
            message_links[str(info.message_id)] = user_id
            save_links()
            await update.message.reply_text("✅ Ваше сообщение отправлено!")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        await update.message.reply_text("❌ Ошибка отправки сообщения. Попробуйте позже.")


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        print(f"⚠️ Попытка ответа не от админа: {update.effective_user.id}")
        return

    if not update.message.reply_to_message:
        return

    admin_msg_id = str(update.message.reply_to_message.message_id)
    print(f"🔄 Ответ админа на сообщение {admin_msg_id}")

    if admin_msg_id not in message_links:
        await update.message.reply_text("❌ Не удалось найти пользователя.")
        return

    user_id = message_links[admin_msg_id]

    try:
        print(f"📤 Отправка ответа пользователю {user_id}")
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=ADMIN_ID,
            message_id=update.message.message_id
        )
        await update.message.reply_text("✅ Ответ отправлен пользователю!")
    except Exception as e:
        print(f"❌ Ошибка отправки ответа: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"🔥 Ошибка: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
        except:
            pass


def main():
    print("🤖 Запуск бота обратной связи...")
    print(f"📞 Админ ID: {ADMIN_ID}")
    print(f"🔑 Токен: {BOT_TOKEN[:10]}...")

    load_links()

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.User(ADMIN_ID),
        user_message
    ))
    application.add_handler(MessageHandler(
        ~filters.TEXT & ~filters.COMMAND & ~filters.User(ADMIN_ID),
        user_message
    ))
    application.add_handler(MessageHandler(
        filters.ALL & filters.User(ADMIN_ID),
        admin_reply
    ))

    application.add_error_handler(error_handler)

    print("✅ Бот запущен и готов к работе!")

    # Запускаем polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":

    main()
