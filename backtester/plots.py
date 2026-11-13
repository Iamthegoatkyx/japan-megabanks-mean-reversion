"""Charts saved as PNG files. Colours come from one small palette, defined once here."""
from __future__ import annotations

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
STRATEGY = "#2a78d6"   # blue
BENCHMARK = "#eb6834"  # orange
NEGATIVE = "#e34948"   # red end of the diverging scale
NEUTRAL = "#f0efec"    # grey midpoint = "no difference"

# Red (worse than buy-and-hold) -> grey (equal) -> blue (better).
DIVERGING = LinearSegmentedColormap.from_list("red_grey_blue", [NEGATIVE, NEUTRAL, STRATEGY])


def _style(ax):
    """Quiet axes: light grid, no box, muted tick labels."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=INK_2, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def heatmap(grid: pd.DataFrame, value: str, path, title: str, highlight=None) -> None:
    """Grid of (threshold x window) cells coloured by `value`, centred on 0.

    highlight: (threshold, window) of the preregistered rule, outlined in black.
    """
    table = grid.pivot(index="threshold", columns="window", values=value)
    limit = float(np.nanmax(np.abs(table.to_numpy()))) or 1.0
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)

    fig, ax = plt.subplots(figsize=(7.5, 5), facecolor=SURFACE)
    image = ax.imshow(table.to_numpy(), cmap=DIVERGING, norm=norm, aspect="auto")
    ax.set_xticks(range(len(table.columns)), [str(w) for w in table.columns])
    ax.set_yticks(range(len(table.index)), [f"{t:.0%}" for t in table.index])
    ax.set_xlabel("Moving-average window (trading days)", color=INK_2)
    ax.set_ylabel("Entry: % below moving average", color=INK_2)
    ax.tick_params(colors=INK_2, length=0)
    for side in ax.spines.values():
        side.set_visible(False)

    # Write the number in every cell: dark text on pale cells, white on strong ones.
    for i, threshold in enumerate(table.index):
        for j, window in enumerate(table.columns):
            v = table.loc[threshold, window]
            colour = "white" if abs(v) > 0.6 * limit else INK
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=9, color=colour)

    if highlight is not None:
        i = list(table.index).index(highlight[0])
        j = list(table.columns).index(highlight[1])
        ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                   edgecolor=INK, linewidth=2.5))
    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=INK_2, length=0)
    ax.set_title(title, color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def cost_chart(costs: pd.DataFrame, path, title: str, preregistered_bps=None) -> None:
    """Portfolio Sharpe of strategy and buy-and-hold as costs rise."""
    fig, ax = plt.subplots(figsize=(7, 4.2), facecolor=SURFACE)
    _style(ax)
    x = costs.index.to_numpy()
    for column, label, colour in [("strategy_sharpe", "Strategy", STRATEGY),
                                  ("buy_hold_sharpe", "Buy & hold", BENCHMARK)]:
        y = costs[column].to_numpy()
        ax.plot(x, y, color=colour, linewidth=2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2, label=label)
        ax.annotate(label, (x[-1], y[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=INK_2, fontsize=9)
    ax.axhline(0, color=BASELINE, linewidth=1)
    if preregistered_bps is not None:
        ax.axvline(preregistered_bps, color=MUTED, linewidth=1, linestyle=":")
        ax.annotate(f"preregistered ({preregistered_bps:g} bps)", (preregistered_bps, 0),
                    xycoords=("data", "axes fraction"), xytext=(4, 4),
                    textcoords="offset points", color=MUTED, fontsize=8)
    ax.set_xticks(x, [f"{c:g}" for c in x])
    ax.set_xlabel("Cost per side (bps)", color=INK_2)
    ax.set_ylabel("Sharpe ratio", color=INK_2)
    ax.set_xlim(x[0] - 2, x[-1] + 12)
    ax.legend(frameon=False, labelcolor=INK_2, loc="lower left")
    ax.set_title(title, color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def equity_chart(strategy_net: pd.Series, benchmark_net: pd.Series, path, title: str) -> None:
    """Top: growth of 1 yen (log scale). Bottom: drawdown from the previous peak.

    Log scale because over many years a fall from 2.0 to 1.0 and from 1.0 to
    0.5 are both -50%, and should look the same size.
    """
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 6), sharex=True, facecolor=SURFACE,
                                      gridspec_kw={"height_ratios": [2, 1]})
    for ax in (top, bottom):
        _style(ax)
    for net, label, colour in [(strategy_net, "Strategy", STRATEGY),
                               (benchmark_net, "Buy & hold", BENCHMARK)]:
        equity = (1 + net).cumprod()
        drawdown = equity / np.maximum(equity.cummax(), 1.0) - 1
        top.plot(equity.index, equity, color=colour, linewidth=2, label=label)
        top.annotate(f"{label} {equity.iloc[-1]:.2f}", (equity.index[-1], equity.iloc[-1]),
                     xytext=(6, 0), textcoords="offset points", va="center",
                     color=INK_2, fontsize=9)
        bottom.plot(drawdown.index, drawdown, color=colour, linewidth=1.5)
    top.set_yscale("log")
    # Plain numbers (0.5, 1, 2) instead of 10^-1-style labels.
    plain = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}")
    top.yaxis.set_major_formatter(plain)
    top.yaxis.set_minor_formatter(plain)
    top.tick_params(axis="y", which="minor", labelsize=8, labelcolor=MUTED, length=0)
    top.axhline(1.0, color=BASELINE, linewidth=1)
    top.set_ylabel("Growth of ¥1 (log)", color=INK_2)
    top.legend(frameon=False, labelcolor=INK_2, loc="lower left")
    bottom.axhline(0, color=BASELINE, linewidth=1)
    bottom.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    bottom.set_ylabel("Drawdown", color=INK_2)
    top.set_title(title, color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
