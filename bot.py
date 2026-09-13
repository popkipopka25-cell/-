import asyncio
import logging
import os
import json
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
PORT = int(os.getenv("PORT", 10000))
OWNER_IDS = set(map(int, (os.getenv("OWNER_IDS", "") or "").split(",") if os.getenv("OWNER_IDS") else []))
JSONBLOB_URL = os.getenv("JSONBLOB_URL", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_topics = {}   # user_id -> topic_id
topic_users = {}   # topic_id -> user_id
all_users = set()

class Form(StatesGroup):
    choosing_role = State()
    answering = State()

# Список ролей
ROLES = {
    "manager": "📢 Менеджер ТГК",
    "video": "🎬 Видеомонтажёр",
    "sender": "📨 Рассыльщик",
    "support": "🛡 Админ общения/поддержки",
}

# Анкеты по ролям (список вопросов)
FORMS = {
    "manager": [
        "1. Ник:",
        "2. Возраст:",
        "3. Был ли опыт ведения ТГК? (Да/Нет)",
        "4. Умеете оформлять посты? (Да/Нет)",
        "5. Умеете работать с фото, видео и текстом? (Да/Нет)",
        "6. Сколько времени готовы уделять каналу?",
        "7. Сможете регулярно выкладывать посты? (Да/Нет)",
        "8. Сможете соблюдать стиль и правила канала? (Да/Нет)",
        "9. Что будете делать, если случайно выложили неправильный пост?",
        "10. Готовы отвечать за свои публикации и исправлять ошибки? (Да/Нет)",
        "11. Будете ли использовать должность в личных целях? (Да/Нет)",
        "12. Почему именно вас стоит взять?",
        "13. Ваш юз:",
        "14. Готовы соблюдать правила администрации и выполнять обязанности менеджера? (Да/Нет)",
        "15. Готовы пройти испытательный срок? (Да/Нет)",
    ],
    "video": [
        "1. Ваше имя",
        "2. Ваш возраст",
        "3. Часовой пояс",
        "4. Почему решили стать видеомонтажёром?",
        "5. Сколько недель/месяцев/лет занимаетесь монтажом видео?",
        "6. С какими программами для видеомонтажа вы работаете?",
        "7. Что чаще монтируете? (ролики/рекламу/клипы и т.д.)",
        "8. Делаете ли цветокоррекцию и обработку звука? (да/нет, если да — насколько уверенно)",
        "9. Есть ли навыки анимации или моушн-графики? (да/нет)",
        "10. Сколько времени понадобится вам для видеомонтажа?",
        "11. Скиньте 3 видео своих работ (можно ссылками или файлами).",
    ],
    "sender": [
        "1. Имя",
        "2. Telegram юз",
        "3. Город и часовой пояс",
        "4. Был ли опыт в данной теме?",
        "5. Что делали чаще всего: рассылки, прогревы, вовлечение, работа с негативом? (1–2 пункта)",
        "6. Знакомы с лимитами и спам-фильтрами Telegram? Что самое важное, чтобы не улететь в бан?",
        "7. Почему вы решили прийти именно к нам?",
        "8. В какое время вам будет удобно работать?",
    ],
    "support": [
        "1. Имя",
        "2. Возраст",
        "3. Ваш юз",
        "4. Часовой пояс",
        "5. Был ли опыт в общении/поддержке?",
        "6. Как вы реагируете на конфликтные ситуации?",
        "7. Сколько времени готовы уделять работе?",
        "8. Почему выбрали именно это направление?",
    ],
}

WELCOME_TEXT = (
    "Привет! 👋\n\n"
    "Я бот для подачи заявки в команду.\n"
    "Выбери, кем ты хочешь стать:"
)

def role_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"role_{key}")] for key, name in ROLES.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_card_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f"block:{user_id}"),
        InlineKeyboardButton(text="✅ Прочитать", callback_data=f"read:{user_id}")
    ]])

async def save_data():
    if not JSONBLOB_URL:
        return
    data = {
        "user_topics": {str(k): v for k, v in user_topics.items()},
        "all_users": list(all_users),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(JSONBLOB_URL, json=data) as resp:
                if resp.status not in (200, 204):
                    logging.error(f"Ошибка сохранения: {resp.status}")
    except Exception as e:
        logging.error(f"Ошибка сохранения: {e}")

async def load_data():
    global user_topics, topic_users, all_users
    if not JSONBLOB_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(JSONBLOB_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user_topics = {int(k): v for k, v in data.get("user_topics", {}).items()}
                    topic_users = {v: k for k, v in user_topics.items()}
                    all_users = set(map(int, data.get("all_users", [])))
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    all_users.add(message.from_user.id)
    await save_data()
    await message.answer(WELCOME_TEXT, reply_markup=role_keyboard())
    await state.set_state(Form.choosing_role)

@dp.callback_query(F.data.startswith("role_"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    role_key = callback.data.split("_", 1)[1]
    if role_key not in FORMS:
        await callback.answer("Неизвестная роль.")
        return
    await state.update_data(role=role_key, step=0, answers=[])
    await callback.message.edit_text(f"Ты выбрал: {ROLES[role_key]}\n\nНачинаем анкету.")
    await callback.message.answer(FORMS[role_key][0])
    await state.set_state(Form.answering)
    await callback.answer()

@dp.message(Form.answering)
async def process_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    role_key = data.get("role")
    step = data.get("step", 0)
    answers = data.get("answers", [])
    questions = FORMS[role_key]

    # Сохраняем ответ — текст, фото, видео, голос, кружок, документ, стикер
    if message.text:
        answers.append({"type": "text", "content": message.text})
    elif message.photo:
        answers.append({"type": "photo", "content": message.photo[-1].file_id})
    elif message.video:
        answers.append({"type": "video", "content": message.video.file_id})
    elif message.voice:
        answers.append({"type": "voice", "content": message.voice.file_id})
    elif message.video_note:
        answers.append({"type": "video_note", "content": message.video_note.file_id})
    elif message.document:
        answers.append({"type": "document", "content": message.document.file_id})
    elif message.sticker:
        answers.append({"type": "sticker", "content": message.sticker.file_id})
    else:
        answers.append({"type": "text", "content": "—"})

    step += 1
    if step < len(questions):
        await state.update_data(step=step, answers=answers)
        await message.answer(questions[step])
    else:
        # анкета завершена
        await state.update_data(answers=answers)
        await finish_form(message, state)

async def finish_form(message: Message, state: FSMContext):
    data = await state.get_data()
    role_key = data.get("role")
    answers = data.get("answers", [])
    user_id = message.from_user.id
    username = message.from_user.username or f"id{user_id}"

    # создаём тему
    try:
        topic = await bot.create_forum_topic(chat_id=GROUP_ID, name=f"{username}")
        topic_id = topic.message_thread_id
        user_topics[user_id] = topic_id
        topic_users[topic_id] = user_id
        await save_data()

        # отправляем карточку
        card = f"🆕 Новая заявка\n👤 Имя: {message.from_user.full_name}\n🔖 Username: @{message.from_user.username or 'нет'}\n📌 Роль: {ROLES[role_key]}\n\n"
        for i, ans in enumerate(answers, 1):
            q = FORMS[role_key][i - 1]
            card += f"{q}\n➡️ {ans['content']}\n\n"

        await bot.send_message(GROUP_ID, card, message_thread_id=topic_id, reply_markup=get_card_keyboard(user_id))

        # отправляем медиа отдельными сообщениями
        for ans in answers:
            if ans["type"] == "photo":
                await bot.send_photo(GROUP_ID, ans["content"], message_thread_id=topic_id)
            elif ans["type"] == "video":
                await bot.send_video(GROUP_ID, ans["content"], message_thread_id=topic_id)
            elif ans["type"] == "voice":
                await bot.send_voice(GROUP_ID, ans["content"], message_thread_id=topic_id)
            elif ans["type"] == "video_note":
                await bot.send_video_note(GROUP_ID, ans["content"], message_thread_id=topic_id)
            elif ans["type"] == "document":
                await bot.send_document(GROUP_ID, ans["content"], message_thread_id=topic_id)
            elif ans["type"] == "sticker":
                await bot.send_sticker(GROUP_ID, ans["content"], message_thread_id=topic_id)

        await message.answer("Спасибо! Твоя анкета отправлена. Администратор скоро свяжется с тобой в этом чате.")
    except Exception as e:
        logging.error(f"Не удалось создать тему: {e}")
        await message.answer("Произошла ошибка при отправке анкеты. Попробуй позже.")
    finally:
        await state.clear()

# ---------- Пересылка сообщений ----------
@dp.message(F.chat.type == "private")
async def handle_user_message(message: Message, state: FSMContext):
    # Если пользователь в процессе анкеты — не пересылаем
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if user_id not in user_topics:
        await message.answer("Пожалуйста, начни с /start и выбери роль.")
        return
    topic_id = user_topics[user_id]

    try:
        if message.text:
            await bot.send_message(GROUP_ID, message.text, message_thread_id=topic_id)
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=message.caption, message_thread_id=topic_id)
        elif message.video:
            await bot.send_video(GROUP_ID, message.video.file_id, caption=message.caption, message_thread_id=topic_id)
        elif message.voice:
            await bot.send_voice(GROUP_ID, message.voice.file_id, message_thread_id=topic_id)
        elif message.video_note:
            await bot.send_video_note(GROUP_ID, message.video_note.file_id, message_thread_id=topic_id)
        elif message.document:
            await bot.send_document(GROUP_ID, message.document.file_id, message_thread_id=topic_id)
        elif message.sticker:
            await bot.send_sticker(GROUP_ID, message.sticker.file_id, message_thread_id=topic_id)
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")

@dp.message(F.chat.id == GROUP_ID)
async def handle_admin_message(message: Message):
    if message.from_user is None or message.from_user.is_bot:
        return
    if message.text and message.text.startswith('/'):
        return
    if not message.message_thread_id:
        return

    topic_id = message.message_thread_id
    user_id = topic_users.get(topic_id)
    if not user_id:
        return

    if message.text and message.text.startswith("//"):
        return  # внутренняя заметка

    try:
        if message.text:
            await bot.send_message(user_id, message.text)
        elif message.photo:
            await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
        elif message.video:
            await bot.send_video(user_id, message.video.file_id, caption=message.caption)
        elif message.voice:
            await bot.send_voice(user_id, message.voice.file_id)
        elif message.video_note:
            await bot.send_video_note(user_id, message.video_note.file_id)
        elif message.document:
            await bot.send_document(user_id, message.document.file_id)
        elif message.sticker:
            await bot.send_sticker(user_id, message.sticker.file_id)
    except Exception as e:
        logging.error(f"Ошибка отправки пользователю: {e}")

# ---------- Кнопки блокировки/прочтения ----------
@dp.callback_query(F.data.startswith("block:"))
async def process_block(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    await callback.answer("Пользователь заблокирован (демо).")

@dp.callback_query(F.data.startswith("read:"))
async def process_read(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    try:
        await bot.send_message(user_id, "Твоя анкета рассмотрена, скоро с тобой свяжутся.")
    except:
        pass
    await callback.answer("Отмечено как прочитано")

# ---------- Запуск ----------
async def main():
    logging.basicConfig(level=logging.INFO)
    await load_data()
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))

    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text="Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

    await polling_task

if __name__ == "__main__":
    asyncio.run(main())