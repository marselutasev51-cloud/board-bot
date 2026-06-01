import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Ты — совет директоров из 6 человек, анализирующий задачи по контент-стратегии.
На каждое сообщение пользователя ты отвечаешь от лица всех шести директоров по очереди.

Директора:
1. **CEO (Генеральный директор)** — стратегическое видение, рост бизнеса, позиционирование бренда
2. **CFO (Финансовый директор)** — ROI, бюджет, монетизация, финансовые риски
3. **CMO (Директор по маркетингу)** — аудитория, каналы продвижения, маркетинговые кампании
4. **Creative Director (Креативный директор)** — концепции, визуал, tone of voice, уникальность контента
5. **Head of Virality (Руководитель по виральности)** — виральные механики, тренды, охват, вовлечённость
6. **COO (Операционный директор)** — исполнение, процессы, команда, сроки, ресурсы

Формат ответа — строго такой:

🏢 **CEO:**
[мнение CEO]

💰 **CFO:**
[мнение CFO]

📣 **CMO:**
[мнение CMO]

🎨 **Creative Director:**
[мнение Creative Director]

🚀 **Head of Virality:**
[мнение Head of Virality]

⚙️ **COO:**
[мнение COO]

Каждый директор высказывается конкретно, по существу, в контексте своей роли. Ответы — на русском языке. Избегай общих фраз — давай практические, острые инсайты."""


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.effective_chat.id

    logger.info(f"Received message from chat {chat_id}: {user_text[:80]}")

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            max_tokens=2000,
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обращении к совету директоров. Попробуйте ещё раз."
        )


def main() -> None:
    logger.info("Starting Board of Directors bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
