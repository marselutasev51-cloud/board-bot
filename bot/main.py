import os
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

MAX_HISTORY = 20

chat_histories: dict[int, list[dict]] = defaultdict(list)

SYSTEM_PROMPT = """Ты — совет директоров из 6 человек, анализирующий задачи по контент-стратегии.
На каждое сообщение пользователя ты отвечаешь от лица всех шести директоров по очереди.

Директора:
1. CEO (Генеральный директор) — стратегическое видение, рост бизнеса, позиционирование бренда
2. CFO (Финансовый директор) — ROI, бюджет, монетизация, финансовые риски
3. CMO (Директор по маркетингу) — аудитория, каналы продвижения, маркетинговые кампании
4. Creative Director (Креативный директор) — концепции, визуал, tone of voice, уникальность контента
5. Head of Virality (Руководитель по виральности) — виральные механики, тренды, охват, вовлечённость
6. COO (Операционный директор) — исполнение, процессы, команда, сроки, ресурсы

Формат ответа — строго такой (используй одиночные звёздочки для жирного текста):

🏢 *CEO:*
[мнение CEO]

💰 *CFO:*
[мнение CFO]

📣 *CMO:*
[мнение CMO]

🎨 *Creative Director:*
[мнение Creative Director]

🚀 *Head of Virality:*
[мнение Head of Virality]

⚙️ *COO:*
[мнение COO]

Каждый директор высказывается конкретно, по существу, в контексте своей роли. Ответы — на русском языке. Избегай общих фраз — давай практические, острые инсайты.
Помни контекст предыдущих сообщений в этом разговоре и ссылайся на него при необходимости.
Важно: не используй двойные звёздочки (**), только одиночные (*) для жирного текста."""

START_TEXT = """👋 Добро пожаловать в *Совет директоров*!

Здесь вашу задачу по контент-стратегии разбирают шесть топ-менеджеров:

🏢 *CEO* — стратегия и позиционирование бренда
💰 *CFO* — бюджет, ROI и монетизация
📣 *CMO* — аудитория, каналы и кампании
🎨 *Creative Director* — концепции, визуал и tone of voice
🚀 *Head of Virality* — виральность, тренды и охват
⚙️ *COO* — исполнение, процессы и сроки

Просто напишите задачу или вопрос — и совет немедленно приступит к работе.

Например:
• _«Нужно запустить новый продукт в соцсетях за 2 недели»_
• _«Какой контент лучше всего работает для B2B-аудитории?»_
• _«Как увеличить органический охват без бюджета?»_"""

HELP_TEXT = """ℹ️ *Как пользоваться ботом*

Отправьте любое сообщение с задачей или вопросом по контент-стратегии — и все шесть директоров выскажут своё мнение.

*Что можно спрашивать:*
• Стратегия запуска продукта или кампании
• Выбор каналов и форматов контента
• Анализ идей и гипотез
• Планирование бюджета на контент
• Виральные механики и growth-стратегии
• Процессы производства и дистрибуции контента

*Команды:*
/start — приветствие и знакомство с советом
/help — эта справка
/summary — итоги разговора: ключевые решения и задачи
/reset — очистить историю разговора и начать заново

*Совет:* чем конкретнее задача, тем точнее и полезнее ответы директоров."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    logger.info(f"User {update.effective_user.id} started the bot")
    chat_histories[chat_id].clear()
    await update.message.reply_text(START_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"User {update.effective_user.id} requested help")
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


SUMMARY_PROMPT = """Подведи итоги нашего разговора от лица совета директоров.
Структурируй ответ так (используй одиночные звёздочки для жирного текста):

📋 *Итоги заседания совета директоров*

*Что обсуждали:*
[1-2 предложения о теме разговора]

*Ключевые решения и выводы:*
[пронумерованный список главных инсайтов и договорённостей из разговора]

*Задачи к исполнению:*
[пронумерованный список конкретных следующих шагов, которые были названы или вытекают из обсуждения, с указанием ответственного директора где уместно]

Будь конкретным — опирайся только на то, что реально обсуждалось в этом разговоре.
Важно: не используй двойные звёздочки (**), только одиночные (*) для жирного текста."""


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    history = chat_histories[chat_id]

    if not history:
        await update.message.reply_text(
            "📋 Пока нечего подводить — разговор ещё не начался. Напишите задачу совету директоров!"
        )
        return

    logger.info(f"Chat {chat_id} requested summary")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history[-MAX_HISTORY:]
        + [{"role": "user", "content": SUMMARY_PROMPT}]
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1500,
        )
        reply = response.choices[0].message.content
        try:
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        await update.message.reply_text(
            "⚠️ Не удалось подготовить итоги. Попробуйте ещё раз."
        )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat_histories[chat_id].clear()
    logger.info(f"Chat {chat_id} history cleared")
    await update.message.reply_text(
        "🔄 История разговора очищена. Совет директоров готов к новой задаче.",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.effective_chat.id

    logger.info(f"Received message from chat {chat_id}: {user_text[:80]}")

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    history = chat_histories[chat_id]
    history.append({"role": "user", "content": user_text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=2000,
        )

        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})

        try:
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"Error calling OpenAI: {e}")
        history.pop()
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обращении к совету директоров. Попробуйте ещё раз."
        )


def main() -> None:
    logger.info("Starting Board of Directors bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
