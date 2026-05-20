import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.ai_processor import AIProcessor, AIProcessingError
from src.config import PaymentsConfig
from src.constants import TARIFF_PACKAGES, get_tariff
from src.db import Database

logger = logging.getLogger(__name__)
router = Router()


# ── keyboards ────────────────────────────────────────────────

def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Создать фото", callback_data="action:create")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="action:help")],
        [InlineKeyboardButton(text="📋 Требования к фото", callback_data="help:requirements")],
        [InlineKeyboardButton(text="💡 Советы", callback_data="help:tips")],
        [InlineKeyboardButton(text="💵 Баланс", callback_data="balance")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В меню", callback_data="action:back")],
    ])


def balance_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p.button_label, callback_data=f"buy:{p.id}")]
        for p in TARIFF_PACKAGES
    ]
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="action:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── texts ────────────────────────────────────────────────────

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


PAYLOAD_PREFIX = "balance_topup"


def _build_payment_payload(package_id: str, telegram_id: int) -> str:
    return f"{PAYLOAD_PREFIX}:{package_id}:{telegram_id}"


def _parse_payment_payload(payload: str) -> tuple[str, int] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != PAYLOAD_PREFIX:
        return None

    package_id = parts[1]
    try:
        telegram_id = int(parts[2])
    except ValueError:
        return None

    return package_id, telegram_id


# ── helpers ──────────────────────────────────────────────────

async def _safe_edit_text(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        raise


def _username(message_or_cb) -> str:
    user = getattr(message_or_cb, "from_user", None)
    if user is None:
        return ""
    return user.username or user.first_name or ""


# ── /start & /help ───────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db: Database) -> None:
    await db.get_or_create_user(message.from_user.id, _username(message))
    await message.answer(WELCOME_TEXT, reply_markup=main_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(INSTRUCTION_TEXT, reply_markup=back_kb(), parse_mode="HTML")


# ── menu callbacks ───────────────────────────────────────────

@router.callback_query(F.data == "action:create")
async def action_create(callback: CallbackQuery) -> None:
    await callback.answer()
    await _safe_edit_text(
        callback,
        "⚠️ Перед первой генерацией внимательно следуй инструкции — "
        "это важно для качества генерации.\n\n"
        "📸 Отправь фото — AI сделает документное фото.",
        reply_markup=back_kb(),
    )


@router.callback_query(F.data == "action:help")
async def action_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await _safe_edit_text(
        callback,
        INSTRUCTION_TEXT,
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "help:requirements")
async def help_requirements(callback: CallbackQuery) -> None:
    await callback.answer()
    await _safe_edit_text(
        callback,
        REQUIREMENTS_TEXT,
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "help:tips")
async def help_tips(callback: CallbackQuery) -> None:
    await callback.answer()
    await _safe_edit_text(
        callback,
        TIPS_TEXT,
        reply_markup=back_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "action:back")
async def action_back(callback: CallbackQuery) -> None:
    await callback.answer()
    await _safe_edit_text(callback, WELCOME_TEXT, reply_markup=main_kb())


# ── balance ──────────────────────────────────────────────────

@router.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    user = await db.get_or_create_user(callback.from_user.id, _username(callback))
    balance = user["balance"]
    text = (
        f"💵 <b>Баланс</b>\n\n"
        f"Доступно генераций: <b>{balance}</b>\n\n"
        f"<i>1 генерация = 1 готовое фото на документы</i>\n\n"
        f"Выбери пакет для пополнения 👇"
    )
    await _safe_edit_text(callback, text, reply_markup=balance_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("buy:"))
async def buy_package(
    callback: CallbackQuery,
    db: Database,
    payments: PaymentsConfig,
) -> None:
    package_id = callback.data.split(":", 1)[1]
    tariff = get_tariff(package_id)
    if tariff is None:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    if not payments.is_configured:
        await callback.answer(
            "Платежи временно недоступны. Попробуй позже.",
            show_alert=True,
        )
        return

    await db.get_or_create_user(callback.from_user.id, _username(callback))
    payload = _build_payment_payload(tariff.id, callback.from_user.id)

    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Пополнение баланса",
            description=(
                f"Пакет на {tariff.generations} генераций.\n"
                "После оплаты генерации будут начислены автоматически."
            ),
            provider_token=payments.provider_token,
            currency=payments.currency,
            prices=[
                LabeledPrice(
                    label=f"{tariff.generations} генераций",
                    amount=tariff.price_rub * 100,
                )
            ],
            payload=payload,
            start_parameter="balance_topup",
            max_tip_amount=0,
        )
    except TelegramBadRequest:
        logger.exception("Failed to send payment invoice")
        await callback.answer(
            "Не удалось открыть оплату. Напиши боту в личку и нажми /start.",
            show_alert=True,
        )
        return

    await callback.answer("Счёт на оплату отправлен")

    text = (
        "💳 <b>Счёт сформирован</b>\n\n"
        f"Пакет: <b>{tariff.generations} генераций</b> за <b>{tariff.price_rub} ₽</b>\n\n"
        "После успешной оплаты генерации начислятся автоматически."
    )
    await _safe_edit_text(callback, text, reply_markup=back_kb(), parse_mode="HTML")


@router.pre_checkout_query()
async def process_pre_checkout(
    pre_checkout_query: PreCheckoutQuery,
    bot: Bot,
    payments: PaymentsConfig,
) -> None:
    parsed_payload = _parse_payment_payload(pre_checkout_query.invoice_payload)
    if parsed_payload is None:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Платёж не прошёл. Открой баланс и попробуй снова.",
        )
        return

    package_id, payload_telegram_id = parsed_payload
    tariff = get_tariff(package_id)
    if tariff is None or payload_telegram_id != pre_checkout_query.from_user.id:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Платёж не прошёл. Попробуй заново.",
        )
        return

    if pre_checkout_query.currency != payments.currency:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Неверная валюта платежа.",
        )
        return

    expected_amount_minor = tariff.price_rub * 100
    if pre_checkout_query.total_amount != expected_amount_minor:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Неверная сумма платежа.",
        )
        return

    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(
    message: Message,
    db: Database,
    payments: PaymentsConfig,
) -> None:
    payment: SuccessfulPayment = message.successful_payment
    if payment is None:
        return

    parsed_payload = _parse_payment_payload(payment.invoice_payload)
    if parsed_payload is None:
        logger.warning("Successful payment with invalid payload: %s", payment.invoice_payload)
        return

    package_id, payload_telegram_id = parsed_payload
    tariff = get_tariff(package_id)
    if tariff is None:
        logger.warning("Successful payment with unknown package: %s", package_id)
        return
    if payload_telegram_id != message.from_user.id:
        logger.warning(
            "Successful payment user mismatch. payload=%s, actual=%s",
            payload_telegram_id,
            message.from_user.id,
        )
        return

    expected_amount_minor = tariff.price_rub * 100
    if payment.currency != payments.currency or payment.total_amount != expected_amount_minor:
        logger.warning(
            "Successful payment validation failed: currency=%s amount=%s expected=%s",
            payment.currency,
            payment.total_amount,
            expected_amount_minor,
        )
        return

    is_new_payment, balance = await db.apply_successful_payment(
        telegram_id=message.from_user.id,
        username=_username(message),
        package_id=tariff.id,
        amount_minor=payment.total_amount,
        currency=payment.currency,
        generations=tariff.generations,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        provider_payment_charge_id=payment.provider_payment_charge_id or "",
    )

    if is_new_payment:
        text = (
            "✅ <b>Оплата прошла успешно</b>\n\n"
            f"Начислено: <b>{tariff.generations}</b> генераций\n"
            f"Текущий баланс: <b>{balance}</b> генераций"
        )
    else:
        text = (
            "ℹ️ Этот платёж уже был учтён ранее.\n\n"
            f"Текущий баланс: <b>{balance}</b> генераций"
        )

    await message.answer(text, reply_markup=main_kb(), parse_mode="HTML")


# ── photo generation ─────────────────────────────────────────

@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot, ai: AIProcessor, db: Database) -> None:
    user = await db.get_or_create_user(message.from_user.id, _username(message))

    if user["balance"] <= 0:
        await message.answer(
            "❌ У тебя закончились генерации.\n\n"
            "Пополни баланс, чтобы продолжить 👇",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💵 Баланс", callback_data="balance")],
            ]),
        )
        return

    if not await db.consume_generation(message.from_user.id):
        await message.answer("❌ Не удалось списать генерацию. Попробуй ещё раз.")
        return

    status = await message.answer("⏳ Генерирую фото…")

    file = await bot.get_file(message.photo[-1].file_id)
    photo_bytes = (await bot.download_file(file.file_path)).read()

    try:
        result_bytes = await ai.generate_document_photo(photo_bytes)
    except AIProcessingError as e:
        await db.add_balance(message.from_user.id, 1)
        await status.edit_text(f"❌ {e}", reply_markup=back_kb())
        return
    except Exception:
        logger.exception("AI processing failed")
        await db.add_balance(message.from_user.id, 1)
        await status.edit_text(
            "❌ Ошибка генерации. Попробуй ещё раз.",
            reply_markup=back_kb(),
        )
        return

    if result_bytes.startswith(b"\x89PNG"):
        out_name = "document_photo.png"
    elif result_bytes.startswith(b"\xff\xd8\xff"):
        out_name = "document_photo.jpg"
    else:
        out_name = "document_photo.jpg"

    await message.answer_photo(
        BufferedInputFile(result_bytes, filename=out_name),
        caption="✅ Готово!",
    )
    await message.answer_document(
        BufferedInputFile(result_bytes, filename=out_name),
    )

    await status.delete()

    remaining = await db.get_balance(message.from_user.id)
    await message.answer(
        f"Осталось генераций: <b>{remaining}</b>\n\nХочешь ещё?",
        reply_markup=main_kb(),
        parse_mode="HTML",
    )
