"""
Deterministic text preparation. Pure stdlib, no I/O.

Does two jobs that directly cut LLM cost:
  1. clean(): normalise PDF artefacts (ligatures, icon glyphs, ragged whitespace)
  2. split_contacts(): pull emails/phones/urls out with regex and REMOVE them
     from the text, so they are neither billed as tokens nor sent to a third party.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"https?://[^\s)>\]]+|www\.[^\s)>\]]+", re.I)
# Two shapes, both with literal spaces (never \s) so a match can't cross a line:
#   +<country code> followed by digits/separators   e.g. +91741701076, +1 (415) 555-0100
#   grouped or bare local numbers: 415 555 0100, (415) 555-0100, 9876543210
# Date ranges ("2019 - 2023") and scores ("10.00) 2019") deliberately don't fit.
_PHONE = re.compile(
    r"\+\d[\d ().-]{8,}\d"
    r"|(?<![\w.])(?:\(?\d{2,5}\)?(?:[ .-]\d{2,5}){2,4}|\d{10})(?!\d)"
)

_DROP_CATS = {"Cc", "Cf", "Cs", "Co", "Cn"}  # control / format / unassigned: removed
_ICON_CAT = "So"  # icon glyphs (phone, mail...): replaced by a SPACE, not removed


@dataclass
class Contacts:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


def _tidy(text: str) -> str:
    lines = (re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n"))
    lines = ("" if not re.search(r"\w", ln) else ln for ln in lines)  # drop "| | |" leftovers
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):  # collapse runs of blank lines
            out.append(ln)
    return "\n".join(out).strip()


def clean(text: str) -> str:
    # NFKC folds ligatures (ﬁ -> fi, ﬂ -> fl, ﬀ -> ff) and width variants
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    # Icons become spaces: dropping them would glue "phone+91..." onto the next
    # token and the email regex would swallow it as part of the local part.
    out = []
    for ch in t:
        cat = unicodedata.category(ch)
        if ch == "\n":
            out.append(ch)
        elif cat == _ICON_CAT:
            out.append(" ")
        elif cat not in _DROP_CATS:
            out.append(ch)
    return _tidy("".join(out))


def _dedupe(items) -> list[str]:
    return list(dict.fromkeys(items))


def split_contacts(text: str) -> tuple[str, Contacts]:
    emails = _dedupe(_EMAIL.findall(text))
    text = _EMAIL.sub(" ", text)

    urls = _dedupe(u.rstrip(".,;") for u in _URL.findall(text))
    text = _URL.sub(" ", text)

    phones: list[str] = []

    def _phone(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        if 10 <= len(digits) <= 15:  # rejects date ranges like "2019 - 2023"
            phones.append(re.sub(r" +", " ", m.group()).strip())
            return " "
        return m.group()

    text = _PHONE.sub(_phone, text)
    return _tidy(text), Contacts(emails, _dedupe(phones), urls)


def prepare(raw: str) -> tuple[str, Contacts]:
    """raw PDF/DOCX text -> (text to send to the LLM, contacts found by regex)."""
    return split_contacts(clean(raw))
