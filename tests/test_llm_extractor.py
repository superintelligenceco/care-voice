import json

import pytest

from care_voice.extractors import LLMExtractor

from .helpers import local_server


def completion(content):
    return {"choices": [{"message": {"content": content}}]}


def fixed(payload, status=200):
    return lambda *_: (status, payload)


def test_llm_extracts_and_sends_minimal_context(script, ctx):
    reply = completion(json.dumps({"understood": True, "value": False, "flags": []}))
    with local_server(fixed(reply)) as (url, requests):
        extractor = LLMExtractor(url, "test-model", api_key="k")
        answer = extractor.extract(script.question("took_meds"), "I skipped them", ctx)
    assert (answer.value, answer.understood, answer.source) == (False, True, "llm")
    (req,) = requests
    assert req["path"] == "/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer k"
    sent = json.loads(req["body"])
    assert sent["model"] == "test-model"
    assert sent["temperature"] == 0
    user = json.loads(sent["messages"][1]["content"])
    assert user == {
        "question": "Have you taken your morning medication?",
        "type": "yes_no",
        "problem_question": False,
        "today": "wednesday",
        "reply": "I skipped them",
    }
    assert "Ada" not in req["body"].decode()


def test_rule_flags_always_merged(script, ctx):
    reply = completion(json.dumps({"understood": True, "value": True, "flags": ["bogus"]}))
    with local_server(fixed(reply)) as (url, _):
        answer = LLMExtractor(url, "m").extract(
            script.question("slept_well"), "yes but help me I can't get up", ctx
        )
    assert "emergency" in answer.flags
    assert "bogus" not in answer.flags


@pytest.mark.parametrize(
    ("qid", "value", "expected"),
    [
        ("mood", 4, 4),
        ("pain_level", 7.0, 7),
        ("day_of_week", "Friday", "friday"),
        ("pain_where", "left knee", "left knee"),
    ],
)
def test_value_coercion(script, ctx, qid, value, expected):
    reply = completion(json.dumps({"understood": True, "value": value, "flags": ["pain"]}))
    with local_server(fixed(reply)) as (url, _):
        answer = LLMExtractor(url, "m").extract(script.question(qid), "whatever", ctx)
    assert answer.value == expected
    assert "pain" in answer.flags
    if qid == "day_of_week":
        assert answer.detail["correct"] is False


def test_not_understood(script, ctx):
    reply = completion(json.dumps({"understood": False, "value": None}))
    with local_server(fixed(reply)) as (url, _):
        answer = LLMExtractor(url, "m").extract(script.question("mood"), "the cat", ctx)
    assert not answer.understood


@pytest.mark.parametrize(
    ("qid", "payload", "status"),
    [
        ("took_meds", completion(json.dumps({"understood": True, "value": "yes"})), 200),
        ("mood", completion(json.dumps({"understood": True, "value": 9})), 200),
        ("mood", completion(json.dumps({"understood": True, "value": True})), 200),
        ("day_of_week", completion(json.dumps({"understood": True, "value": "soon"})), 200),
        ("mood", completion("not json"), 200),
        ("mood", completion("[1, 2]"), 200),
        ("mood", {"unexpected": True}, 200),
        ("mood", {"error": "rate limited"}, 429),
    ],
)
def test_falls_back_to_rules_on_bad_output(script, ctx, qid, payload, status):
    with local_server(fixed(payload, status)) as (url, _):
        answer = LLMExtractor(url, "m").extract(script.question(qid), "3", ctx)
    assert answer.source == "rules"
    assert "llm_error" in answer.detail


def test_falls_back_when_unreachable(script, ctx):
    extractor = LLMExtractor("http://127.0.0.1:9", "m", timeout=1)
    answer = extractor.extract(script.question("took_meds"), "yes", ctx)
    assert (answer.value, answer.source) == (True, "rules")


def test_rejects_bad_base_url():
    with pytest.raises(ValueError):
        LLMExtractor("file:///etc/passwd", "m")
