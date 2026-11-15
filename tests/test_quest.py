"""Сценарий, штампы и сохранение прогресса. Сеть и токен не нужны."""

from pathlib import Path

from bot.config import MEDIA_DIR
from bot.content import BEATS, ROUTE_URL, WELCOME, validate
from bot.db import Store
from bot.keyboards import welcome_kb

EXPECTED_CORRECT = {
    "p1": "b",
    "p2": "b",
    "p3d": "b",
    "p4": "b",
    "p5": "b",
    "p6": "b",
    "p7": "b",
    "p8": "a",
    "p9": "a",
}


def test_scenario_files_and_answers() -> None:
    validate()
    quizzes = [beat for beat in BEATS if beat.kind == "quiz"]
    assert [beat.id for beat in quizzes] == list(EXPECTED_CORRECT)
    for beat in quizzes:
        correct = next(choice for choice in beat.choices if choice.correct)
        assert correct.id == EXPECTED_CORRECT[beat.id]
        assert "крыло" in beat.choices[1].reaction.lower() or beat.id != "p1"

    point3 = [beat for beat in BEATS if beat.id.startswith("p3")]
    assert [beat.audio for beat in point3] == [
        "audio/p3-marx.mp3",
        "audio/p3-post.mp3",
        "audio/p3-mvd.mp3",
        "audio/p3-shop.mp3",
    ]
    assert [beat.kind for beat in point3] == ["walk", "walk", "walk", "quiz"]
    assert point3[-1].reward is not None
    assert point3[-1].reward.stamps == ("stamps/03.jpg", "stamps/04.png")

    library = next(beat for beat in BEATS if beat.id == "p7")
    assert library.reward is not None
    assert "Дом физкультуры" in library.reward.note
    assert len(library.reward.photos) == 3

    stamps = [path for beat in quizzes if beat.reward for path in beat.reward.stamps]
    assert stamps == [
        "stamps/01.png",
        "stamps/02.png",
        "stamps/03.jpg",
        "stamps/04.png",
        "stamps/05.png",
        "stamps/06.png",
        "stamps/07.png",
        "stamps/08.jpg",
        "stamps/09.png",
        "stamps/10.png",
    ]
    assert BEATS[-1].kind == "final"
    assert "vLHBIAZT" in ROUTE_URL
    assert "10 штампов" in WELCOME
    post = next(beat for beat in BEATS if beat.id == "p3b")
    assert "дом № 22" in post.intro
    assert "Главпочтамт" in post.intro


def test_certificate_writes_the_name_into_the_blank() -> None:
    from PIL import Image

    from bot.certificate import NAME_BOX, render_certificate, traveler_name

    class User:
        def __init__(self, first_name, last_name=None, username=None):
            self.first_name = first_name
            self.last_name = last_name
            self.username = username

    assert traveler_name(User("Мария", "Соколова")) == "Мария Соколова"
    assert traveler_name(User("", username="guest")) == "guest"
    assert traveler_name(None) == "Путешественник"

    blank = Image.open(MEDIA_DIR / "photos/certificate.jpg").convert("RGB")
    named = render_certificate("Мария Соколова")
    long = render_certificate("Александр Константинович Вяземский")
    assert named.size == blank.size == (1280, 853)
    left, top, right, bottom = NAME_BOX
    assert _changed_pixels(blank, named, NAME_BOX) > 400
    assert _changed_pixels(blank, long, NAME_BOX) > 400
    # Надпись «9 точек квеста» под плашкой остаётся как на шаблоне.
    assert named.getpixel((640, 520)) == blank.getpixel((640, 520))
    for image in (named, long):
        for x in range(left, right, 12):
            assert image.getpixel((x, 340)) == blank.getpixel((x, 340))
            assert image.getpixel((x, 470)) == blank.getpixel((x, 470))


def _changed_pixels(before, after, box) -> int:
    left, top, right, bottom = box
    changed = 0
    for y in range(top, bottom, 2):
        for x in range(left, right, 2):
            if before.getpixel((x, y)) != after.getpixel((x, y)):
                changed += 1
    return changed


def test_every_media_file_is_used() -> None:
    from bot.content import media_paths

    used = set(media_paths())
    on_disk = {
        str(path.relative_to(MEDIA_DIR))
        for folder in ("photos", "audio", "stamps")
        for path in (MEDIA_DIR / folder).iterdir()
        if path.is_file()
    }
    assert used == on_disk


def test_welcome_buttons() -> None:
    labels = [row[0].text for row in welcome_kb().inline_keyboard]
    assert labels == ["Начать квест🔍", "Хочу посмотреть маршрут🗺️"]


def test_progress_survives_wrong_answers_and_restart(tmp_path: Path) -> None:
    store = Store(tmp_path / "bot.sqlite")
    user_id = 7
    assert store.try_begin(user_id) == "begin"
    assert store.try_begin(user_id) == "resume"

    for beat in BEATS:
        progress = store.get(user_id)
        assert progress.step == BEATS.index(beat)
        assert progress.status == "active"
        if beat.kind == "final":
            store.mark_done(user_id)
            break
        if beat.kind == "walk":
            assert store.advance(user_id, progress.step)
            assert not store.advance(user_id, progress.step)
            continue
        assert beat.reward is not None
        wrong = next(choice for choice in beat.choices if not choice.correct)
        assert wrong.reaction
        assert store.get(user_id).step == progress.step
        assert store.advance(user_id, progress.step)

    assert store.get(user_id).status == "done"
    assert store.try_begin(user_id) == "done"
    store.restart(user_id)
    assert store.get(user_id).status == "active"
    assert store.get(user_id).step == 0
    store.reset(user_id)
    assert store.try_begin(user_id) == "begin"


def test_quest_opens_only_with_the_link(tmp_path: Path) -> None:
    import sqlite3

    from bot.access import link_grants

    assert link_grants("right-code", "right-code")
    assert not link_grants("wrong-code", "right-code")
    assert not link_grants("", "right-code")
    assert not link_grants(None, "right-code")
    assert not link_grants("right-code-extra", "right-code")

    legacy = tmp_path / "legacy.sqlite"
    with sqlite3.connect(legacy) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                step INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO users VALUES (1, 'active', 3, '2026-01-01T00:00:00+00:00')"
        )

    store = Store(legacy)
    assert store.is_allowed(1)
    assert not store.is_allowed(2)
    store.allow(2)
    assert store.is_allowed(2)
    store.reset(2)
    assert store.is_allowed(2)

    fresh = Store(tmp_path / "fresh.sqlite")
    assert not fresh.is_allowed(5)
    fresh.ensure(5)
    assert not fresh.is_allowed(5)


def test_file_id_cache(tmp_path: Path) -> None:
    store = Store(tmp_path / "bot.sqlite")
    assert store.get_file_id("audio/p1-hotel.mp3") is None
    store.set_file_id("audio/p1-hotel.mp3", "abc")
    assert store.get_file_id("audio/p1-hotel.mp3") == "abc"
    store.delete_file_id("audio/p1-hotel.mp3")
    assert store.get_file_id("audio/p1-hotel.mp3") is None
