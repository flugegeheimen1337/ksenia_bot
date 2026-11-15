"""Кнопки квеста."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.content import ROUTE_URL, Beat


def welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать квест🔍", callback_data="menu:start")],
            [InlineKeyboardButton(text="Хочу посмотреть маршрут🗺️", callback_data="menu:route")],
        ]
    )


def route_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть маршрут на карте", url=ROUTE_URL)],
        ]
    )


def choices_kb(beat: Beat) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=choice.label, callback_data=f"a:{beat.id}:{choice.id}")]
            for choice in beat.choices
        ]
    )


def retry_kb(beat: Beat) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать ещё раз", callback_data=f"r:{beat.id}")],
        ]
    )


def next_kb(beat: Beat) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=beat.continue_label, callback_data=f"n:{beat.id}")],
        ]
    )


def done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Показать паспорт", callback_data="menu:passport")],
            [InlineKeyboardButton(text="Пройти квест ещё раз", callback_data="menu:restart")],
        ]
    )


def final_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="В главное меню", callback_data="menu:home")],
        ]
    )
