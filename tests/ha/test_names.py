"""Renaming rules."""

from __future__ import annotations

from custom_components.move_device.names import (
    slug,
    swap_name,
    swap_object_id,
    uses_entity_ids,
    valid_entity_id,
)


def test_swap_name_whole_words_any_case() -> None:
    assert swap_name("Kitchen Light", ["Kitchen"], "Office") == "Office Light"
    assert swap_name("kitchen light", ["Kitchen"], "Office") == "Office light"
    assert swap_name("Kitchenette Light", ["Kitchen"], "Office") is None
    assert swap_name("Lamp", ["Kitchen"], "Office") is None
    assert swap_name(None, ["Kitchen"], "Office") is None
    assert swap_name("Kitchen Light", [], "Office") is None


def test_swap_name_longest_phrase_and_spaces() -> None:
    finds = ["Living", "Living Room", None, " "]
    assert swap_name("Living  Room Lamp", finds, "Den") == "Den Lamp"
    assert swap_name("Living Lamp", finds, "Den") == "Den Lamp"


def test_swap_name_remove_words() -> None:
    assert swap_name("Kitchen Light", ["Kitchen"], "") == "Light"
    assert swap_name("Kitchen", ["Kitchen"], "") is None


def test_swap_object_id() -> None:
    assert swap_object_id("light.kitchen_light", ["Kitchen"], "Office") == (
        "light.office_light"
    )
    assert swap_object_id("light.kitchenette", ["Kitchen"], "Office") is None
    assert swap_object_id(
        "sensor.living_room_temp", ["Living Room"], "Guest Bedroom"
    ) == ("sensor.guest_bedroom_temp")
    assert swap_object_id("light.kitchen", ["Kitchen"], "") is None
    assert swap_object_id("light.kitchen_lamp", ["Kitchen"], "") == "light.lamp"
    assert swap_object_id("bad", ["Kitchen"], "Office") is None
    assert swap_object_id("light.kitchen", [], "Office") is None


def test_slug_and_valid() -> None:
    assert slug("Café Böse!") == "cafe_bose"
    assert valid_entity_id("light.office_lamp")
    assert not valid_entity_id("light.Office")
    assert not valid_entity_id("light._x")
    assert not valid_entity_id("lightx")


def test_find_whole_ids() -> None:
    text = (
        "entity_id: light.kitchen\n"
        "value: \"{{ states('light.kitchen') }} {{ states.light.kitchen.state }}\"\n"
        "other: light.kitchen_2\n"
    )
    assert uses_entity_ids(text, ["light.kitchen", "light.den"]) == ["light.kitchen"]
    # Part of a longer ID doesn't count.
    assert uses_entity_ids("light.kitchen_2", ["light.kitchen"]) == []
    assert uses_entity_ids("states.light.kitchen.state", ["light.kitchen"]) == [
        "light.kitchen"
    ]


def test_uses_entity_ids_skips_patterns_for_absent_ids(monkeypatch) -> None:
    """IDs that aren't in the text at all never get a pattern built and run."""
    from custom_components.move_device import names

    calls = []
    real = names.re.search

    def search(*args, **kwargs):
        calls.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(names.re, "search", search)
    text = '{"entity_id": "light.kitchen"}'
    assert uses_entity_ids(text, ["light.den", "sensor.hall", "light.kitchen"]) == [
        "light.kitchen"
    ]
    assert len(calls) == 1
