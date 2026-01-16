import json
import time
import os
import sys
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8587220562:AAEY1HwkiWjRv7UKksLyCuNeTN9grQqRj2Y"
ADMIN_ID = 6904586409  # ТВОЙ ID (получи через @userinfobot если не уверен)
ANTISPAM_SECONDS = 3
# ===================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LINKS_FILE = DATA_DIR / "message_links.json"

message_links = {}
last_message_time = {}


def save_links():
    try:
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(message_links, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Сохранено {len(message_links)} связей")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}")


def load_links():
    global message_links
    try:
        if LINKS_FILE.exists():
            with open(LINKS_FILE, "r", encoding="utf-8") as f:
                message_links = json.load(f)
            logger.info(f"📂 Загружено {len(message_links)} связей")
        else:
            message_links = {}
            logger.info("📂 Файл связей не найден, создан новый")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки: {e}")
        message_links = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"🟢 /start от {user.id}")

    await update.message.reply_text(
        "🤖 *Бот обратной связи*\n\n"
        "Напишите сообщение - оно придет администратору.\n"
        "Админ ответит вам здесь же.\n\n"
        "Отправляйте текст, фото или файлы.",
        parse_mode="Markdown"
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ID пользователя"""
    user = update.effective_user
    logger.info(f"🆔 Запрос ID от {user.id}")

    await update.message.reply_text(
        f"*Ваш профиль:*\n"
        f"🆔 ID: `{user.id}`\n"
        f"👤 Username: @{user.username if user.username else 'нет'}\n"
        f"📝 Имя: {user.first_name if user.first_name else 'не указано'}\n\n"
        f"*Текущий админ ID:* `{ADMIN_ID}`",
        parse_mode="Markdown"
    )


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ЛЮБЫХ сообщений от пользователей (включая админа как пользователя)"""
    user = update.effective_user
    chat = update.effective_chat

    logger.info(f"📨 Сообщение от {user.id} (@{user.username})")

    # Если это не личный чат - игнорируем
    if chat.type != "private":
        return

    # Антиспам для обычных пользователей (но не для админа)
    if user.id != ADMIN_ID:
        now = time.time()
        if user.id in last_message_time:
            time_diff = now - last_message_time[user.id]
            if time_diff < ANTISPAM_SECONDS:
                await update.message.reply_text(f"⏳ Подождите {ANTISPAM_SECONDS} секунд")
                return
        last_message_time[user.id] = now

    # Формируем информацию о пользователе
    user_info = f"@{user.username}" if user.username else f"ID: {user.id}"
    if user.first_name:
        user_info = f"{user.first_name} ({user_info})"

    # Если это админ - добавляем пометку
    if user.id == ADMIN_ID:
        user_info = f"👑 АДМИН {user_info}"

    try:
        if update.message.text:
            # Отправляем текст админу (самому себе если ты админ)
            logger.info(f"📝 Текст от {user.id}: {update.message.text[:50]}...")

            sent_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📩 *Сообщение от {user_info}*\n\n{update.message.text}",
                parse_mode="Markdown"
            )

            # Сохраняем связь: ID сообщения → ID отправителя
            message_links[str(sent_msg.message_id)] = user.id
            save_links()

            # Отвечаем отправителю
            if user.id == ADMIN_ID:
                await update.message.reply_text("✅ Сообщение сохранено (ты админ)")
            else:
                await update.message.reply_text("✅ Сообщение отправлено администратору!")

        else:
            # Медиа (фото, файлы и т.д.)
            logger.info(f"📎 Медиа от {user.id}")

            # Пересылаем админу
            forwarded_msg = await update.message.forward(chat_id=ADMIN_ID)

            # Информационное сообщение админу
            info_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📎 *Медиа от {user_info}*",
                reply_to_message_id=forwarded_msg.message_id,
                parse_mode="Markdown"
            )

            # Сохраняем связи
            message_links[str(forwarded_msg.message_id)] = user.id
            message_links[str(info_msg.message_id)] = user.id
            save_links()

            await update.message.reply_text("✅ Медиа отправлено администратору!")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка отправки. Попробуйте позже.")


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ОТВЕТОВ админа (когда он отвечает на сообщение через Reply)"""
    user = update.effective_user

    # Только админ может отвечать
    if user.id != ADMIN_ID:
        return

    # Должен быть ответ на какое-то сообщение
    if not update.message.reply_to_message:
        return

    replied_msg_id = str(update.message.reply_to_message.message_id)
    logger.info(f"🔄 Ответ админа на сообщение {replied_msg_id}")

    # Ищем отправителя оригинального сообщения
    if replied_msg_id not in message_links:
        await update.message.reply_text("❌ Ошибка: Не могу найти отправителя.")
        return

    target_user_id = message_links[replied_msg_id]
    logger.info(f"📤 Отправка ответа пользователю {target_user_id}")

    try:
        if update.message.text:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"👨‍💼 *Ответ администратора:*\n\n{update.message.text}",
                parse_mode="Markdown"
            )
        else:
            # Если админ отправил медиа в ответ
            await context.bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )

        await update.message.reply_text("✅ Ответ отправлен!")

    except Exception as e:
        logger.error(f"❌ Ошибка отправки ответа: {e}")
        await update.message.reply_text(f"❌ Не удалось отправить: {e}")


def main():
    print("=" * 50)
    print("🤖 ТЕСТОВЫЙ БОТ ОБРАТНОЙ СВЯЗИ")
    print("=" * 50)

    print(f"🔑 Токен: {BOT_TOKEN[:10]}...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("=" * 50)

    # Загружаем сохраненные данные
    load_links()

    try:
        app = Application.builder().token(BOT_TOKEN).build()

        # Команды
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("id", id_command))

        # ВАЖНО: Сначала обработчик ответов админа
        app.add_handler(MessageHandler(
            filters.REPLY & filters.User(ADMIN_ID),
            handle_admin_reply
        ))

        # Затем обработчик ВСЕХ остальных сообщений
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_user_message
        ))

        # И обработчик медиа
        app.add_handler(MessageHandler(
            (~filters.TEXT) & filters.ChatType.PRIVATE,
            handle_user_message
        ))

        print("🟢 Бот запущен!")
        print("\n📱 ИНСТРУКЦИЯ ДЛЯ ТЕСТА:")
        print("1. Напиши боту любое сообщение (например 'тест')")
        print("2. Сообщение придет тебе же как админу")
        print("3. Ответь на него (Reply) - ответ вернется тебе же")
        print("\n🔧 Проверь свой ID командой /id")
        print("=" * 50)

        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
