from __future__ import annotations

from datetime import date

import pytest

from care_voice.extractors import ExtractionContext, RuleBasedExtractor
from care_voice.script import CheckinScript, load_script

# 30 September 2026 is a Wednesday.
WEDNESDAY = date(2026, 9, 30)


@pytest.fixture
def script() -> CheckinScript:
    return load_script()


@pytest.fixture
def extractor() -> RuleBasedExtractor:
    return RuleBasedExtractor()


@pytest.fixture
def ctx() -> ExtractionContext:
    return ExtractionContext(today=WEDNESDAY, person_name="Ada")
