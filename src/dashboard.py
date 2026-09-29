"""Self-contained interactive Plotly dashboard (single HTML file)."""
import pandas as pd, numpy as np, plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import OUT, FACTORS

v2 = pd.read_parquet(OUT / "returns_v2_betaneutral.parquet"); v1 = pd.read_parquet(OUT / "returns_multifactor.parquet")
expo = pd.read_csv(OUT / "exposures_v2_betaneutral.csv", index_col=0, parse_dates=True)
cal = pd.read_csv(OUT / "calendar_v2_betaneutral.csv", index_col=0)
sl = {f: pd.read_parquet(OUT / f"returns_{f}.parquet") for f in FACTORS}
navy, grey = "#0B3D91", "#9AA5B1"
cum = lambda r: (1 + r).cumprod()

fig = make_subplots(rows=3, cols=2, vertical_spacing=0.09, horizontal_spacing=0.07,
    subplot_titles=("Growth of $1 (v2 net vs. benchmark)", "Relative wealth: v1 vs. v2", "Drawdown",
                    "Calendar-year active return (v2)", "Rolling 3-year information ratio (v2)", "Active factor exposure (v2)"))
fig.add_trace(go.Scatter(x=v2.index, y=cum(v2.net), name="v2 net", line=dict(color=navy, width=2)), 1, 1)
fig.add_trace(go.Scatter(x=v2.index, y=cum(v2.bench), name="Benchmark", line=dict(color=grey, width=2)), 1, 1)
fig.add_trace(go.Scatter(x=v1.index, y=cum(v1.net) / cum(v1.bench), name="v1 four-factor tilt", line=dict(color=grey, width=2)), 1, 2)
fig.add_trace(go.Scatter(x=v2.index, y=cum(v2.net) / cum(v2.bench), name="v2 beta-neutral", line=dict(color=navy, width=2)), 1, 2)
dd = cum(v2.net) / cum(v2.net).cummax() - 1; ddb = cum(v2.bench) / cum(v2.bench).cummax() - 1
fig.add_trace(go.Scatter(x=dd.index, y=dd, fill="tozeroy", name="v2 drawdown", line=dict(color=navy, width=1)), 2, 1)
fig.add_trace(go.Scatter(x=ddb.index, y=ddb, name="Benchmark drawdown", line=dict(color=grey, width=1.5)), 2, 1)
fig.add_trace(go.Bar(x=cal.index.astype(str), y=cal.Active, name="Active return", marker_color=[navy if v >= 0 else "#B23A48" for v in cal.Active]), 2, 2)
act = v2.net - v2.bench; ir = act.rolling(36).mean() / act.rolling(36).std() * 12 ** .5
fig.add_trace(go.Scatter(x=ir.index, y=ir, name="Rolling IR", line=dict(color=navy, width=2)), 3, 1)
for f, c in zip(FACTORS, ["#0B3D91", "#2A9D8F", "#E9C46A", "#B23A48"]):
    fig.add_trace(go.Scatter(x=expo.index, y=expo[f], name=f.capitalize(), line=dict(color=c, width=1.5)), 3, 2)
for r, c in [(1, 2), (3, 1)]: fig.add_hline(y=1 if r == 1 else 0, line=dict(color="black", width=0.6), row=r, col=c)
fig.update_yaxes(tickformat=".0%", row=2, col=1); fig.update_yaxes(tickformat=".0%", row=2, col=2)
fig.update_layout(height=1050, template="plotly_white", title=dict(text="Multi-Factor US Large Cap Strategy - Research Dashboard (Feb 2011 - Sep 2026)", x=0.02),
                  legend=dict(orientation="h", y=-0.04), margin=dict(l=40, r=20, t=70, b=60), hovermode="x unified")
m = pd.read_csv(OUT / "metrics_v2_betaneutral.csv", index_col=0).iloc[:, 0]
kpis = f"Excess return {m['Excess return']:+.1%} | IR {m['Information ratio']:.2f} | TE {m['Tracking error']:.1%} | Sharpe {m['Sharpe']:.2f} vs {m['Benchmark Sharpe']:.2f} | Beta {m['Beta']:.2f} | Max DD {m['Max drawdown']:.1%} vs {m['Benchmark max drawdown']:.1%}"
html = fig.to_html(include_plotlyjs=True, full_html=True)
html = html.replace("<body>", f'<body style="font-family:Helvetica,Arial,sans-serif;margin:16px"><div style="color:#0B3D91;font-weight:600;margin:4px 0 8px 8px">{kpis}</div>'
                    '<div style="color:#5B6770;font-size:13px;margin:0 0 8px 8px">Hypothetical backtest, net of 10 bps per dollar traded. Universe: current S&amp;P 500 constituents (survivorship bias affects both series). Hugo Hoenn, 2026.</div>')
(OUT / "dashboard.html").write_text(html); print("dashboard", len(html) // 1024, "KB")
