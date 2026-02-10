from __future__ import annotations
import asyncio
import datetime
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from pathlib import Path
from .storage import temp_workspace
from .processor import collect_input_files, process_layout
from .config import Settings

router = Router()

CHOICES = {
    "Термо 75×120": "THERMAL_75x120",
    "Термо 100×150": "THERMAL_100x150",
    "A4 — 1 на лист": "A4_SINGLE",
    "A4 — 4 на лист": "A4_2x2",
    "A4 — 8 на лист": "A4_2x4",
    "A4 — 9 на лист": "A4_3x3",
    "Просто склеить PDF": "MERGE",
}

# Простая in-memory "сессия чата" для хранения выбранного режима.
# Для продакшена лучше FSM/Redis.
_chat_state: dict[int, str] = {}

def _choice_keyboard() -> types.ReplyKeyboardMarkup:
    rows = [
        [types.KeyboardButton(text="Термо 75×120"), types.KeyboardButton(text="Термо 100×150")],
        [types.KeyboardButton(text="A4 — 1 на лист"), types.KeyboardButton(text="A4 — 4 на лист")],
        [types.KeyboardButton(text="A4 — 8 на лист"), types.KeyboardButton(text="A4 — 9 на лист")],
        [types.KeyboardButton(text="Просто склеить PDF")],
    ]
    return types.ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
    )

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Пришлите ZIP или PDF с накладными Kaspi. Затем выберите формат печати.",
        reply_markup=_choice_keyboard()
    )

@router.message(F.text.in_(list(CHOICES.keys())))
async def on_choice(message: types.Message):
    _chat_state[message.chat.id] = CHOICES[message.text]
    await message.answer(f"Ок, формат: {message.text}. Теперь пришлите ZIP или PDF.")

async def _download_doc(bot, doc: types.Document, dest: Path):
    file = await bot.get_file(doc.file_id)
    await bot.download_file(file.file_path, destination=dest)

@router.message(F.document)
async def on_files(message: types.Message):
    mode = _chat_state.get(message.chat.id, "MERGE")
    settings = Settings.from_env()
    await message.chat.do("upload_document")

    with temp_workspace() as workdir:
        # Скачать все вложенные документы
        in_paths: list[Path] = []
        if message.document:
            dest = workdir / (message.document.file_name or "file.pdf")
            await _download_doc(message.bot, message.document, dest)
            in_paths.append(dest)

        # Распаковать ZIP и собрать PDF
        inputs = collect_input_files(in_paths, workdir)
        if not inputs:
            await message.answer("Внутри не найдено PDF.")
            return

        # Генерим имя исходя из текущей даты/времени
        now = datetime.datetime.now().strftime("%d%m%y%H%M")
        out_filename = f"result_{now}.pdf"
        out_pdf = workdir / out_filename

        # Обработка компоновки
        try:
            process_layout(mode, inputs, out_pdf)
        except Exception as e:
            await message.answer(f"Ошибка при обработке: {e}")
            return

        # Отправляем файл с именем result_ддммггЧЧММ.pdf
        await message.answer_document(
            FSInputFile(out_pdf), 
            caption=f"Готово! Файл: {out_filename}"
        )

@router.message()
async def fallback(message: types.Message):
    await message.answer(
        "Пришлите ZIP или PDF с накладными, или выберите режим печати на клавиатуре ниже.",
        reply_markup=_choice_keyboard()
    )
