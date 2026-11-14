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


def test_file_id_cache(tmp_path: Path) -> None:
    store = Store(tmp_path / "bot.sqlite")
    assert store.get_file_id("audio/p1-hotel.mp3") is None
    store.set_file_id("audio/p1-hotel.mp3", "abc")
    assert store.get_file_id("audio/p1-hotel.mp3") == "abc"
    store.delete_file_id("audio/p1-hotel.mp3")
    assert store.get_file_id("audio/p1-hotel.mp3") is None
