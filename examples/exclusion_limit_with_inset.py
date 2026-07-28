# examples/exclusion_limit_with_inset.py
"""
Mirrors a real cross-section upper-limit plot: an expected/observed curve
with a +/-1 sigma band and a zoomed inset, styled with BelleII colors.

Run: python examples/exclusion_limit_with_inset.py
"""

import os

from afplotter import GenericPlotter, KITColors, set_experiment
from _synthetic_data import make_exclusion_curve

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main() -> None:
    set_experiment("BelleII")
    masses, expected, band_lower, band_upper = make_exclusion_curve(seed=5)

    plotter = GenericPlotter()
    plotter.set_matplotlibrc_params(16)
    plotter.xlabel = "$m_a$ (GeV/c$^2$)"
    plotter.ylabel = "$\\sigma$ (fb)"
    plotter.xlim = (0.2, 9.5)
    plotter.ylim = (0.0, float(band_upper.max()) * 1.2)
    plotter.luminosity_value = 62.8

    plotter.add_generic_plot("plot", masses, expected, label="Expected", color="black", ls="--", lw=2)
    plotter.add_generic_plot(
        "fill_between", x=masses, y1=band_lower, y2=band_upper, color=KITColors.kit_yellow, label="$\\pm 1\\sigma$"
    )

    plotter.add_inset(
        xlim=(0.2, 2.0),
        ylim=(0.0, float(expected[masses < 2.0].max()) * 1.3),
        bbox_to_anchor=(0.45, 0.5, 0.5, 0.45),
        width="100%",
        height="100%",
        title="Low-mass region",
        tick_labelsize=10,
        title_fontsize=11,
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plotter.savedir = OUTPUT_DIR
    plotter.savename = "exclusion_limit_with_inset"
    plotter.saveformat = "png"
    plotter.plot(save=True)
    print("Saved to", plotter.savepath or plotter._get_savestring())


if __name__ == "__main__":
    main()
