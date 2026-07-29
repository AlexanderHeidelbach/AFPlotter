import matplotlib.pyplot as plt

from afplotter import palettes


def test_set_palette_by_name():
    p = palettes.set_palette("KIT")
    assert p.name == "KIT"
    assert palettes.get_palette().name == "KIT"


def test_set_palette_defaults_to_petroff():
    p = palettes.set_palette()
    assert p.name == "Petroff"


def test_get_palette_without_set_defaults_to_petroff():
    assert palettes.get_palette().name == "Petroff"


def test_set_palette_updates_rcparams_immediately():
    plt.rcParams["axes.prop_cycle"] = plt.cycler("color", ["#123456"])
    palettes.set_palette("KIT")
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == palettes.KIT_PALETTE.background


def test_kit_palette_excludes_kit_red_and_reserves_it_as_signal():
    assert palettes.KITColors.kit_red not in palettes.KIT_PALETTE.background
    assert palettes.KIT_PALETTE.signal == palettes.KITColors.kit_red


def test_lmu_palette_excludes_lmu_red_and_reserves_it_as_signal():
    assert palettes.LMUColors.lmu_red not in palettes.LMU_PALETTE.background
    assert palettes.LMU_PALETTE.signal == palettes.LMUColors.lmu_red


def test_petroff_palette_excludes_red_and_reserves_it_as_signal():
    assert palettes.PetroffColors.red not in palettes.PETROFF_PALETTE.background
    assert palettes.PETROFF_PALETTE.signal == palettes.PetroffColors.red
