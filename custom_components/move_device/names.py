"""Renaming rules. Pure: no Home Assistant imports, tested on their own.

A move swaps the old area's name for the new one, as whole words:
"Kitchen Light" in Kitchen becomes "Office Light" in Office. The old area's
aliases count as its name too, and the person can add their own find and
replace text. Entity IDs get the same swap on their slug:
``light.kitchen_light`` becomes ``light.office_light``. A name or ID without
any of the words is left as it is.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
import unicodedata

_SPACES = re.compile(r"\s+")


def slug(text: str) -> str:
    """Lower-case, ASCII, words joined by ``_`` (as Home Assistant's slugify)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


def _finds(finds: Iterable[str | None]) -> list[str]:
    """Distinct non-blank phrases, longest first, so "Living Room" wins over "Living"."""
    seen: dict[str, str] = {}
    for find in finds:
        phrase = _SPACES.sub(" ", (find or "").strip())
        if phrase and phrase.casefold() not in seen:
            seen[phrase.casefold()] = phrase
    return sorted(seen.values(), key=len, reverse=True)


def swap_name(
    name: str | None, finds: Iterable[str | None], replace: str
) -> str | None:
    """``name`` with every whole-word find replaced, or None when none match.

    Case is ignored when matching. Spaces in a find match any run of spaces.
    An empty ``replace`` removes the words and tidies the spaces left behind.
    """
    if not name:
        return None
    phrases = _finds(finds)
    if not phrases:
        return None
    pattern = re.compile(
        r"(?<!\w)("
        + "|".join(r"\s+".join(map(re.escape, p.split(" "))) for p in phrases)
        + r")(?!\w)",
        re.IGNORECASE,
    )
    new, count = pattern.subn(replace.strip(), name)
    if not count:
        return None
    new = _SPACES.sub(" ", new).strip()
    return new if new and new != name else None


def swap_object_id(
    entity_id: str, finds: Iterable[str | None], replace: str
) -> str | None:
    """``entity_id`` with the finds' slugs swapped in its object ID, or None.

    Only whole ``_``-separated parts match: ``kitchen`` matches
    ``light.kitchen_light`` but not ``light.kitchenette``.
    """
    domain, _, object_id = entity_id.partition(".")
    if not object_id:
        return None
    slugs = sorted(
        {s for s in (slug(f or "") for f in finds) if s}, key=len, reverse=True
    )
    if not slugs:
        return None
    pattern = re.compile(
        r"(?<![a-z0-9])(" + "|".join(map(re.escape, slugs)) + r")(?![a-z0-9])"
    )
    new_object_id, count = pattern.subn(slug(replace), object_id)
    if not count:
        return None
    new_object_id = re.sub(r"_+", "_", new_object_id).strip("_")
    if not new_object_id or new_object_id == object_id:
        return None
    return f"{domain}.{new_object_id}"


def valid_entity_id(entity_id: str) -> bool:
    """``domain.object_id`` with Home Assistant's allowed characters."""
    return bool(re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id or "")) and not (
        entity_id.split(".", 1)[1].startswith("_")
        or entity_id.split(".", 1)[1].endswith("_")
    )


def replace_entity_ids(text: str, renames: dict[str, str]) -> tuple[str, int]:
    """Replace whole entity IDs in ``text``. Returns the text and the count.

    An ID matches when it isn't part of a longer word: ``light.kitchen``
    matches in ``states('light.kitchen')`` and ``states.light.kitchen.state``
    but not in ``light.kitchen_2``.
    """
    if not renames:
        return text, 0
    pattern = re.compile(
        r"(?<![\w])("
        + "|".join(map(re.escape, sorted(renames, key=len, reverse=True)))
        + r")(?!\w)"
    )
    return pattern.subn(lambda m: renames[m.group(1)], text)


def uses_entity_ids(text: str, entity_ids: Iterable[str]) -> list[str]:
    """The entity IDs that appear whole in ``text``, in the order given."""
    found = []
    for entity_id in entity_ids:
        if re.search(r"(?<![\w])" + re.escape(entity_id) + r"(?!\w)", text):
            found.append(entity_id)
    return found
