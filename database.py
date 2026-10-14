import aiosqlite
from datetime import datetime

DB_PATH = "reminders.db"


async def init_db():
    """Создаёт таблицу напоминаний при первом запуске."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def add_reminder(user_id: int, text: str, remind_at: datetime) -> int:
    """Добавляет напоминание, возвращает его id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO reminders (user_id, text, remind_at, created_at) VALUES (?, ?, ?, ?)",
            (user_id, text, remind_at.isoformat(), datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_reminders(user_id: int):
    """Возвращает все напоминания пользователя, отсортированные по времени."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, text, remind_at FROM reminders WHERE user_id = ? ORDER BY remind_at",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "text": r[1], "remind_at": datetime.fromisoformat(r[2])}
            for r in rows
        ]


async def delete_reminder(reminder_id: int, user_id: int) -> bool:
    """Удаляет напоминание. True если удалено, False если не найдено."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_due_reminders():
    """Возвращает все напоминания, время которых пришло."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, text FROM reminders WHERE remind_at <= ?",
            (now,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "user_id": r[1], "text": r[2]} for r in rows]


async def delete_by_id(reminder_id: int):
    """Удаляет напоминание по id (используется после отправки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()