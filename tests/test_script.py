from pathlib import Path

import pytest
import yaml

from care_voice.script import ScriptError, load_script, parse_script


def test_default_script_loads(script):
    ids = [q.id for q in script.iter_all()]
    assert ids == [
        "slept_well",
        "took_meds",
        "has_eaten",
        "in_pain",
        "pain_level",
        "pain_where",
        "had_fall",
        "day_of_week",
        "mood",
    ]
    assert script.question("in_pain").is_problem_question
    assert not script.question("took_meds").is_problem_question
    assert script.question("pain_level").max == 10


def test_example_scripts_load():
    root = Path(__file__).parent.parent / "examples"
    for path in root.glob("*script*.yaml"):
        assert load_script(path).questions


def _minimal(**overrides):
    q = {"id": "q1", "type": "yes_no", "ask": "OK?"}
    q.update(overrides)
    return {"questions": [q]}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "non-empty list"),
        ({"questions": []}, "non-empty list"),
        ({"questions": ["x"]}, "must be a mapping"),
        (_minimal(type="essay"), "unknown type"),
        (_minimal(ask=""), "'ask'"),
        (_minimal(type="scale", min=5, max=1), "min < max"),
        (_minimal(polarity="sideways"), "polarity"),
        (_minimal(followups=[{"id": "q2"}]), "'when'"),
        (_minimal(followups=[{"when": True, "id": "q1", "type": "text", "ask": "?"}]), "duplicate"),
        ("not a mapping", "must be a mapping"),
    ],
)
def test_invalid_scripts_are_rejected(data, message):
    with pytest.raises(ScriptError, match=message):
        parse_script(data)


def test_load_script_from_file(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump(_minimal()))
    script = load_script(path)
    assert script.question("q1").ask == "OK?"
    with pytest.raises(KeyError):
        script.question("missing")


def test_missing_file_raises_script_error(tmp_path):
    with pytest.raises(ScriptError, match="cannot read"):
        load_script(tmp_path / "nope.yaml")
