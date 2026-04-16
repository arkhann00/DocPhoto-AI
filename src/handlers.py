import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.ai_processor import AIProcessor, AIProcessingError

logger = logging.getLogger(__name__)
router = Router()


def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Создать фото", callback_data="action:create")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="action:help")],
        [InlineKeyboardButton(text="📋 Требования к фото", callback_data="help:requirements")],
        [InlineKeyboardButton(text="💡 Советы", callback_data="help:tips")],
    ])


WELCOME_TEXT = (
    "👋 Привет! Я бот для создания фото на документы.\n\n"
    "🤖 AI сгенерирует документное фото из любого снимка.\n\n"
    "Выбери действие 👇"
)

INSTRUCTION_TEXT = (
    "📖 <b>Как пользоваться</b>\n\n"
    "1. Нажми <b>«Создать фото»</b>\n"
    "2. Отправь любое фото с лицом\n"
    "3. Подожди ~30 сек — AI обработает фото\n"
    "4. Получи готовое фото на документы\n\n"
    "Фото будет соответствовать формату <b>35x45 мм</b> "
    "(внутренний паспорт РФ)."
)

REQUIREMENTS_TEXT = (
    "📋 <b>Требования к исходному фото</b>\n\n"
    "✅ Лицо хорошо видно, не закрыто\n"
    "✅ Достаточное освещение\n"
    "✅ Один человек в кадре\n"
    "✅ Фото не размытое\n\n"
    "❌ Не подойдут:\n"
    "• Фото в солнцезащитных очках\n"
    "• Групповые фото\n"
    "• Сильно обрезанные фото\n"
    "• Фото со спины или в профиль"
)

TIPS_TEXT = (
    "💡 <b>Советы для лучшего результата</b>\n\n"
    "• Используй фото с ровным освещением лица\n"
    "• Лучше всего — фото анфас (прямо в камеру)\n"
    "• Чем выше качество исходного фото, тем лучше результат\n"
    "• Если результат не устроил — попробуй другое фото\n"
    "• Бот не меняет черты лица, только фон и кадрирование"
)


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В меню", callback_data="action:back")],
    ])


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(INSTRUCTION_TEXT, reply_markup=back_kb(), parse_mode="HTML")


@router.callback_query(F.data == "action:create")
async def action_create(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📸 Отправь фото — AI сделает документное фото.",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "action:help")
async def action_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        INSTRUCTION_TEXT, reply_markup=back_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "help:requirements")
async def help_requirements(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        REQUIREMENTS_TEXT, reply_markup=back_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "help:tips")
async def help_tips(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        TIPS_TEXT, reply_markup=back_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "action:back")
async def action_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_kb())
    await callback.answer()


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot, ai: AIProcessor) -> None:
    status = await message.answer("⏳ Генерирую фото…")

    file = await bot.get_file(message.photo[-1].file_id)
    photo_bytes = (await bot.download_file(file.file_path)).read()

    try:
        result_bytes = await ai.generate_document_photo(photo_bytes)
    except AIProcessingError as e:
        await status.edit_text(f"❌ {e}", reply_markup=back_kb())
        return
    except Exception:
        logger.exception("AI processing failed")
        await status.edit_text(
            "❌ Ошибка генерации. Попробуй ещё раз.",
            reply_markup=back_kb(),
        )
        return

    await message.answer_photo(
        BufferedInputFile(result_bytes, filename="document_photo.jpg"),
        caption="✅ Готово!",
    )

    await status.delete()
    await message.answer("Хочешь ещё?", reply_markup=main_kb())
