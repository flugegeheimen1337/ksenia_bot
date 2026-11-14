"""Отправка аудио, фото и текстов. file_id кэшируется после первой загрузки."""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto

from bot.config import MEDIA_DIR
from bot.content import PASSPORT_COVER, PERFORMER, SPREAD, SPREAD_CAPTION, START_PHOTO, WELCOME, Beat
from bot.db import Store
from bot.keyboards import choices_kb, final_kb, next_kb, welcome_kb

logger = logging.getLogger(__name__)


class Presenter:
    def __init__(self, bot: Bot, store: Store) -> None:
        self.bot = bot
        self.store = store

    def _file(self, relative: str) -> Path:
        path = MEDIA_DIR / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    async def show_welcome(self, chat_id: int) -> None:
        # У альбома нельзя повесить кнопки, поэтому текст и кнопки идут сразу следом.
        await self._album(chat_id, (START_PHOTO, PASSPORT_COVER))
        await self.bot.send_message(chat_id, WELCOME, reply_markup=welcome_kb())

    async def show_beat(self, chat_id: int, beat: Beat, *, task_only: bool = False, preface: str | None = None) -> None:
        if preface:
            await self.bot.send_message(chat_id, preface)
        if beat.kind == "final":
            await self.show_final(chat_id)
            return
        if not task_only:
            if beat.audio:
                await self._audio(chat_id, beat.audio, beat.audio_title)
            await self._photos(chat_id, beat.photos)
        markup = choices_kb(beat) if beat.kind == "quiz" else next_kb(beat)
        await self.bot.send_message(chat_id, beat.message(task_only=task_only), reply_markup=markup)

    async def show_wrong(self, chat_id: int, beat: Beat, reaction: str) -> None:
        from bot.keyboards import retry_kb

        await self.bot.send_message(chat_id, reaction, reply_markup=retry_kb(beat))

    async def show_reward(self, chat_id: int, beat: Beat, reaction: str) -> None:
        await self.bot.send_message(chat_id, reaction)
        reward = beat.reward
        if reward is None:
            return
        await self._photos(chat_id, reward.stamps, caption=reward.caption)
        if reward.photos:
            await self._photos(chat_id, reward.photos)
        if reward.note:
            await self.bot.send_message(chat_id, reward.note)

    async def show_final(self, chat_id: int) -> None:
        from bot.content import BEATS

        final = BEATS[-1]
        if final.audio:
            await self._audio(chat_id, final.audio, final.audio_title)
        await self._photos(chat_id, final.photos)
        await self.bot.send_message(chat_id, final.intro)
        await self._photo(chat_id, SPREAD, caption=SPREAD_CAPTION, reply_markup=final_kb())

    async def show_passport(self, chat_id: int) -> None:
        await self._photo(chat_id, SPREAD, caption=SPREAD_CAPTION, reply_markup=final_kb())

    async def _photos(self, chat_id: int, relative_paths: tuple[str, ...], caption: str | None = None) -> None:
        if not relative_paths:
            return
        if len(relative_paths) == 1:
            await self._photo(chat_id, relative_paths[0], caption=caption)
            return
        await self._album(chat_id, relative_paths, caption=caption)

    async def _photo(self, chat_id: int, relative: str, caption: str | None = None, reply_markup=None) -> None:
        file_id = self.store.get_file_id(relative)
        if file_id:
            try:
                await self.bot.send_photo(chat_id, file_id, caption=caption, reply_markup=reply_markup)
                return
            except TelegramBadRequest as exc:
                if not _bad_file_id(exc):
                    raise
                logger.info("сбрасываю file_id %s: %s", relative, exc)
                self.store.delete_file_id(relative)
        message = await self.bot.send_photo(
            chat_id,
            FSInputFile(self._file(relative)),
            caption=caption,
            reply_markup=reply_markup,
        )
        if message.photo:
            self.store.set_file_id(relative, message.photo[-1].file_id)

    async def _album(self, chat_id: int, relative_paths: tuple[str, ...], caption: str | None = None) -> None:
        cached = all(self.store.get_file_id(item) for item in relative_paths)
        try:
            messages = await self.bot.send_media_group(chat_id, self._album_media(relative_paths, caption, cached=cached))
        except TelegramBadRequest as exc:
            if not cached or not _bad_file_id(exc):
                raise
            for item in relative_paths:
                self.store.delete_file_id(item)
            messages = await self.bot.send_media_group(
                chat_id, self._album_media(relative_paths, caption, cached=False)
            )
        for relative, message in zip(relative_paths, messages):
            if message.photo:
                self.store.set_file_id(relative, message.photo[-1].file_id)

    def _album_media(self, relative_paths: tuple[str, ...], caption: str | None, *, cached: bool) -> list[InputMediaPhoto]:
        media: list[InputMediaPhoto] = []
        for index, relative in enumerate(relative_paths):
            file_id = self.store.get_file_id(relative) if cached else None
            source = file_id or FSInputFile(self._file(relative))
            media.append(
                InputMediaPhoto(
                    media=source,
                    caption=caption if index == 0 else None,
                )
            )
        return media

    async def _audio(self, chat_id: int, relative: str, title: str) -> None:
        file_id = self.store.get_file_id(relative)
        if file_id:
            try:
                await self.bot.send_audio(chat_id, file_id, title=title, performer=PERFORMER)
                return
            except TelegramBadRequest as exc:
                if not _bad_file_id(exc):
                    raise
                self.store.delete_file_id(relative)
        message = await self.bot.send_audio(
            chat_id,
            FSInputFile(self._file(relative), filename=f"{title}.mp3"),
            title=title,
            performer=PERFORMER,
        )
        if message.audio:
            self.store.set_file_id(relative, message.audio.file_id)


def _bad_file_id(exc: TelegramBadRequest) -> bool:
    text = str(exc).lower()
    return "file" in text and ("identifier" in text or "id" in text or "invalid" in text)
