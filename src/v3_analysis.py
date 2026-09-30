import numpy as np, pandas as pd, statsmodels.api as sm, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from config import ROOT, OUT
from analytics import metrics, french_factors
from stats import block_bootstrap_ir
O3 = ROOT / "output" / "v3"; FIG3 = O3 / "figures"; FIG3.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False}); NAVY, GREY, TEAL, RED = "#0B3D91", "#9AA5B1", "#2A9D8F", "#B23A48"
v3 = pd.read_parquet(O3 / "returns_v3.parquet"); v2 = pd.read_parquet(OUT / "returns_v2_betaneutral.parquet")
ff = french_factors(); rf = ff["RF"]; rf.index = rf.index.to_period("M")
def rf_for(idx): s = rf.reindex(idx.to_period("M")); s.index = idx; return s.ffill()
act = v3.net - v3.bench
m = metrics(v3.net, v3.bench, rf_for(v3.index)); (lo, med, hi), p = block_bootstrap_ir(act)
t_ir = act.mean() / act.std() * np.sqrt(len(act))
print(m.to_string()); print(f"\nIR {m['Information ratio']:.2f}, t = {t_ir:.2f}, 90% bootstrap CI [{lo:.2f}, {hi:.2f}], P(IR>0) = {p:.0%}")
# sub-periods
per = {"1990s (1990-99)": ("1990", "1999"), "2000s (2000-09)": ("2000", "2009"), "2010s (2010-19)": ("2010", "2019"), "2020-24": ("2020", "2024")}
sub = pd.DataFrame({k: metrics(v3.net.loc[a:b], v3.bench.loc[a:b], rf_for(v3.net.loc[a:b].index))[["Excess return", "Tracking error", "Information ratio", "Sharpe", "Benchmark Sharpe", "Max drawdown", "Benchmark max drawdown"]] for k, (a, b) in per.items()}).T
print("\n", sub.round(3).to_string())
# overlap with v2 (survivorship check)
ov = v3.loc["2011-02":"2024-12"]; ov2 = v2.loc["2011-02":"2024-12"]
cmp = pd.DataFrame({"v2 (current constituents)": metrics(ov2.net, ov2.bench, rf_for(ov2.index)), "v3 (CRSP/Compustat, point-in-time)": metrics(ov.net, ov.bench, rf_for(ov.index))}).T[["Annualised return", "Benchmark return", "Excess return", "Tracking error", "Information ratio", "Sharpe", "Beta"]]
print("\nOverlap Feb 2011-Dec 2024:\n", cmp.round(3).to_string()); print("corr of active returns v2 vs v3:", round((ov.net - ov.bench).corr(ov2.net - ov2.bench), 2))
# FF regression
f = ff.copy(); f.index = f.index.to_period("M"); X = f.reindex(act.index.to_period("M"))[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]]; X.index = act.index
mod = sm.OLS(act, sm.add_constant(X), missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 3})
reg = pd.DataFrame({"coef": mod.params, "t": mod.tvalues}); reg.loc["const", "coef"] *= 12; reg = reg.rename(index={"const": "Alpha (ann.)"}); print(f"\nFF5+MOM R2 {mod.rsquared:.2f}\n", reg.round(3).to_string())
cal = pd.DataFrame({"Strategy": v3.net, "Benchmark": v3.bench}); cal = (1 + cal).groupby(cal.index.year).prod() - 1; cal["Active"] = cal.Strategy - cal.Benchmark
stress = {"1990 recession (Jul-Oct 1990)": ("1990-07", "1990-10"), "LTCM (Aug-Sep 1998)": ("1998-08", "1998-09"), "Dot-com bust (Mar 2000-Sep 2002)": ("2000-03", "2002-09"), "GFC (Oct 2007-Feb 2009)": ("2007-10", "2009-02"),
          "COVID (Feb-Mar 2020)": ("2020-02", "2020-03"), "2022": ("2022-01", "2022-12")}
st = pd.DataFrame({k: {"Strategy": (1 + v3.net.loc[a:b]).prod() - 1, "Benchmark": (1 + v3.bench.loc[a:b]).prod() - 1} for k, (a, b) in stress.items()}).T; st["Relative"] = st.Strategy - st.Benchmark
print("\n", st.round(3).to_string())
sleeves = pd.DataFrame({f: metrics(r.net, r.bench, rf_for(r.index))[["Excess return", "Tracking error", "Information ratio"]] for f, r in {k: pd.read_parquet(O3 / f"returns_v3_{k}.parquet") for k in ["value", "momentum", "quality"]}.items()}).T
for n, o in [("metrics", m), ("subperiods", sub), ("v2_v3_overlap", cmp), ("ff_regression", reg), ("calendar", cal), ("stress", st), ("sleeves", sleeves)]: o.to_csv(O3 / f"{n}.csv")
pd.Series({"ir": m["Information ratio"], "t": t_ir, "ci5": lo, "ci95": hi, "p_pos": p, "r2": mod.rsquared, "act_corr_v2_v3": (ov.net - ov.bench).corr(ov2.net - ov2.bench)}).to_csv(O3 / "summary.csv")
# charts
fig, ax = plt.subplots(figsize=(9, 4.2)); rel = (1 + v3.net).cumprod() / (1 + v3.bench).cumprod(); rel.plot(ax=ax, color=NAVY, lw=2.2, label="v3: CRSP/Compustat, point-in-time S&P 500, 1990-2024")
rel2 = (1 + v2.net).cumprod() / (1 + v2.bench).cumprod(); (rel2 * rel.loc[:"2011-02"].iloc[-1]).plot(ax=ax, color=GREY, lw=1.6, label="v2: current constituents, 2011-2026 (rescaled to join)")
for a, b in [("2000-03", "2002-09"), ("2007-10", "2009-02"), ("2020-02", "2020-03"), ("2022-01", "2022-12")]: ax.axvspan(pd.Timestamp(a), pd.Timestamp(b) + pd.offsets.MonthEnd(0), color=NAVY, alpha=.07)
ax.axhline(1, color="k", lw=.6); ax.set_title("Relative wealth vs. cap-weighted benchmark (shaded: dot-com bust, GFC, COVID, 2022)"); ax.legend(frameon=False); ax.set_xlabel("")
fig.tight_layout(); fig.savefig(FIG3 / "relative_wealth.png", dpi=180); plt.close(fig)
fig, ax = plt.subplots(figsize=(9, 3.6)); ax.bar(cal.index.astype(str), cal.Active * 100, color=[NAVY if v >= 0 else RED for v in cal.Active]); ax.axhline(0, color="k", lw=.6); ax.set_ylabel("%"); ax.set_title("Calendar-year active return, 1990-2024"); plt.setp(ax.get_xticklabels(), rotation=90, fontsize=8)
fig.tight_layout(); fig.savefig(FIG3 / "calendar_active.png", dpi=180); plt.close(fig)
fig, ax = plt.subplots(figsize=(9, 3.4)); ir = act.rolling(60).mean() / act.rolling(60).std() * 12 ** .5; ir.plot(ax=ax, color=NAVY, lw=2); ax.axhline(0, color="k", lw=.6); ax.axhline(m["Information ratio"], color=GREY, lw=1, ls="--"); ax.set_title("Rolling 5-year information ratio (dashed: full-sample 0.38)"); ax.set_xlabel("")
fig.tight_layout(); fig.savefig(FIG3 / "rolling_ir.png", dpi=180); plt.close(fig)
fig, ax = plt.subplots(figsize=(9, 4)); 
for k, c in [("value", RED), ("momentum", TEAL), ("quality", "#E9C46A")]:
    r = pd.read_parquet(O3 / f"returns_v3_{k}.parquet"); ((1 + r.net).cumprod() / (1 + r.bench).cumprod()).plot(ax=ax, color=c, lw=1.6, label=k.capitalize())
rel.plot(ax=ax, color="k", lw=2.2, label="Composite"); ax.axhline(1, color="k", lw=.6); ax.set_title("Single-factor sleeves vs. composite, relative wealth"); ax.legend(frameon=False, ncol=4); ax.set_xlabel("")
fig.tight_layout(); fig.savefig(FIG3 / "sleeves.png", dpi=180); plt.close(fig); print("\ncharts done")
