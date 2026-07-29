from dataclasses import dataclass

import matplotlib.pyplot as plt
from cycler import cycler


class KITColors:
    """
    KIT color scheme plus additional grey shades
    """

    kit_green = "#009682"  # type: str
    kit_blue = "#4664aa"  # type: str
    kit_maygreen = "#8cb63c"  # type: str
    kit_yellow = "#fce500"  # type: str
    kit_orange = "#df9b1b"  # type: str
    kit_brown = "#a7822e"  # type: str
    kit_red = "#a22223"  # type: str
    kit_purple = "#a3107c"  # type: str
    kit_cyan = "#23a1e0"  # type: str
    kit_black = "#000000"  # type: str
    white = "#ffffff"  # type: str
    light_grey = "#bdbdbd"  # type: str
    grey = "#797979"  # type: str
    dark_grey = "#4e4e4e"  # type: str


class LMUColors:
    """LMU corporate color scheme."""

    lmu_green = "#00883A"  # R 0,   G 136, B 58
    lmu_blue = "#0F1987"  # R 15,  G 25,  B 135
    lmu_cyan = "#643BE3"  # R 100, G 59,  B 227
    lmu_violet = "#8C4091"  # R 140, G 64,  B 145
    lmu_red = "#D71919"  # R 215, G 25,  B 25
    lmu_orange = "#F18700"  # R 241, G 135, B 0


class PetroffColors:
    """
    Petroff 10 colour sequence, as shipped in matplotlib's ``petroff10`` style.

    See M. A. Petroff, "Accessible Color Sequences for Data Visualization",
    arXiv:2107.02270.
    """

    blue = "#3f90da"  # type: str
    amber = "#ffa90e"  # type: str
    red = "#bd1f01"  # type: str
    grey_green = "#94a4a2"  # type: str
    purple = "#832db6"  # type: str
    brown = "#a96b59"  # type: str
    orange = "#e76300"  # type: str
    khaki = "#b9ac70"  # type: str
    slate = "#717581"  # type: str
    pale_cyan = "#92dadd"  # type: str


@dataclass(frozen=True)
class Palette:
    """
    A named background color cycle plus a color reserved exclusively for signal.

    :param name: Unique palette identifier, e.g. "Petroff".
    :param background: Cycle colors for non-signal components. Must not
        contain ``signal``.
    :param signal: Color reserved for signal components; never appears in
        ``background``.
    """

    name: str
    background: list[str]
    signal: str


#: Petroff 10 (arXiv:2107.02270) minus its red, which is reserved for signal.
PETROFF_PALETTE = Palette(
    name="Petroff",
    background=[
        PetroffColors.blue,
        PetroffColors.amber,
        PetroffColors.grey_green,
        PetroffColors.purple,
        PetroffColors.brown,
        PetroffColors.orange,
        PetroffColors.khaki,
        PetroffColors.slate,
        PetroffColors.pale_cyan,
    ],
    signal=PetroffColors.red,
)

#: KIT color scheme minus kit_red, which is reserved for signal.
KIT_PALETTE = Palette(
    name="KIT",
    background=[
        KITColors.kit_green,
        KITColors.kit_blue,
        KITColors.kit_cyan,
        KITColors.kit_orange,
        KITColors.kit_maygreen,
        KITColors.kit_yellow,
        KITColors.kit_purple,
        KITColors.kit_brown,
        KITColors.dark_grey,
    ],
    signal=KITColors.kit_red,
)

#: LMU color scheme minus lmu_red, which is reserved for signal.
LMU_PALETTE = Palette(
    name="LMU",
    background=[
        LMUColors.lmu_green,
        LMUColors.lmu_blue,
        LMUColors.lmu_cyan,
        LMUColors.lmu_violet,
        LMUColors.lmu_orange,
    ],
    signal=LMUColors.lmu_red,
)

_PALETTES: dict[str, Palette] = {
    PETROFF_PALETTE.name: PETROFF_PALETTE,
    KIT_PALETTE.name: KIT_PALETTE,
    LMU_PALETTE.name: LMU_PALETTE,
}

_CURRENT_PALETTE: Palette | None = None


def register_palette(palette: Palette) -> None:
    """
    Register a new palette.

    :param palette: The palette to register.
    :raises ValueError: If a palette with the same name is already registered.
    :return: None
    """
    if palette.name in _PALETTES:
        raise ValueError(f"Palette {palette.name} already registered")
    _PALETTES[palette.name] = palette


def get(name: str) -> Palette:
    """
    Look up a registered palette by name.

    :param name: Palette name, e.g. "Petroff".
    :raises ValueError: If no palette with that name is registered.
    :return: The matching Palette.
    """
    try:
        return _PALETTES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown palette '{name}'. Available: {', '.join(_PALETTES)}") from exc


def set_palette(name: str = "Petroff") -> Palette:
    """
    Select the active color palette and apply it immediately.

    :param name: Palette name, e.g. "KIT". Defaults to "Petroff".
    :return: The now-current Palette.
    """
    global _CURRENT_PALETTE
    _CURRENT_PALETTE = get(name)
    plt.rcParams["axes.prop_cycle"] = cycler("color", _CURRENT_PALETTE.background)
    return _CURRENT_PALETTE


def get_palette() -> Palette:
    """
    Get the current palette, defaulting to "Petroff" if none has been set.

    :return: The current Palette.
    """
    global _CURRENT_PALETTE
    if _CURRENT_PALETTE is None:
        _CURRENT_PALETTE = PETROFF_PALETTE
    return _CURRENT_PALETTE
