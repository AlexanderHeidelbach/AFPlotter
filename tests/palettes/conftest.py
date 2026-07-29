import pytest

from afplotter import palettes


def _reset_palette_state():
    palettes._PALETTES = {
        palettes.PETROFF_PALETTE.name: palettes.PETROFF_PALETTE,
        palettes.KIT_PALETTE.name: palettes.KIT_PALETTE,
        palettes.LMU_PALETTE.name: palettes.LMU_PALETTE,
    }
    palettes._CURRENT_PALETTE = None


@pytest.fixture(autouse=True)
def clean_palette_registry():
    """Reset the module-global palette registry/context before and after each test.

    Without this, tests that register or select palettes leak state into
    whichever test runs next, so results depend on run order.
    """
    _reset_palette_state()
    yield
    _reset_palette_state()
