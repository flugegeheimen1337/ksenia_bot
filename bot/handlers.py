"""Команды и кнопки. В группах бот молчит: квест только в личном чате по ссылке."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.content import BEATS, BY_ID, ROUTE_TEXT
from bot.db import Store
from bot.keyboards import done_kb, route_kb
from bot.present import Presenter

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

_locks: dict[int, asyncio.Lock] = {}


def _lock(user_id: int) -> asyncio.Lock:
    return _locks.setdefault(user_id, asyncio.Lock())


def setup(bot: Bot, store: Store) -> Router:
    router.bot = bot  # type: ignore[attr-defined]
    router.store = store  # type: ignore[attr-defined]
    router.presenter = Presenter(bot, store)  # type: ignore[attr-defined]
    return router


def _presenter() -> Presenter:
    return router.presenter  # type: ignore[attr-defined]


def _store() -> Store:
    return router.store  # type: ignore[attr-defined]


async def _quiet(callback: CallbackQuery, text: str | None = None) -> None:
    try:
        await callback.answer(text)
    except TelegramBadRequest:
        pass


async def _clear(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


def _chat(callback: CallbackQuery) -> int:
    if callback.message is not None:
        return callback.message.chat.id
    return callback.from_user.id


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    _store().ensure(message.from_user.id)
    await _presenter().show_welcome(message.chat.id)


@router.message(Command("reset"))
async def on_reset(message: Message) -> None:
    if message.from_user is None:
        return
    async with _lock(message.from_user.id):
        _store().reset(message.from_user.id)
    await message.answer("Прогресс сброшен. Нажмите «Начать квест», чтобы пройти маршрут заново.")
    await _presenter().show_welcome(message.chat.id)


@router.callback_query(F.data == "menu:home")
async def on_home(callback: CallbackQuery) -> None:
    await _quiet(callback)
    _store().ensure(callback.from_user.id)
    await _presenter().show_welcome(_chat(callback))


@router.callback_query(F.data == "menu:route")
async def on_route(callback: CallbackQuery) -> None:
    await _quiet(callback)
    chat_id = _chat(callback)
    await callback.bot.send_message(chat_id, ROUTE_TEXT, reply_markup=route_kb())
    await _presenter().show_welcome(chat_id)


@router.callback_query(F.data == "menu:start")
async def on_begin(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    async with _lock(user_id):
        action = _store().try_begin(user_id)
        await _quiet(callback)
        chat_id = _chat(callback)
        if action == "done":
            await callback.bot.send_message(
                chat_id,
                "Вы уже собрали паспорт путешественника.",
                reply_markup=done_kb(),
            )
            return
        progress = _store().get(user_id)
        preface = None
        if action == "resume" and progress.step > 0:
            preface = "Продолжаем квест с текущего места."
        await _deliver(callback, progress.step, preface=preface)


@router.callback_query(F.data == "menu:restart")
async def on_restart(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    async with _lock(user_id):
        _store().restart(user_id)
        await _quiet(callback)
        await _deliver(callback, 0)


@router.callback_query(F.data == "menu:passport")
async def on_passport(callback: CallbackQuery) -> None:
    progress = _store().ensure(callback.from_user.id)
    if progress.status != "done":
        await _quiet(callback, "Паспорт соберётся в финале, когда будут все штампы")
        return
    await _quiet(callback)
    await _presenter().show_passport(_chat(callback))


@router.callback_query(F.data.startswith("n:"))
async def on_next(callback: CallbackQuery) -> None:
    beat_id = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id
    async with _lock(user_id):
        progress = _store().ensure(user_id)
        if progress.status != "active" or BEATS[progress.step].id != beat_id:
            await _quiet(callback, "Этот шаг уже позади")
            return
        beat = BEATS[progress.step]
        if beat.kind != "walk":
            await _quiet(callback)
            return
        await _quiet(callback)
        await _clear(callback)
        if not _store().advance(user_id, progress.step):
            return
        await _deliver(callback, progress.step + 1)


@router.callback_query(F.data.startswith("r:"))
async def on_retry(callback: CallbackQuery) -> None:
    beat_id = (callback.data or "").split(":", 1)[1]
    user_id = callback.from_user.id
    async with _lock(user_id):
        progress = _store().ensure(user_id)
        if progress.status != "active" or BEATS[progress.step].id != beat_id:
            await _quiet(callback, "Этот шаг уже позади")
            return
        await _quiet(callback)
        await _clear(callback)
        await _presenter().show_beat(_chat(callback), BEATS[progress.step], task_only=True)


async def _deliver(callback: CallbackQuery, beat_index: int, preface: str | None = None) -> None:
    if beat_index not in range(len(BEATS)):
        return
    beat = BEATS[beat_index]
    try:
        await _presenter().show_beat(_chat(callback), beat, preface=preface)
    except Exception:
        logger.exception("не открылся шаг %s", beat.id)
        await callback.bot.send_message(
            _chat(callback),
            "Не получилось открыть точку. Нажмите «Начать квест» в главном меню.",
        )
        return
    if beat.kind == "final":
        _store().mark_done(callback.from_user.id)


@router.callback_query(F.data.startswith("a:"))
async def on_answer(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await _quiet(callback)
        return
    _, beat_id, choice_id = parts
    user_id = callback.from_user.id
    async with _lock(user_id):
        progress = _store().ensure(user_id)
        if progress.status != "active" or BEATS[progress.step].id != beat_id:
            await _quiet(callback, "Этот шаг уже позади")
            return
        beat = BEATS[progress.step]
        choice = beat.choice(choice_id)
        if choice is None:
            await _quiet(callback)
            return
        await _quiet(callback)
        await _clear(callback)
        chat_id = _chat(callback)
        presenter = _presenter()
        if not choice.correct:
            await presenter.show_wrong(chat_id, beat, choice.reaction)
            return
        try:
            await presenter.show_reward(chat_id, beat, choice.reaction)
        except Exception:
            logger.exception("не отправился штамп, user=%s beat=%s", user_id, beat.id)
            await callback.bot.send_message(
                chat_id,
                "Не получилось отправить штамп. Нажмите «Начать квест» и выберите верный ответ ещё раз.",
            )
            return
        if not _store().advance(user_id, progress.step):
            return
        await _deliver(callback, progress.step + 1)


assert set(BY_ID) == {beat.id for beat in BEATS}
