"""
charts.py - Plotly figure builders sharing one visual system.

Thin marks, hairline grids, a fixed pastel categorical order,
status colours reserved for good/bad meaning, and one y-axis per chart.
"""
import calendar
from datetime import date, datetime

import plotly.graph_objects as go
import plotly.io as pio

# --- Tokens (keep in sync with the CSS tokens in app.py) ---
FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
SURFACE = "#fcfcfe"
INK = "#2b2d42"
INK_2 = "#565a6e"
MUTED = "#80849a"
GRID = "#eceef4"
BASELINE = "#c9ccd8"

# Categorical slots, assigned in this order and never cycled. Soft pastels that stay
# distinct from one another (blue, peach, mint, butter, pink, sage, lavender, coral).
SERIES = ["#7fa6e3", "#f2a07b", "#6fc4a1", "#f0c75e", "#eb9cc0", "#9cc47a", "#a99be3", "#e98b8b"]
OTHER = "#cfd1da"
BLUE_RAMP = {250: "#c3d5f3", 350: "#9fbbea", 450: "#7fa6e3", 550: "#5b7fcf", 650: "#42609f"}

GOOD = "#5fb88a"
CRITICAL = "#e07a78"
POSITIVE = "#7fa6e3"  # diverging pair: blue (money in / owed to you) ...
NEGATIVE = "#e98b8b"  # ... red (money out / you owe)

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}

# Dark-mode stand-ins for the neutral tokens above (keep in sync with TOKENS in app.py).
# Series and status colours are pastel already and read well on both backgrounds.
DARK_SWAPS = {
    SURFACE: "#232636",
    INK: "#e3e5f0",
    INK_2: "#b3b7ca",
    MUTED: "#8c91a8",
    GRID: "#2e3244",
    BASELINE: "#4a4f66",
    OTHER: "#565b72",
    "#e0e2ea": "#3a3e52",  # hover-label border
}


def money(v, curr, decimals=0):
    sign = "-" if v < 0 else ""
    return f"{sign}{curr}{abs(v):,.{decimals}f}"


def _layout(fig, height, curr=None, legend=True, hovermode="closest"):
    fig.update_layout(
        height=height,
        margin=dict(t=36 if legend else 12, b=8, l=8, r=12),
        font=dict(family=FONT, size=12, color=INK_2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode=hovermode,
        hoverlabel=dict(bgcolor=SURFACE, bordercolor="#e0e2ea", font=dict(family=FONT, size=12, color=INK)),
        showlegend=legend,
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom",
                    font=dict(size=12, color=INK_2), bgcolor="rgba(0,0,0,0)", itemclick=False,
                    itemdoubleclick=False),
        bargap=0.35,
        bargroupgap=0.12,
    )
    fig.update_xaxes(showgrid=False, linecolor=BASELINE, linewidth=1, ticks="", tickfont=dict(color=MUTED),
                     zeroline=False, fixedrange=True)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, zeroline=False, linecolor=BASELINE, ticks="",
                     tickfont=dict(color=MUTED), fixedrange=True)
    if curr is not None:
        fig.update_yaxes(tickprefix=curr, tickformat="~s")
    return fig


def _month_label(ym):
    """Axis label for a YYYY-MM month; the current, unfinished month is flagged."""
    try:
        label = datetime.strptime(ym, "%Y-%m").strftime("%b %Y")
    except ValueError:
        return ym
    if ym == date.today().strftime("%Y-%m"):
        label += "<br><span style='font-size:10px'>so far</span>"
    return label


# ---------------------------------------------------------------------------
# Overview: cumulative spend vs budget pace
# ---------------------------------------------------------------------------
def spending_pace(daily_rows, month, budget, curr, projected=None):
    y, m = map(int, month.split("-"))
    days_in_month = calendar.monthrange(y, m)[1]
    today = date.today()
    is_current = (today.year, today.month) == (y, m)
    last_day = today.day if is_current else days_in_month

    by_day = {int(r["date"][8:10]): float(r["total"]) for r in daily_rows}
    days = list(range(1, last_day + 1))
    cumulative, running = [], 0.0
    for d in days:
        running += by_day.get(d, 0.0)
        cumulative.append(round(running, 2))

    fig = go.Figure()
    if budget and budget > 0:
        fig.add_trace(go.Scatter(
            x=[0, days_in_month], y=[0, budget], mode="lines", name="Budget pace",
            line=dict(color=BASELINE, width=2),
            hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=days, y=cumulative, mode="lines", name="Spent so far",
        line=dict(color=SERIES[0], width=2, shape="hv"),
        fill="tozeroy", fillcolor="rgba(127,166,227,0.14)",
        customdata=[by_day.get(d, 0.0) for d in days],
        hovertemplate=(f"Day %{{x}}<br>Spent to date <b>{curr}%{{y:,.0f}}</b>"
                       f"<br>That day {curr}%{{customdata:,.0f}}<extra></extra>"),
    ))
    if is_current and projected and last_day < days_in_month and cumulative:
        fig.add_trace(go.Scatter(
            x=[last_day, days_in_month], y=[cumulative[-1], projected], mode="lines", name="Projected",
            line=dict(color=SERIES[0], width=2, dash="dot"),
            hovertemplate=f"Projected month-end <b>{curr}%{{y:,.0f}}</b><extra></extra>",
        ))

    # Selective direct labels: today's total and the budget line's end.
    if cumulative:
        fig.add_annotation(x=days[-1], y=cumulative[-1], text=f"<b>{money(cumulative[-1], curr)}</b>",
                           showarrow=False, xanchor="right", yanchor="bottom", yshift=6,
                           font=dict(color=INK, size=12))
        fig.add_trace(go.Scatter(x=[days[-1]], y=[cumulative[-1]], mode="markers", showlegend=False,
                                 marker=dict(size=8, color=SERIES[0], line=dict(color=SURFACE, width=2)),
                                 hoverinfo="skip"))
    if budget and budget > 0:
        fig.add_annotation(x=days_in_month, y=budget, text=f"Budget {money(budget, curr)}", showarrow=False,
                           xanchor="right", yanchor="bottom", yshift=4, font=dict(color=MUTED, size=11))

    _layout(fig, 280, curr, hovermode="x")
    fig.update_xaxes(range=[0.5, days_in_month + 0.5], tickvals=[1, 8, 15, 22, days_in_month],
                     ticktext=[f"{calendar.month_abbr[m]} {d}" for d in [1, 8, 15, 22, days_in_month]])
    top = max([budget or 0, projected or 0] + cumulative + [1])
    fig.update_yaxes(range=[0, top * 1.12])
    return fig


# ---------------------------------------------------------------------------
# Category spend vs limit (bullet bars)
# ---------------------------------------------------------------------------
def category_vs_budget(cat_status, curr, max_rows=8):
    rows = [c for c in cat_status if c["spent"] > 0 or c["has_budget"]][:max_rows]
    rows = list(reversed(rows))  # largest at the top
    names = [c["category"] for c in rows]
    spent = [c["spent"] for c in rows]
    over = [c["has_budget"] and c["spent"] > c["budget"] for c in rows]
    colors = [CRITICAL if o else SERIES[0] for o in over]
    hover = []
    for c in rows:
        if c["has_budget"]:
            left = c["budget"] - c["spent"]
            status = f"{money(abs(left), curr)} {'over' if left < 0 else 'left'}"
            hover.append(f"<b>{c['category']}</b><br>Spent {money(c['spent'], curr)} of {money(c['budget'], curr)}<br>{status}")
        else:
            hover.append(f"<b>{c['category']}</b><br>Spent {money(c['spent'], curr)}<br>No limit set")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names, x=spent, orientation="h", name="Spent", marker=dict(color=colors, cornerradius=4),
        width=0.55, hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
    ))
    lim_y = [c["category"] for c in rows if c["has_budget"]]
    lim_x = [c["budget"] for c in rows if c["has_budget"]]
    if lim_x:
        fig.add_trace(go.Scatter(
            y=lim_y, x=lim_x, mode="markers", name="Limit",
            marker=dict(symbol="line-ns", size=22, line=dict(color=INK, width=2)),
            hovertemplate=f"Limit {curr}%{{x:,.0f}}<extra></extra>",
        ))
    # Value labels sit past whichever is further right (bar end or limit tick) so they never collide.
    fig.add_trace(go.Scatter(
        y=names, x=[max(c["spent"], c["budget"] if c["has_budget"] else 0) for c in rows], mode="text",
        text=["\u2002" + money(v, curr) for v in spent], textposition="middle right", showlegend=False, hoverinfo="skip",
        textfont=dict(color=INK_2, size=11), cliponaxis=False,
    ))
    _layout(fig, max(180, 40 * len(rows) + 50), legend=bool(lim_x))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, tickprefix=curr, tickformat="~s", showline=False)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK_2))
    xmax = max(spent + lim_x + [1])
    fig.update_xaxes(range=[0, xmax * 1.25])
    return fig


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def income_vs_expenses(merged, curr):
    """merged: DataFrame with month, Income, Expenses (sorted)."""
    labels = [_month_label(m) for m in merged["month"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=merged["Income"], name="Income", marker=dict(color=SERIES[0], cornerradius=4),
                         hovertemplate=f"Income <b>{curr}%{{y:,.0f}}</b><extra></extra>"))
    fig.add_trace(go.Bar(x=labels, y=merged["Expenses"], name="Expenses", marker=dict(color=SERIES[1], cornerradius=4),
                         hovertemplate=f"Expenses <b>{curr}%{{y:,.0f}}</b><extra></extra>"))
    _layout(fig, 300, curr, hovermode="x unified")
    fig.update_layout(barmode="group")
    return fig


def net_savings(merged, curr):
    labels = [_month_label(m) for m in merged["month"]]
    net = (merged["Income"] - merged["Expenses"]).round(2).tolist()
    rate = [((n / i) * 100 if i else 0) for n, i in zip(net, merged["Income"])]
    fig = go.Figure(go.Bar(
        x=labels, y=net, marker=dict(color=[POSITIVE if v >= 0 else NEGATIVE for v in net], cornerradius=4),
        customdata=rate, name="Net savings",
        hovertemplate=f"Net <b>{curr}%{{y:,.0f}}</b><br>Savings rate %{{customdata:.0f}}%<extra></extra>",
        text=[money(v, curr) if i == len(net) - 1 else "" for i, v in enumerate(net)],
        textposition="outside", cliponaxis=False, textfont=dict(color=INK, size=11),
    ))
    _layout(fig, 300, curr, legend=False)
    fig.add_hline(y=0, line=dict(color=BASELINE, width=1))
    lo, hi = min(net + [0]), max(net + [0])
    pad = (hi - lo) * 0.18 or 1
    fig.update_yaxes(range=[lo - (pad if lo < 0 else 0), hi + pad])
    return fig


def category_trend(rows, curr, top_n=5):
    """Stacked monthly spend by category; the tail folds into Other."""
    months = sorted({r["month"] for r in rows})
    totals = {}
    for r in rows:
        totals[r["category"]] = totals.get(r["category"], 0) + r["total"]
    ranked = sorted(totals, key=totals.get, reverse=True)
    top = ranked[:top_n]
    series = {c: {m: 0.0 for m in months} for c in top + ["Other"]}
    for r in rows:
        key = r["category"] if r["category"] in top else "Other"
        series[key][r["month"]] += r["total"]
    if not any(series["Other"].values()):
        series.pop("Other")

    labels = [_month_label(m) for m in months]
    fig = go.Figure()
    for i, (cat, vals) in enumerate(series.items()):
        color = OTHER if cat == "Other" else SERIES[i]
        fig.add_trace(go.Bar(
            x=labels, y=[vals[m] for m in months], name=cat,
            marker=dict(color=color, line=dict(color=SURFACE, width=1.5)),
            hovertemplate=f"{cat} <b>{curr}%{{y:,.0f}}</b><extra></extra>",
        ))
    _layout(fig, 320, curr, hovermode="x unified")
    fig.update_layout(barmode="stack", bargap=0.45, legend_traceorder="normal")
    return fig


# ---------------------------------------------------------------------------
# Shared money
# ---------------------------------------------------------------------------
def net_balances(bal_details, curr):
    rows = sorted(bal_details, key=lambda b: b["balance"])
    names = [b["name"] for b in rows]
    vals = [b["balance"] for b in rows]
    colors = [POSITIVE if v > 0.01 else (NEGATIVE if v < -0.01 else OTHER) for v in vals]
    hover = [f"<b>{b['name']}</b><br>" + (
        f"Gets back {money(b['balance'], curr, 2)}" if b["balance"] > 0.01 else
        f"Owes {money(-b['balance'], curr, 2)}" if b["balance"] < -0.01 else "Settled up") for b in rows]
    fig = go.Figure(go.Bar(
        y=names, x=vals, orientation="h", marker=dict(color=colors, cornerradius=4), width=0.55,
        hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        text=[money(v, curr) for v in vals], textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=11),
    ))
    _layout(fig, max(160, 44 * len(rows) + 40), legend=False)
    m = max([abs(v) for v in vals] + [1]) * 1.3
    fig.update_xaxes(range=[-m, m], showgrid=True, gridcolor=GRID, tickprefix=curr, tickformat="~s",
                     showline=False, zeroline=True, zerolinecolor=BASELINE, zerolinewidth=1)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK_2))
    return fig


def debt_flow(plan, curr):
    """Sankey of suggested payments (people who pay on the left, people paid on the right)."""
    pairs = {}
    for t in plan:
        key = (t["from_name"], t["to_name"])
        pairs[key] = pairs.get(key, 0.0) + t["amount"]
    payers = sorted({f for f, _ in pairs})
    payees = sorted({t for _, t in pairs})
    # A person can appear on both sides (pays in one circle, is paid in another).
    nodes = [f"{p} " for p in payers] + payees
    idx_src = {p: i for i, p in enumerate(payers)}
    idx_dst = {p: len(payers) + i for i, p in enumerate(payees)}
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(pad=18, thickness=12, line=dict(width=0), label=nodes,
                  color=[NEGATIVE] * len(payers) + [POSITIVE] * len(payees),
                  hovertemplate=f"%{{label}}<br>{curr}%{{value:,.2f}}<extra></extra>"),
        link=dict(source=[idx_src[f] for f, _ in pairs], target=[idx_dst[t] for _, t in pairs],
                  value=[round(v, 2) for v in pairs.values()], color="rgba(127,166,227,0.22)",
                  customdata=[f"{f} pays {t} {money(v, curr, 2)}" for (f, t), v in pairs.items()],
                  hovertemplate="%{customdata}<extra></extra>"),
    ))
    fig.update_layout(height=max(200, 52 * max(len(payers), len(payees)) + 40), margin=dict(t=8, b=8, l=8, r=8),
                      font=dict(family=FONT, size=12, color=INK), paper_bgcolor="rgba(0,0,0,0)",
                      hoverlabel=dict(bgcolor=SURFACE, bordercolor="#e0e2ea", font=dict(family=FONT, color=INK)))
    return fig


AGE_BUCKETS = [("0–7 days", 0, 7), ("8–14 days", 8, 14), ("15–30 days", 15, 30), ("30+ days", 31, 10 ** 6)]


def outstanding_by_age(queue, curr):
    """Ordinal ramp: the older the debt, the darker the bar."""
    sums = [0.0] * len(AGE_BUCKETS)
    counts = [0] * len(AGE_BUCKETS)
    for st in queue:
        for i, (_, lo, hi) in enumerate(AGE_BUCKETS):
            if lo <= st["days_outstanding"] <= hi:
                sums[i] += st["total_owed"]
                counts[i] += 1
    ramp = [BLUE_RAMP[250], BLUE_RAMP[350], BLUE_RAMP[450], BLUE_RAMP[650]]
    fig = go.Figure(go.Bar(
        x=[b[0] for b in AGE_BUCKETS], y=sums, marker=dict(color=ramp, cornerradius=4), width=0.5,
        customdata=counts,
        hovertemplate=f"%{{x}}<br><b>{curr}%{{y:,.0f}}</b> across %{{customdata}} people<extra></extra>",
        text=[money(v, curr) if v else "" for v in sums], textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=11),
    ))
    _layout(fig, 240, curr, legend=False)
    fig.update_yaxes(range=[0, max(sums + [1]) * 1.25])
    return fig


def to_dark(fig):
    """Return a copy of a figure with its neutral (ink, grid, surface) colours swapped for dark mode."""
    spec = fig.to_json()
    for light, dark in DARK_SWAPS.items():
        spec = spec.replace(f'"{light}"', f'"{dark}"').replace(f'"{light.upper()}"', f'"{dark}"')
    return pio.from_json(spec)
