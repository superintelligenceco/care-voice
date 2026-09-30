import pytest

from care_voice.extractors.rules import (
    detect_flags,
    normalize,
    parse_scale,
    parse_weekday,
    parse_yes_no,
)


def test_normalize():
    assert normalize("  I DIDN\u2019T,   sleep!! ") == "i didn't sleep"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Yes", True),
        ("yeah, I did", True),
        ("Of course I have", True),
        ("I took them with breakfast", True),
        ("I slept like a log, really well", True),
        ("No", False),
        ("nope", False),
        ("Not yet", False),
        ("I forgot", False),
        ("I didn't sleep well", False),
        ("Not very well, no", False),
        ("I haven't had anything", False),
        ("", None),
        ("banana", None),
        ("What was the question?", None),
    ],
)
def test_yes_no(text, expected):
    assert parse_yes_no(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I'm fine, thank you", False),
        ("All good", False),
        ("My knee hurts", True),
        ("A little in my back", True),
        ("It hurts, I can't bend down", True),
        ("I don't have any pain", False),
        ("No pain at all", False),
        ("I fell in the kitchen but I'm okay", True),
        ("I didn't fall", False),
    ],
)
def test_yes_no_problem_questions(text, expected):
    assert parse_yes_no(text, problem_question=True) is expected


@pytest.mark.parametrize(
    ("text", "lo", "hi", "expected"),
    [
        ("4", 1, 5, (4, "number")),
        ("I'd say a three", 1, 5, (3, "number")),
        ("maybe six or seven", 0, 10, (6, "number")),
        ("none", 0, 10, (0, "number")),
        ("9", 1, 5, (None, "out_of_range")),
        ("wonderful", 1, 5, (5, "word")),
        ("pretty low today", 1, 5, (2, "word")),
        ("not great", 1, 5, (2, "word")),
        ("not bad", 1, 5, (3, "word")),
        ("wonderful", 0, 10, (None, "no_number")),
        ("I don't know", 1, 5, (None, "no_number")),
    ],
)
def test_scale(text, lo, hi, expected):
    assert parse_scale(text, lo, hi) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("It's Wednesday", "wednesday"),
        ("wednesday I think", "wednesday"),
        ("Is it Tuesday or Wednesday?", None),
        ("no idea", None),
    ],
)
def test_weekday(text, expected):
    assert parse_weekday(text) == expected


@pytest.mark.parametrize(
    ("text", "flags"),
    [
        ("Help me, I can't get up", {"emergency"}),
        ("I have chest pains", {"emergency", "pain"}),
        ("I slipped in the bathroom", {"fall"}),
        ("No, I haven't had a fall", set()),
        ("My hip is sore", {"pain"}),
        ("no pain today", set()),
        ("Where am I? Who are you?", {"disoriented"}),
        ("I don't know what day it is", {"disoriented"}),
        ("Lovely morning", set()),
    ],
)
def test_detect_flags(text, flags):
    assert detect_flags(text) == frozenset(flags)


def test_extract_day_of_week_marks_correctness(script, extractor, ctx):
    q = script.question("day_of_week")
    assert extractor.extract(q, "Wednesday", ctx).detail["correct"] is True
    wrong = extractor.extract(q, "Friday", ctx)
    assert wrong.understood and wrong.detail["correct"] is False


def test_extract_text_and_unclear(script, extractor, ctx):
    where = extractor.extract(script.question("pain_where"), " my left knee ", ctx)
    assert where.value == "my left knee"
    unclear = extractor.extract(script.question("mood"), "hmm", ctx)
    assert not unclear.understood and unclear.value is None
    assert unclear.source == "rules"
