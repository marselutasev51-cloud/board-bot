import os
import asyncio
import logging
import time
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
MAX_MSG_LEN = 4000
RATE_LIMIT_SECONDS = 8

chat_histories: dict[int, list[dict]] = defaultdict(list)
last_request_ts: dict[int, float] = {}

DIRECTORS_MAP = {
    "ceo": "CEO",
    "cfo": "CFO",
    "cmo": "CMO",
    "creative": "Creative Director",
    "virality": "Head of Virality",
    "coo": "COO",
}

SYSTEM_PROMPT = """Ты — совет директоров из 6 человек, каждый со своей яркой личностью и позицией. Анализируешь задачи по контент-стратегии.

*Личности директоров:*

🏢 *CEO (Алексей)* — мыслит 3-5-летними горизонтами, нетерпелив к деталям, режет суть до одного слова. Ищет асимметричные возможности. Иногда жёстко прерывает CFO, когда тот слишком консервативен. Говорит короткими, резкими фразами.

💰 *CFO (Марина)* — скептик по природе. Любую идею сначала ломает через unit-экономику. Не против риска — против неизмеримого риска. Цитирует конкретные цифры, даже если это диапазон. Спорит с CMO о том, что важнее — охват или конверсия.

📣 *CMO (Дмитрий)* — живёт в данных аудитории и трендах. Думает сегментами, а не «всей аудиторией». Часто не соглашается с Creative Director: красота ≠ конверсия. Всегда называет конкретный канал и метрику успеха.

🎨 *Creative Director (Соня)* — провокатор. Её первая реакция — «а что если сделать наоборот?». Видит там, где другие не видят. Уважает CMO, но убеждена: люди помнят эмоцию, а не CTR. Говорит образами и аналогиями.

🚀 *Head of Virality (Макс)* — прагматик виральности, без романтики. Знает: вирусность — это механика, а не удача. Называет конкретные тактики: петли, триггеры, форматы. Нетерпим к общим словам — требует «покажи пример».

⚙️ *COO (Наташа)* — хранитель реальности. Переводит любую идею в: кто делает, сколько стоит, когда готово. Не убивает идеи — она ихземляет. Часто задаёт неудобный вопрос «а у нас есть на это ресурс?».

*Правила:*
- Каждый директор говорит от первого лица, в своём стиле
- Директора могут прямо ссылаться на слова коллег («Согласен с Мариной, но...», «Соня, это красиво, но вот цифра...»)
- Каждый даёт ОДНО конкретное действие в конце своего блока
- Ответы на русском, без воды
- Не используй двойные звёздочки (**), только одиночные (*) для жирного

*Формат каждого блока:*
[эмодзи] *[Роль]:*
[мнение, 3-5 предложений, острое и конкретное]
→ *Действие:* [одно конкретное следующее действие]

Помни контекст предыдущих сообщений — ссылайся на него."""

FOCUS_SYSTEM_PROMPT_TEMPLATE = """Ты — {name}, член совета директоров. Отвечаешь развёрнуто и глубоко, только от своего лица.

{persona}

Пользователь просит твой детальный анализ. Дай развёрнутый ответ:
- Твоя оценка ситуации (что видишь, что тебя беспокоит / радует)
- 3-5 конкретных рекомендаций с обоснованием
- Риски, которые другие могут не заметить
- Итоговый приоритет действий

Отвечай в первом лице, в своём стиле. Без воды. Ответ на русском.
Не используй двойные звёздочки (**), только одиночные (*) для жирного."""

PERSONAS = {
    "ceo": ("🏢", "CEO (Алексей)", "Ты мыслишь 3-5-летними горизонтами, ищешь асимметричные возможности, режешь суть до главного. Нетерпелив к деталям, говоришь короткими резкими фразами. Тебе интересны стратегия, позиционирование, рост."),
    "cfo": ("💰", "CFO (Марина)", "Ты скептик по природе. Любую идею ломаешь через unit-экономику. Не против риска — против неизмеримого. Всегда называешь конкретные цифры, даже если это диапазон. Фокус: ROI, бюджет, монетизация, риски."),
    "cmo": ("📣", "CMO (Дмитрий)", "Ты живёшь в данных аудитории. Думаешь сегментами, называешь конкретный канал и метрику успеха. Фокус: аудитория, каналы, воронка, конверсия."),
    "creative": ("🎨", "Creative Director (Соня)", "Ты провокатор. Первая реакция — «а что если наоборот?». Говоришь образами. Убеждена: люди помнят эмоцию, а не CTR. Фокус: концепция, визуал, tone of voice, уникальность."),
    "virality": ("🚀", "Head of Virality (Макс)", "Ты прагматик виральности. Знаешь: вирусность — это механика, не удача. Называешь конкретные тактики: петли, триггеры, форматы. Нетерпим к общим словам. Фокус: охват, вовлечённость, виральные механики."),
    "coo": ("⚙️", "COO (Наташа)", "Ты хранитель реальности. Переводишь любую идею в: кто делает, сколько стоит, когда готово. Задаёшь неудобный вопрос «а у нас есть на это ресурс?». Фокус: исполнение, процессы, сроки, команда."),
}

SUMMARY_PROMPT = """Подведи итоги нашего разговора от лица всего совета директоров.
Используй одиночные звёздочки (*) для жирного текста, не двойные.

📋 *Итоги заседания*

*Тема:*
[1-2 предложения]

*Ключевые решения и инсайты:*
[нумерованный список, с указанием кто предложил]

*Разногласия в совете:*
[если были — кто с кем расходился и в чём]

*Приоритетные действия:*
[нумерованный список конкретных шагов с ответственным]

Только то, что реально обсуждалось. Без воды."""

START_TEXT = """👋 Добро пожаловать в *Совет директоров*!

Ваши задачи по контент-стратегии разбирают шесть топ-менеджеров с разными взглядами:

🏢 *CEO Алексей* — стратегия и асимметричные возможности
💰 *CFO Марина* — ROI, бюджет, unit-экономика
📣 *CMO Дмитрий* — аудитория, каналы, конверсия
🎨 *Creative Director Соня* — концепции, эмоция, tone of voice
🚀 *Head of Virality Макс* — виральные механики, охват
⚙️ *COO Наташа* — исполнение, ресурсы, сроки

Напишите задачу — совет немедленно приступит к работе.

*Команды:*
/focus `ceo` | `cfo` | `cmo` | `creative` | `virality` | `coo` — глубокий анализ от одного директора
/summary — итоги разговора
/reset — начать заново
/help — справка"""

HELP_TEXT = """ℹ️ *Как пользоваться ботом*

Отправьте любой вопрос или задачу по контент-стратегии.

*Команды:*
/start — приветствие
/help — эта справка
/focus `<роль>` — глубокий анализ от одного директора
/summary — итоги разговора с решениями и задачами
/reset — очистить историю

*Роли для /focus:*
`ceo` `cfo` `cmo` `creative` `virality` `coo`

Пример: `/focus cfo Нужно ли вкладывать в платное продвижение?`

*Совет:* чем конкретнее задача — тем острее ответы."""


def split_long_message(text: str) -> list[str]:
    if len(text) <= MAX_MSG_LEN:
        return [text]
    chunks = []
    while text:
        if len(text) <= MAX_MSG_LEN:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, MAX_MSG_LEN)
        if split_at == -1:
            split_at = text.rfind("\n", 0, MAX_MSG_LEN)
        if split_at == -1:
            split_at = MAX_MSG_LEN
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip("\n")
    return chunks


async def keep_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass


async def send_reply(update: Update, text: str) -> None:
    for chunk in split_long_message(text):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)


def check_rate_limit(chat_id: int) -> float:
    now = time.monotonic()
    last = last_request_ts.get(chat_id, 0)
    wait = RATE_LIMIT_SECONDS - (now - last)
    return wait if wait > 0 else 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat_histories[chat_id].clear()
    logger.info(f"User {update.effective_user.id} started")
    await update.message.reply_text(START_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat_histories[chat_id].clear()
    logger.info(f"Chat {chat_id} reset")
    await update.message.reply_text("🔄 История очищена. Совет готов к новой задаче.")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    history = chat_histories[chat_id]
    if not history:
        await update.message.reply_text("📋 Разговор ещё не начался — нечего подводить.")
        return

    logger.info(f"Chat {chat_id} requested summary")
    stop = asyncio.Event()
    asyncio.create_task(keep_typing(context, chat_id, stop))

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history[-MAX_HISTORY:]
        + [{"role": "user", "content": SUMMARY_PROMPT}]
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, max_tokens=1500
        )
        stop.set()
        await send_reply(update, response.choices[0].message.content)
    except Exception as e:
        stop.set()
        logger.error(f"Summary error: {e}")
        await update.message.reply_text("⚠️ Не удалось подготовить итоги. Попробуйте ещё раз.")


async def focus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        roles = " | ".join(f"`{k}`" for k in PERSONAS)
        await update.message.reply_text(
            f"Укажите роль и вопрос.\nПример: `/focus cfo Стоит ли запускать платную рекламу?`\n\nРоли: {roles}",
            parse_mode="Markdown",
        )
        return

    role_key = args[0].lower()
    if role_key not in PERSONAS:
        roles = ", ".join(PERSONAS.keys())
        await update.message.reply_text(f"Неизвестная роль. Доступные: {roles}")
        return

    wait = check_rate_limit(chat_id)
    if wait > 0:
        await update.message.reply_text(f"⏳ Подождите {wait:.0f} сек. между запросами.")
        return

    question = " ".join(args[1:]) if len(args) > 1 else None
    if not question:
        history = chat_histories[chat_id]
        if not history:
            await update.message.reply_text("Задайте вопрос после роли.\nПример: `/focus ceo Как масштабировать охват?`", parse_mode="Markdown")
            return
        question = "(проанализируй контекст нашего разговора со своей точки зрения)"

    emoji, name, persona = PERSONAS[role_key]
    system = FOCUS_SYSTEM_PROMPT_TEMPLATE.format(name=name, persona=persona)

    history = chat_histories[chat_id]
    messages = [{"role": "system", "content": system}]
    if history:
        messages += history[-10:]
    messages.append({"role": "user", "content": question})

    last_request_ts[chat_id] = time.monotonic()
    stop = asyncio.Event()
    asyncio.create_task(keep_typing(context, chat_id, stop))
    logger.info(f"Chat {chat_id} focus on {role_key}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, max_tokens=1500
        )
        stop.set()
        reply = f"{emoji} *{name}* — детальный анализ:\n\n" + response.choices[0].message.content
        await send_reply(update, reply)
    except Exception as e:
        stop.set()
        logger.error(f"Focus error: {e}")
        await update.message.reply_text("⚠️ Ошибка. Попробуйте ещё раз.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.effective_chat.id

    wait = check_rate_limit(chat_id)
    if wait > 0:
        await update.message.reply_text(f"⏳ Совет ещё думает. Подождите {wait:.0f} сек.")
        return

    logger.info(f"Chat {chat_id}: {user_text[:80]}")
    last_request_ts[chat_id] = time.monotonic()

    history = chat_histories[chat_id]
    history.append({"role": "user", "content": user_text})

    stop = asyncio.Event()
    asyncio.create_task(keep_typing(context, chat_id, stop))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, max_tokens=2500
        )
        stop.set()
        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        await send_reply(update, reply)
    except Exception as e:
        stop.set()
        history.pop()
        logger.error(f"OpenAI error: {e}")
        await update.message.reply_text("⚠️ Ошибка при обращении к совету. Попробуйте ещё раз.")


def main() -> None:
    logger.info("Starting Board of Directors bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(CommandHandler("focus", focus_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
