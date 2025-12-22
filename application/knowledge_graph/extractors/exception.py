from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class ExceptionCue:
    cue: str
    raw: str


# MVP cues (high-recall, will refine later)
CUE_PATTERNS = [
    r"\btrừ\s+trường\s+hợp\b",
    r"\bngoại\s+trừ\b",
    r"\bkhông\s+áp\s+dụng\b",
    r"\btrừ\s+khi\b",
    r"\bkhông\s+bao\s+gồm\b",
]

RE_EXCEPTION = re.compile("|".join(CUE_PATTERNS), flags=re.IGNORECASE)


def extract_exception_cues(text: str) -> List[ExceptionCue]:
    if not text:
        return []
    return [ExceptionCue(cue=m.group(0).lower(), raw=m.group(0)) for m in RE_EXCEPTION.finditer(text)]
