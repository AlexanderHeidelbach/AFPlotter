import pytest

from afplotter import palettes


def _dummy_palette(name: str) -> "palettes.Palette":
    return palettes.Palette(name=name, background=["#000000"], signal="#ffffff")


def test_register_and_get():
    p = _dummy_palette("TestPalette")
    palettes.register_palette(p)
    assert palettes.get("TestPalette") is p


def test_register_duplicate_raises():
    p = _dummy_palette("TestPalette")
    palettes.register_palette(p)
    with pytest.raises(ValueError, match="already registered"):
        palettes.register_palette(p)


def test_get_unknown_raises():
    with pytest.raises(ValueError, match="Unknown palette"):
        palettes.get("NoSuchPalette")


def test_builtin_palettes_are_registered():
    assert palettes.get("Petroff").name == "Petroff"
    assert palettes.get("KIT").name == "KIT"
    assert palettes.get("LMU").name == "LMU"
