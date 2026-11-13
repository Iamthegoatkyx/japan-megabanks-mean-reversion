"""Build ONE self-contained interactive file: outputs/dashboard.html (Plotly).

Usage:  python dashboard.py      then open outputs/dashboard.html in a browser.

Visualisation only: no new decisions, no new settings. Everything is either
read from the saved outputs/ files or recomputed with the SAME code and the
SAME cached data that produced the committed results (so the numbers match).
The out-of-sample daily series aren't saved, so they are recomputed here;
that reproduces the committed out-of-sample results, it doesn't re-decide anything.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

from backtester import config
from backtester.backtest import equal_weight
from backtester.data import load_prices
from backtester.experiments import common_dates, run_universe
from backtester.metrics import exit_breakdown, trade_list

OUT = Path("outputs")
SPLIT = pd.Timestamp(config.OUT_OF_SAMPLE_START)

# Same palette as the PNG charts (backtester/plots.py), plus three exit colours.
SURFACE, INK, INK_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
STRATEGY, BENCHMARK = "#2a78d6", "#eb6834"
EXIT_COLOURS = {"back to MA": "#1baf7a", "time stop": "#eda100", "stop-loss": "#e87ba4",
                "open": MUTED}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def style(fig: go.Figure, height: int) -> go.Figure:
    """Quiet, consistent look for every figure."""
    fig.update_layout(height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
                      font=dict(family=FONT, color=INK_2, size=12),
                      margin=dict(l=60, r=30, t=50, b=40), hovermode="x unified",
                      legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(showgrid=False, linecolor="#c3c2b7", zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


# ---------------------------------------------------------------- data

def load_runs():
    """Strategy and buy-and-hold backtests for both periods, per bank and portfolio."""
    runs = {}
    for period in ("in-sample", "out-of-sample"):
        strategies, benchmarks = run_universe(period)
        port_s, port_b = common_dates(strategies), common_dates(benchmarks)
        runs[period] = {
            "banks": {n: (strategies[n], benchmarks[n]) for n in strategies},
            "portfolio": (equal_weight({n: bt["net"] for n, bt in port_s.items()}),
                          equal_weight({n: bt["net"] for n, bt in port_b.items()})),
        }
    return runs


def growth_and_drawdown(net: pd.Series):
    """¥1 growth (starting at 1 on the period's first day) and drawdown from peak."""
    equity = (1 + net).cumprod()
    drawdown = equity / equity.cummax().clip(lower=1.0) - 1
    return equity, drawdown


def two_periods(series_by_period: dict[str, pd.Series]) -> pd.Series:
    """Join in-sample and out-of-sample with a gap (NaN) at the split, so the line
    breaks there. Each period starts at ¥1, exactly as in its own results.md."""
    a, b = series_by_period["in-sample"], series_by_period["out-of-sample"]
    gap = pd.Series([float("nan")], index=[a.index[-1] + pd.Timedelta(days=1)])
    return pd.concat([a, gap, b])


# ---------------------------------------------------------------- sections 1 + 2

def equity_figure(runs) -> go.Figure:
    names = ["Portfolio"] + list(runs["in-sample"]["banks"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32],
                        vertical_spacing=0.04)
    for k, name in enumerate(names):
        for which, label, colour in [(0, "Strategy", STRATEGY), (1, "Buy & hold", BENCHMARK)]:
            eq, dd = {}, {}
            for period in runs:
                net = (runs[period]["portfolio"][which] if name == "Portfolio"
                       else runs[period]["banks"][name][which]["net"])
                eq[period], dd[period] = growth_and_drawdown(net)
            visible = k == 0
            fig.add_trace(go.Scatter(x=two_periods(eq).index, y=two_periods(eq), name=label,
                                     line=dict(color=colour, width=2), visible=visible,
                                     legendgroup=label, connectgaps=False,
                                     hovertemplate="¥%{y:.2f}"), row=1, col=1)
            fig.add_trace(go.Scatter(x=two_periods(dd).index, y=two_periods(dd), name=label,
                                     line=dict(color=colour, width=1.5), visible=visible,
                                     legendgroup=label, showlegend=False, connectgaps=False,
                                     hovertemplate="%{y:.1%}"), row=2, col=1)

    per_group = 4
    buttons = []
    for k, name in enumerate(names):
        vis = [k * per_group <= i < (k + 1) * per_group for i in range(len(names) * per_group)]
        buttons.append(dict(label=name, method="update", args=[{"visible": vis}]))
    first_day = min(runs["in-sample"]["portfolio"][0].index[0],
                    *(s.index[0] for s, _ in runs["in-sample"]["banks"].values()))
    for row in (1, 2):
        fig.add_vrect(x0=first_day, x1=SPLIT, fillcolor="#f0efec", opacity=0.7,
                      line_width=0, layer="below", row=row, col=1)
        fig.add_vline(x=SPLIT, line=dict(color=MUTED, width=1, dash="dot"), row=row, col=1)
    fig.add_annotation(x=SPLIT, y=1, yref="paper", text="in-sample  ←  |  →  out-of-sample",
                       showarrow=False, xanchor="center", yanchor="bottom",
                       font=dict(color=MUTED, size=11))
    fig.update_yaxes(type="log", title_text="Growth of ¥1 (log)", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", title_text="Drawdown", row=2, col=1)
    fig.update_layout(updatemenus=[dict(buttons=buttons, x=1, xanchor="right", y=1.16,
                                        bgcolor="white", bordercolor=GRID)])
    return style(fig, 620)


# ---------------------------------------------------------------- section 3

def price_figure(runs) -> go.Figure:
    universe = config.UNIVERSES[config.MAIN_UNIVERSE]["tickers"]
    cost = config.UNIVERSES[config.MAIN_UNIVERSE]["cost_bps"]
    fig = go.Figure()
    per_bank = 3 + len(EXIT_COLOURS)
    for k, (ticker, name) in enumerate(universe.items()):
        prices = load_prices(ticker)
        ma = prices.rolling(config.MA_WINDOW).mean()
        visible = k == 0
        fig.add_trace(go.Scatter(x=prices.index, y=prices, name="Close",
                                 line=dict(color=INK, width=1.2), visible=visible))
        fig.add_trace(go.Scatter(x=ma.index, y=ma, name=f"{config.MA_WINDOW}-day MA",
                                 line=dict(color=STRATEGY, width=1.2), visible=visible))
        fig.add_trace(go.Scatter(x=ma.index, y=ma * (1 - config.ENTRY_BELOW_MA),
                                 name=f"{config.ENTRY_BELOW_MA:.0%} below MA (entry level)",
                                 line=dict(color=MUTED, width=1, dash="dash"), visible=visible))
        trades = pd.concat([trade_list(runs[p]["banks"][name][0], cost) for p in runs])
        for reason, colour in EXIT_COLOURS.items():
            t = trades[trades["exit_reason"] == reason]
            x = list(t["buy_date"]) + list(t["sell_date"])
            y = [prices.loc[d] for d in x]
            symbols = ["triangle-up"] * len(t) + ["triangle-down"] * len(t)
            info = [f"{'BUY' if i < len(t) else 'SELL'} · {reason}<br>"
                    f"{r.buy_date.date()} → {r.sell_date.date()}, {r.days_held} days, "
                    f"{r.net_return:+.1%}"
                    for i, r in enumerate(list(t.itertuples()) * 2)]
            fig.add_trace(go.Scatter(x=x, y=y, mode="markers", name=reason,
                                     marker=dict(color=colour, size=10, symbol=symbols,
                                                 line=dict(color="white", width=1.5)),
                                     hovertext=info, hoverinfo="text", visible=visible))
    buttons = []
    for k, name in enumerate(universe.values()):
        vis = [k * per_bank <= i < (k + 1) * per_bank for i in range(3 * per_bank)]
        buttons.append(dict(label=name, method="update", args=[{"visible": vis}]))
    fig.add_vline(x=SPLIT, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_layout(updatemenus=[dict(buttons=buttons, x=1, xanchor="right", y=1.24,
                                        bgcolor="white", bordercolor=GRID)],
                      hovermode="closest")
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06))
    fig.update_yaxes(type="log", title_text="Price (¥, adjusted, log)")
    style(fig, 580)
    fig.update_layout(hovermode="closest", margin=dict(t=90))
    return fig


# ---------------------------------------------------------------- section 4

def heatmap_figure() -> go.Figure:
    grid = pd.read_csv(OUT / "in-sample" / "parameter_grid.csv")
    table = grid.pivot(index="threshold", columns="window", values="sharpe_diff")
    trades = grid.pivot(index="threshold", columns="window", values="trades")
    limit = float(table.abs().max().max())
    x = [str(w) for w in table.columns]
    y = [f"{t:.0%}" for t in table.index]
    fig = go.Figure(go.Heatmap(
        z=table.to_numpy(), x=x, y=y, zmid=0, zmin=-limit, zmax=limit,
        colorscale=[[0, "#e34948"], [0.5, "#f0efec"], [1, STRATEGY]],
        text=table.round(2).to_numpy(), texttemplate="%{text:+.2f}",
        customdata=trades.to_numpy(),
        hovertemplate="window %{x}, entry %{y}<br>Sharpe minus buy & hold: %{z:+.3f}"
                      "<br>trades: %{customdata}<extra></extra>",
        colorbar=dict(title="Sharpe<br>difference", outlinewidth=0)))
    i = list(table.index).index(config.ENTRY_BELOW_MA)
    j = list(table.columns).index(config.MA_WINDOW)
    fig.add_shape(type="rect", x0=j - 0.5, x1=j + 0.5, y0=i - 0.5, y1=i + 0.5,
                  line=dict(color=INK, width=3))
    fig.update_xaxes(title_text="Moving-average window (trading days)", type="category")
    fig.update_yaxes(title_text="Entry: % below MA", type="category")
    style(fig, 460)
    fig.update_layout(hovermode="closest")
    return fig


# ---------------------------------------------------------------- section 5

def cost_figure() -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("In-sample", "Out-of-sample"),
                        shared_yaxes=True)
    cost = config.UNIVERSES[config.MAIN_UNIVERSE]["cost_bps"]
    for col, period in enumerate(("in-sample", "out-of-sample"), start=1):
        c = pd.read_csv(OUT / period / "cost_sensitivity.csv", index_col="cost_bps")
        for column, label, colour in [("strategy_sharpe", "Strategy", STRATEGY),
                                      ("buy_hold_sharpe", "Buy & hold", BENCHMARK)]:
            fig.add_trace(go.Scatter(x=c.index, y=c[column], name=label, mode="lines+markers",
                                     line=dict(color=colour, width=2), marker=dict(size=9),
                                     legendgroup=label, showlegend=col == 1,
                                     hovertemplate="%{x} bps: Sharpe %{y:.2f}"), row=1, col=col)
        fig.add_vline(x=cost, line=dict(color=MUTED, width=1, dash="dot"), row=1, col=col)
    fig.update_xaxes(title_text="Cost per side (bps)", tickvals=[0, 10, 15, 25, 50])
    fig.update_yaxes(title_text="Sharpe ratio", row=1, col=1)
    return style(fig, 400)


# ---------------------------------------------------------------- section 6

def exits_figure(runs) -> go.Figure:
    cost = config.UNIVERSES[config.MAIN_UNIVERSE]["cost_bps"]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Number of trades", "Average return per trade"))
    reasons = ["back to MA", "time stop", "stop-loss"]
    for period, pattern in (("in-sample", ""), ("out-of-sample", "/")):
        trades = pd.concat([trade_list(s, cost) for s, _ in runs[period]["banks"].values()])
        table = exit_breakdown(trades).reindex(reasons)
        colours = [EXIT_COLOURS[r] for r in reasons]
        common = dict(x=reasons, name=period, legendgroup=period,
                      marker=dict(color=colours, pattern=dict(shape=pattern, fgcolor="white")))
        fig.add_trace(go.Bar(y=table["trades"], text=table["trades"].astype(int),
                             hovertemplate="%{x}: %{y} trades", **common), row=1, col=1)
        fig.add_trace(go.Bar(y=table["avg_return"], text=[f"{v:+.1%}" for v in table["avg_return"]],
                             hovertemplate="%{x}: %{y:+.2%}", showlegend=False, **common),
                      row=1, col=2)
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(tickformat=".0%", row=1, col=2)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    style(fig, 420)
    fig.update_layout(hovermode="closest")
    return fig


# ---------------------------------------------------------------- section 7

def criteria_html() -> str:
    """Read the four criteria straight from the committed out-of-sample results.md."""
    text = (OUT / "out-of-sample" / "portfolio" / "results.md").read_text()
    rows = re.findall(r"^\| ([1-4]\. .+?) \| (.+?) \| (yes|no) \|$", text, flags=re.M)
    outcome = re.search(r"\*\*Mechanical outcome: (.+?)\*\*", text).group(1)
    body = "".join(
        f"<tr><td>{c}</td><td class='num'>{v}</td>"
        f"<td class='{'met' if m == 'yes' else 'miss'}'>{'✓ met' if m == 'yes' else '✗ not met'}</td></tr>"
        for c, v, m in rows)
    return (f"<table><thead><tr><th>Criterion (set before any data)</th><th>Value</th>"
            f"<th>Result</th></tr></thead><tbody>{body}</tbody></table>"
            f"<p class='outcome'>Mechanical outcome: <strong>{outcome}</strong></p>")


# ---------------------------------------------------------------- 3D surface (own file)

# Every metric here is a column saved by robustness.py in parameter_grid.csv.
SURFACE_METRICS = {
    "sharpe_diff": ("Sharpe minus buy & hold", "+.2f",
                    [[0, "#e34948"], [0.5, "#f0efec"], [1, "#3987e5"]]),
    "strategy_sharpe": ("Strategy Sharpe", ".2f", "Blues"),
    "strategy_cagr": ("Strategy CAGR", ".1%", "Blues"),
    "strategy_max_dd": ("Strategy max drawdown", ".1%", "Blues"),
    "trades": ("Number of trades", ".0f", "Blues"),
}


def surface_figure() -> go.Figure:
    """In-sample grid as a rotatable 3D surface; the dropdown picks the metric."""
    grid = pd.read_csv(OUT / "in-sample" / "parameter_grid.csv")
    thresholds = sorted(grid["threshold"].unique())
    windows = sorted(grid["window"].unique())
    x = [t * 100 for t in thresholds]                       # 3..10 (%)
    prereg = grid[(grid.threshold == config.ENTRY_BELOW_MA) & (grid.window == config.MA_WINDOW)].iloc[0]
    best = grid.loc[grid["sharpe_diff"].idxmax()]           # best by the test's own metric
    trades = grid.pivot(index="window", columns="threshold", values="trades").to_numpy()

    fig = go.Figure()
    traces_per_metric = []
    for k, (col, (label, fmt, scale)) in enumerate(SURFACE_METRICS.items()):
        z = grid.pivot(index="window", columns="threshold", values=col)   # rows = window (y)
        visible = k == 0
        floor = float(z.min().min())
        start = len(fig.data)
        surface = dict(z=z.to_numpy(), x=x, y=windows, colorscale=scale, opacity=0.85,
                       customdata=trades, name=label, visible=visible,
                       colorbar=dict(title=label, len=0.7, outlinewidth=0,
                                     tickformat=".0%" if "%" in fmt else ""),
                       hovertemplate=(f"entry %{{x:.0f}}% below MA, window %{{y}} days<br>"
                                      f"{label}: %{{z:{fmt}}}<br>trades: %{{customdata}}<extra></extra>"))
        if col == "sharpe_diff":
            limit = float(z.abs().max().max())
            surface.update(cmid=0, cmin=-limit, cmax=limit)
        fig.add_trace(go.Surface(**surface))
        for point, text, colour in [(prereg, "pre-registered", "white"),
                                    (best, "best in-sample (not chosen)", "#eda100")]:
            px_, py_, pz = point["threshold"] * 100, point["window"], point[col]
            fig.add_trace(go.Scatter3d(
                x=[px_, px_], y=[py_, py_], z=[floor, pz], mode="lines",
                line=dict(color=colour, width=4, dash="dot"), showlegend=False,
                hoverinfo="skip", visible=visible))
            # The label floats above the point so the surface can't hide it.
            lift = 0.15 * (float(z.max().max()) - floor)
            fig.add_trace(go.Scatter3d(
                x=[px_, px_], y=[py_, py_], z=[pz, pz + lift], mode="lines+text",
                text=["", text], textposition="top center",
                textfont=dict(color=colour, size=13), line=dict(color=colour, width=2),
                showlegend=False, hoverinfo="skip", visible=visible))
            fig.add_trace(go.Scatter3d(
                x=[px_], y=[py_], z=[pz], mode="markers",
                marker=dict(size=7, color=colour, line=dict(color="#0d0d0d", width=2)),
                name=text, visible=visible, showlegend=False,
                hovertemplate=(f"{text}<br>entry {px_:.0f}%, window {py_:.0f} days<br>"
                               f"{label}: {pz:{fmt}}<br>trades: {int(point['trades'])}<extra></extra>")))
        if col == "sharpe_diff":
            # See-through plane at 0: above it the setting beat buy-and-hold in-sample.
            fig.add_trace(go.Surface(
                z=[[0, 0], [0, 0]], x=[x[0], x[-1]], y=[windows[0], windows[-1]],
                colorscale=[[0, "white"], [1, "white"]], showscale=False, opacity=0.25,
                hoverinfo="skip", name="z = 0 (equal to buy & hold)", visible=visible))
        traces_per_metric.append(range(start, len(fig.data)))

    buttons = []
    for (col, (label, _, _)), idx in zip(SURFACE_METRICS.items(), traces_per_metric):
        vis = [i in idx for i in range(len(fig.data))]
        tickformat = ".0%" if "%" in SURFACE_METRICS[col][1] else ""
        buttons.append(dict(label=label, method="update",
                            args=[{"visible": vis}, {"scene.zaxis.title.text": label,
                                                     "scene.zaxis.tickformat": tickformat}]))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0d0d0d", height=720,
        font=dict(family=FONT, color="#c3c2b7"),
        title=dict(text="In-sample parameter surface: 42 combinations", x=0.02,
                   font=dict(size=18, color="#f0efec")),
        margin=dict(l=0, r=0, t=70, b=0),
        updatemenus=[dict(buttons=buttons, x=0.02, xanchor="left", y=0.94,
                          bgcolor="#1a1a19", bordercolor="#383835", font=dict(color="#f0efec"))],
        scene=dict(
            xaxis=dict(title="Entry: % below MA", ticksuffix="%", backgroundcolor="#1a1a19",
                       gridcolor="#383835"),
            yaxis=dict(title="MA window (days)", backgroundcolor="#1a1a19", gridcolor="#383835"),
            zaxis=dict(title="Sharpe minus buy & hold", backgroundcolor="#1a1a19",
                       gridcolor="#383835"),
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9))))
    return fig


def write_surface_file() -> Path:
    path = OUT / "parameter_surface_3d.html"
    surface_figure().write_html(path, include_plotlyjs=True, full_html=True,
                                config={"displaylogo": False, "responsive": True})
    # Give the page a proper title and a dark background behind the chart.
    html = path.read_text(encoding="utf-8")
    html = html.replace("<head>", "<head><title>Parameter Surface 3D</title>"
                        "<style>body{margin:0;background:#0d0d0d}</style>", 1)
    path.write_text(html, encoding="utf-8")
    return path


# ---------------------------------------------------------------- page

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Megabanks Mean Reversion</title>
<style>
  body {{ margin: 0; background: #f9f9f7; color: {ink}; font-family: {font}; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; }}
  h2 {{ font-size: 17px; margin: 0 0 4px; }}
  p.lede, p.note {{ color: {ink2}; margin: 0 0 16px; line-height: 1.5; }}
  p.note {{ font-size: 13px; }}
  section {{ background: {surface}; border: 1px solid rgba(11,11,11,0.10);
             border-radius: 10px; padding: 18px 18px 8px; margin: 18px 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid {grid}; }}
  th {{ color: {ink2}; font-weight: 600; }}
  td.num {{ font-variant-numeric: tabular-nums; }}
  td.met {{ color: #006300; font-weight: 600; }}
  td.miss {{ color: #b3261e; font-weight: 600; }}
  p.outcome {{ margin: 14px 0 10px; }}
</style>
<script>{plotlyjs}</script>
</head><body><main>
<h1>Do Japan's megabanks mean-revert?</h1>
<p class="lede">Preregistered dip-buying rule on MUFG, SMFG and Mizuho vs buy-and-hold, after
15 bps per side. Grey shading = in-sample (before 2018); the dotted line is the
2018 split. Visualisation only: every number comes from the committed results.</p>
{sections}
</main></body></html>"""


def section(title: str, note: str, body: str) -> str:
    return f"<section><h2>{title}</h2><p class='note'>{note}</p>{body}</section>"


def main() -> None:
    runs = load_runs()
    def html(fig):
        return fig.to_html(full_html=False, include_plotlyjs=False,
                           config={"displaylogo": False, "responsive": True})
    sections = [
        section("1–2. Growth of ¥1 and drawdown",
                "Use the menu to switch between the portfolio and each bank. Each period "
                "starts at ¥1, as in its results.md, so the line breaks at the split. Log scale.",
                html(equity_figure(runs))),
        section("3. Prices, moving average and every trade",
                "▲ buy, ▼ sell, coloured by why the trade ended. Drag on the chart or use the "
                "slider underneath to zoom into single trades; double-click to zoom out.",
                html(price_figure(runs))),
        section("4. In-sample parameter grid (42 combinations)",
                "Portfolio Sharpe minus buy-and-hold. Outlined: the preregistered rule. "
                "A diagnostic only; settings were never chosen from it. "
                "Rotatable 3D version: <a href='parameter_surface_3d.html'>parameter_surface_3d.html</a>.",
                html(heatmap_figure())),
        section("5. Cost sensitivity",
                "Portfolio Sharpe as trading costs rise. Dotted line: the preregistered 15 bps.",
                html(cost_figure())),
        section("6. Why trades ended (all three banks)",
                "Closed trades only. Solid bars: in-sample; striped bars: out-of-sample.",
                html(exits_figure(runs))),
        section("7. Preregistered success criteria (out-of-sample)",
                "Copied from outputs/out-of-sample/portfolio/results.md.", criteria_html()),
    ]
    page = PAGE.format(ink=INK, ink2=INK_2, surface=SURFACE, grid=GRID, font=FONT,
                       plotlyjs=get_plotlyjs(), sections="\n".join(sections))
    path = OUT / "dashboard.html"
    path.write_text(page, encoding="utf-8")
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB). Open it in any browser.")
    surface = write_surface_file()
    print(f"Wrote {surface} ({surface.stat().st_size / 1e6:.1f} MB).")


if __name__ == "__main__":
    main()
