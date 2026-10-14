import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.session.aiohttp import AiohttpSession

from database import (
    init_db, add_reminder, get_user_reminders,
    delete_reminder, get_due_reminders, delete_by_id
)

BOT_TOKEN = "добавьсвойтокен"


session = AiohttpSession(proxy="socks5://127.0.0.1:10808")
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()



class AddReminder(StatesGroup):
    waiting_text = State()
    waiting_time = State()



@dp.message(Command("start"))
async def cmd_start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add")],
        [InlineKeyboardButton(text="📋 Список", callback_data="list")],
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Я бот-напоминалка. Могу напомнить тебе о чём угодно.\n\n"
        "Команды:\n"
        "/add — добавить напоминание\n"
        "/list — список напоминаний\n"
        "/delete — удалить напоминание",
        reply_markup=keyboard
    )



@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await state.set_state(AddReminder.waiting_text)
    await message.answer("Что напомнить? Напиши текст.")


@dp.message(AddReminder.waiting_text)
async def process_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(AddReminder.waiting_time)
    await message.answer(
        "Когда напомнить? Напиши время в формате:\n\n"
        "`15:30` — сегодня в 15:30\n"
        "`2026-10-20 09:00` — конкретная дата\n"
        "`+30m` — через 30 минут\n"
        "`+2h` — через 2 часа",
        parse_mode="Markdown"
    )


@dp.message(AddReminder.waiting_time)
async def process_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    remind_at = None

    try:
        if time_str.startswith("+"):
            if time_str.endswith("m"):
                minutes = int(time_str[1:-1])
                remind_at = datetime.now() + timedelta(minutes=minutes)
            elif time_str.endswith("h"):
                hours = int(time_str[1:-1])
                remind_at = datetime.now() + timedelta(hours=hours)
        elif " " in time_str:
            remind_at = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        elif ":" in time_str:
            h, m = map(int, time_str.split(":"))
            now = datetime.now()
            remind_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if remind_at < now:
                remind_at += timedelta(days=1)
    except (ValueError, IndexError):
        pass

    if not remind_at:
        await message.answer(
            "Не понял время. Попробуй ещё раз:\n"
            "`15:30` или `+30m` или `2026-10-20 09:00`",
            parse_mode="Markdown"
        )
        return

    data = await state.get_data()
    text = data["text"]
    reminder_id = await add_reminder(message.from_user.id, text, remind_at)

    await state.clear()
    await message.answer(
        f"✅ Напоминание #{reminder_id} добавлено.\n\n"
        f"📝 {text}\n"
        f"⏰ {remind_at.strftime('%d.%m.%Y в %H:%M')}"
    )



@dp.message(Command("list"))
async def cmd_list(message: Message):
    reminders = await get_user_reminders(message.from_user.id)
    if not reminders:
        await message.answer("У тебя пока нет напоминаний.")
        return

    text = "📋 Твои напоминания:\n\n"
    for r in reminders:
        text += f"#{r['id']} — {r['text']}\n"
        text += f"     ⏰ {r['remind_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
    text += "Удалить: /delete <id>"

    await message.answer(text)



@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Используй: /delete <id>\nНапример: /delete 3")
        return

    reminder_id = int(parts[1])
    if await delete_reminder(reminder_id, message.from_user.id):
        await message.answer(f"🗑 Напоминание #{reminder_id} удалено.")
    else:
        await message.answer("Не нашёл такое напоминание.")



@dp.callback_query(F.data == "add")
async def cb_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Что напомнить? Напиши текст.")
    await state.set_state(AddReminder.waiting_text)
    await callback.answer()


@dp.callback_query(F.data == "list")
async def cb_list(callback: CallbackQuery):
    await cmd_list(callback.message)
    await callback.answer()



async def reminder_checker():
    while True:
        try:
            due = await get_due_reminders()
            for r in due:
                try:
                    await bot.send_message(
                        r["user_id"],
                        f"🔔 Напоминание!\n\n{r['text']}"
                    )
                    await delete_by_id(r["id"])
                except Exception as e:
                    print(f"Ошибка отправки: {e}")
        except Exception as e:
            print(f"Ошибка в reminder_checker: {e}")
        await asyncio.sleep(30)



async def main():
    await init_db()
    asyncio.create_task(reminder_checker())
    print("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())