import asyncio
import logging
import os
import json
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
PORT = int(os.getenv("PORT", 10000))
JSONBLOB_URL = os.getenv("JSONBLOB_URL", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_topics = {}
topic_users = {}


class Form(StatesGroup):
    choosing_role = State()
    answering = State()


ROLES = {
    "manager": "📢 Менеджер ТГК",
    "video": "🎬 Видеомонтажёр",
    "sender": "📨 Рассыльщик",
    "support": "🛡 Админ общения/поддержки",
}

FORMS = {
    "manager": [
        {"q": "1. Ник:", "type": "text"},
        {"q": "2. Возраст:", "type": "number"},
        {"q": "3. Был ли опыт ведения ТГК? (Да/Нет)", "type": "yesno"},
        {"q": "4. Умеете оформлять посты? (Да/Нет)", "type": "yesno"},
        {"q": "5. Умеете работать с фото, видео и текстом? (Да/Нет)", "type": "yesno"},
        {"q": "6. Сколько времени готовы уделять каналу?", "type": "text"},
        {"q": "7. Сможете регулярно выкладывать посты? (Да/Нет)", "type": "yesno"},
        {"q": "8. Сможете соблюдать стиль и правила канала? (Да/Нет)", "type": "yesno"},
        {"q": "9. Что будете делать, если случайно выложили неправильный пост?", "type": "text"},
        {"q": "10. Готовы отвечать за свои публикации? (Да/Нет)", "type": "yesno"},
        {"q": "11. Будете ли использовать должность в личных целях? (Да/Нет)", "type": "yesno"},
        {"q": "12. Почему именно вас стоит взять?", "type": "text"},
        {"q": "13. Ваш юз (начинается с @):", "type": "username"},
        {"q": "14. Готовы соблюдать правила администрации? (Да/Нет)", "type": "yesno"},
        {"q": "15. Готовы пройти испытательный срок? (Да/Нет)", "type": "yesno"},
    ],
    "video": [
        {"q": "1. Ваше имя", "type": "text"},
        {"q": "2. Ваш возраст", "type": "number"},
        {"q": "3. Часовой пояс", "type": "text"},
        {"q": "4. Почему решили стать видеомонтажёром?", "type": "text"},
        {"q": "5. Сколько занимаетесь монтажом?", "type": "text"},
        {"q": "6. С какими программами работаете?", "type": "text"},
        {"q": "7. Что чаще монтируете?", "type": "text"},
        {"q": "8. Делаете цветокоррекцию и обработку звука? (да/нет)", "type": "yesno"},
        {"q": "9. Есть навыки анимации или моушн-графики? (да/нет)", "type": "yesno"},
        {"q": "10. Сколько времени понадобится на монтаж?", "type": "text"},
        {"q": "11. Скиньте 3 видео работ.", "type": "text"},
    ],
    "sender": [
        {"q": "1. Имя", "type": "text"},
        {"q": "2. Telegram юз (начинается с @)", "type": "username"},
        {"q": "3. Город и часовой пояс", "type": "text"},
        {"q": "4. Был ли опыт в данной теме?", "type": "text"},
        {"q": "5. Что делали чаще всего?", "type": "text"},
        {"q": "6. Знакомы с лимитами Telegram?", "type": "text"},
        {"q": "7. Почему пришли именно к нам?", "type": "text"},
        {"q": "8. В какое время удобно работать?", "type": "text"},
    ],
    "support": [
        {"q": "1. Имя", "type": "text"},
        {"q": "2. Возраст", "type": "number"},
        {"q": "3. Ваш юз (начинается с @)", "type": "username"},
        {"q": "4. Часовой пояс", "type": "text"},
        {"q": "5. Был ли опыт в общении/поддержке?", "type": "text"},
        {"q": "6. Как реагируете на конфликты?", "type": "text"},
        {"q": "7. Сколько времени готовы уделять?", "type": "text"},
        {"q": "8. Почему выбрали это направление?", "type": "text"},
    ],
}

WELCOME_TEXT = "Привет! 👋\n\nВыбери, кем ты хочешь стать:"


def role_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, name in ROLES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"role_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_card_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Inline[KeyboardButton(text="🔒 Заблокировать", callbackrole_data=f"block:{user_id}"),
                Inline_keyKeyboardButton(text="✅ Прочитать", callback_data]
=f"read:{user_id}"),
            ]
           ]
    )


async def save_data():
 current    if not JSONBLOB_URL:
        return
_q    data = {"user_topics": {str(k): v for k, v in user_topics.items()}}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(JSONBLOB_URL, json=data) as resp:
                _ = resp.status
    except Exception as e:
        logging.error(f"Ошибка сохранения: {e}")


async def load_data():
    global user_topics, topic_users
    if not JSONBLOB_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(JSONBLOB_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user_topics = {int(k): v for k, v in data.get("user_topics", {}).items()}
                    topic_users = {v: k for k, v in user_topics.items()}
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")


def validate_answer(answer_type: str, text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if answer_type == "number":
        return t.isdigit()
    if answer_type == "yesno":
        return t.lower() in ["да", "нет", "yes", "no"]
    if answer_type == "username":
        return t.startswith("@") and len(t) > 1 and " " not in t
    return True


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
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
    await callback.message.answer(FORMS[role_key][0]["q"])
    await state.set_state(Form.answering)
    await callback.answer()


@dp.message(Form.answering)
async def process_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    role_key = data.get("role")
    step = data.get("step", 0)
    answers = data.get("answers", [])
    questions = FORMS = questions[step]

    if message.text:
        if not validate_answer(current_q["type"], message.text):
            if current_q["type"] == "number":
                await message.answer("Пожалуйста, введи только число.")
            elif current_q["type"] == "yesno":
                await message.answer("Пожалуйста, ответь «Да» или «Нет».")
            elif current_q["type"] == "username":
                await message.answer("Юзер должен начинаться с @ и быть без пробелов.")
            else:
                await message.answer("Пожалуйста, ответь текстом.")
            return

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
        await message.answer("Пожалуйста, ответь текстом или медиа.")
        return

    step += 1
    if step < len(questions):
        await state.update_data(step=step, answers=answers)
        await message.answer(questions[step]["q"])
    else:
        await state.update_data(answers=answers)
        await finish_form(message, state)


async def finish_form(message: Message, state: FSMContext):
    data = await state.get_data()
    role_key = data.get("role")
    answers = data.get("answers", [])
    user_id = message.from_user.id
    username = message.from_user.username or f"id{user_id}"

    try:
        topic = await bot.create_forum_topic(chat_id=GROUP_ID, name=f"{username}")
        topic_id = topic.message_thread_id
        user_topics[user_id] = topic_id
        topic_users[topic_id] = user_id
        await save_data()

        card = (
            f"🆕 Новая заявка\n"
            f"👤 {message.from_user.full_name}\n"
            f"🔖 @{message.from_user.username or 'нет'}\n"
            f"📌 {ROLES[role_key]}\n\n"
        )
        for i, ans in enumerate(answers):
            q = FORMS[role_key][i]["q"]
            card += f"{q}\n➡️ {ans['content']}\n\n"

        await bot.send_message(
            GROUP_ID,
            card,
            message_thread_id=topic_id,
            reply_markup=get_card_keyboard(user_id),
        )

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

        await message.answer("Спасибо! Анкета отправлена. Админ скоро свяжется с тобой.")
    except Exception as e:
        logging.error(f"Не удалось создать тему: {e}")
        await message.answer("Произошла ошибка при отправке анкеты. Попробуй позже.")
    finally:
        await state.clear()


@dp.message(F.chat.type == "private")
async def handle_user_message(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if user_id not in user_topics:
        await message.answer("Начни с /start и выбери роль.")
        return

    topic_id = user_topics[user_id]

    try:
        if message.text:
            await bot.send_message(GROUP_ID, message.text, message_thread_id=topic_id)
        elif message.photo:
            await bot.send_photo(
                GROUP_ID,
                message.photo[-1].file_id,
                caption=message.caption,
                message_thread_id=topic_id,
            )
        elif message.video:
            await bot.send_video(
                GROUP_ID,
                message.video.file_id,
                caption=message.caption,
                message_thread_id=topic_id,
            )
        elif message.voice:
            await bot.send_voice(GROUP_ID, message.voice.file_id, message_thread_id=topic_id)
        elif message.video_note:
            await bot.send_video_note(GROUP_ID, message.video_note.file_id, message_thread_id=topic_id)
        elif message.document:
            await bot.send_document(GROUP_ID, message.document.file_id, message_thread_id=topic_id)
        elif message.sticker:
            await bot.send_sticker(GROUP_ID, message.sticker.file_id, message_thread_id=topic_id)
    except Exception as e:
        logging.error(f"Ошибка пересылки от пользователя: {e}")


@dp.message(F.chat.id == GROUP_ID)
async def handle_admin_message(message: Message):
    if message.from_user is None or message.from_user.is_bot:
        return
    if message.text and message.text.startswith("/"):
        return
    if message.message_thread_id is None:
        return

    topic_id = message.message_thread_id
    user_id = topic_users.get(topic_id)
    if not user_id:
        return

    if message.text and message.text.startswith("//"):
        return

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
        logging.error(f"Ошибка отправки пользователю {user_id}: {e}")


@dp.callback_query(F.data.startswith("block:"))
async def process_block(callback: CallbackQuery):
    await callback.answer("Пользователь заблокирован (демо).")


@dp.callback_query(F.data.startswith("read:"))
async def process_read(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    try:
        await bot.send_message(user_id, "Твоя анкета рассмотрена, скоро с тобой свяжутся.")
    except Exception:
        pass
    await callback.answer("Отмечено как прочитано")


async def main():
    logging.basicConfig(level=logging.INFO)
    await load_data()
    await bot.delete_webhook(drop_pending_updates=True)

    polling_task = asyncio.create_task(dp.start_polling(bot))

    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

    await polling_task


if __name__ == "__main__":
    asyncio.run(main())
