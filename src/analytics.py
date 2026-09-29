"""Performance analytics, factor attribution, and charts."""
import io, zipfile, requests, numpy as np, pandas as pd, statsmodels.api as sm
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config import OUT, FIG, FACTORS, RAW, PROC

FF5 = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOM = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"

def _french(url, skip):
    z = zipfile.ZipFile(io.BytesIO(requests.get(url, timeout=60).content))
    txt = z.read(z.namelist()[0]).decode("latin1")
    lines = txt.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip()[:6].isdigit() and len(l.strip()[:6]) == 6)
    rows = []
    for l in lines[start:]:
        parts = [p.strip() for p in l.split(",")]
        if len(parts[0]) != 6 or not parts[0].isdigit(): break
        rows.append(parts)
    df = pd.DataFrame(rows).set_index(0).astype(float) / 100
    hdr = [h.strip() for h in lines[start - 1].split(",")[1:]]
    df.columns = hdr[:df.shape[1]]
    df.index = pd.to_datetime(df.index, format="%Y%m") + pd.offsets.MonthEnd(0)
    return df

def french_factors():
    ff = _french(FF5, 0); mom = _french(MOM, 0)
    mom.columns = ["MOM"]
    return ff.join(mom, how="inner")

def metrics(r, b, rf=None):
    n = len(r); ann = lambda x: (1 + x).prod() ** (12 / n) - 1
    act = r - b
    cum = (1 + r).cumprod(); dd = cum / cum.cummax() - 1
    cumb = (1 + b).cumprod(); ddb = cumb / cumb.cummax() - 1
    ex = r - (rf if rf is not None else 0); exb = b - (rf if rf is not None else 0)
    m = {
        "Annualised return": ann(r), "Benchmark return": ann(b), "Excess return": ann(r) - ann(b),
        "Volatility": r.std() * 12 ** .5, "Benchmark volatility": b.std() * 12 ** .5,
        "Sharpe": ex.mean() / ex.std() * 12 ** .5, "Benchmark Sharpe": exb.mean() / exb.std() * 12 ** .5,
        "Tracking error": act.std() * 12 ** .5,
        "Information ratio": act.mean() / act.std() * 12 ** .5,
        "Max drawdown": dd.min(), "Benchmark max drawdown": ddb.min(),
        "Beta": np.cov(r, b)[0, 1] / b.var(),
        "Hit rate (months)": (act > 0).mean(),
    }
    return pd.Series(m)

def stress(r, b, windows):
    rows = {}
    for name, (s, e) in windows.items():
        rs, bs = r.loc[s:e], b.loc[s:e]
        rows[name] = {"Strategy": (1 + rs).prod() - 1, "Benchmark": (1 + bs).prod() - 1}
    df = pd.DataFrame(rows).T; df["Relative"] = df["Strategy"] - df["Benchmark"]
    return df

def calendar(r, b):
    y = lambda x: (1 + x).groupby(x.index.year).prod() - 1
    df = pd.DataFrame({"Strategy": y(r), "Benchmark": y(b)}); df["Active"] = df.Strategy - df.Benchmark
    return df

def ff_regression(act):
    ff = french_factors().reindex(act.index).dropna()
    y = act.reindex(ff.index)
    X = sm.add_constant(ff[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]])
    m = sm.OLS(y, X).fit()
    out = pd.DataFrame({"coef": m.params, "t": m.tvalues})
    out.loc["const", "coef"] *= 12          # annualise alpha
    return out.rename(index={"const": "Alpha (ann.)"}), m.rsquared

def exposures(W, factors_panels):
    """Active factor exposure (portfolio-weighted z minus benchmark-weighted z) over time."""
    mktcap = pd.read_parquet(PROC / "mktcap.parquet"); invest = pd.read_parquet(PROC / "invest.parquet")
    rows = {}
    for t, w in W.iterrows():
        b = mktcap.loc[t].where(invest.loc[t]).fillna(0); b = b / b.sum()
        rows[t] = {f: ((w * factors_panels[f].loc[t].fillna(0)).sum() - (b * factors_panels[f].loc[t].fillna(0)).sum())
                   for f in FACTORS}
    return pd.DataFrame(rows).T

# ---------------- charts ----------------
def charts(res, calendar_df, expo, sleeves, dd_window=36):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    c_s, c_b = "#0B3D91", "#9AA5B1"
    # 1 growth of $1
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ((1 + res.net).cumprod()).plot(ax=ax, color=c_s, lw=2, label="Multi-factor (net)")
    ((1 + res.bench).cumprod()).plot(ax=ax, color=c_b, lw=2, label="Cap-weighted benchmark")
    ax.set_title("Growth of $1"); ax.legend(frameon=False); ax.set_xlabel("")
    fig.tight_layout(); fig.savefig(FIG / "growth.png", dpi=180); plt.close(fig)
    # 2 relative performance + drawdown
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    rel = (1 + res.net).cumprod() / (1 + res.bench).cumprod()
    rel.plot(ax=a1, color=c_s, lw=2); a1.set_title("Strategy / Benchmark (relative wealth)"); a1.axhline(1, color="k", lw=.6)
    cum = (1 + res.net).cumprod(); dd = cum / cum.cummax() - 1
    cumb = (1 + res.bench).cumprod(); ddb = cumb / cumb.cummax() - 1
    a2.fill_between(dd.index, dd, 0, color=c_s, alpha=.5, label="Strategy"); a2.plot(ddb.index, ddb, color=c_b, lw=1.2, label="Benchmark")
    a2.set_title("Drawdown"); a2.legend(frameon=False, loc="lower left"); a2.set_xlabel("")
    fig.tight_layout(); fig.savefig(FIG / "relative_drawdown.png", dpi=180); plt.close(fig)
    # 3 calendar active returns
    fig, ax = plt.subplots(figsize=(9, 3.6))
    cols = [c_s if v >= 0 else "#B23A48" for v in calendar_df.Active]
    ax.bar(calendar_df.index.astype(str), calendar_df.Active * 100, color=cols)
    ax.axhline(0, color="k", lw=.6); ax.set_ylabel("%"); ax.set_title("Calendar-year active return vs. benchmark")
    fig.tight_layout(); fig.savefig(FIG / "calendar_active.png", dpi=180); plt.close(fig)
    # 4 rolling 3y IR
    act = res.net - res.bench
    ir = act.rolling(dd_window).mean() / act.rolling(dd_window).std() * 12 ** .5
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ir.plot(ax=ax, color=c_s, lw=2); ax.axhline(0, color="k", lw=.6); ax.set_title(f"Rolling {dd_window//12}-year information ratio"); ax.set_xlabel("")
    fig.tight_layout(); fig.savefig(FIG / "rolling_ir.png", dpi=180); plt.close(fig)
    # 5 active factor exposures
    fig, ax = plt.subplots(figsize=(9, 3.6))
    expo.plot(ax=ax, lw=1.6, color=["#0B3D91", "#2A9D8F", "#E9C46A", "#B23A48"])
    ax.axhline(0, color="k", lw=.6); ax.set_title("Active factor exposure (portfolio z − benchmark z)"); ax.legend(frameon=False, ncol=4); ax.set_xlabel("")
    fig.tight_layout(); fig.savefig(FIG / "exposures.png", dpi=180); plt.close(fig)
    # 6 sleeves
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for f, col in zip(FACTORS, ["#0B3D91", "#2A9D8F", "#E9C46A", "#B23A48"]):
        ((1 + sleeves[f].net).cumprod() / (1 + sleeves[f].bench).cumprod()).plot(ax=ax, lw=1.6, color=col, label=f.capitalize())
    ((1 + res.net).cumprod() / (1 + res.bench).cumprod()).plot(ax=ax, lw=2.4, color="k", label="Multi-factor")
    ax.axhline(1, color="k", lw=.6); ax.set_title("Relative wealth vs. benchmark: single-factor sleeves and composite"); ax.legend(frameon=False, ncol=5); ax.set_xlabel("")
    fig.tight_layout(); fig.savefig(FIG / "sleeves.png", dpi=180); plt.close(fig)

def compare_chart(v1, v2):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ((1 + v1.net).cumprod() / (1 + v1.bench).cumprod()).plot(ax=ax, color="#9AA5B1", lw=2, label="v1: four-factor tilt (beta 0.89)")
    ((1 + v2.net).cumprod() / (1 + v2.bench).cumprod()).plot(ax=ax, color="#0B3D91", lw=2.2, label="v2: value + momentum + quality, beta-neutral")
    ax.axhline(1, color="k", lw=.6); ax.set_title("Relative wealth vs. cap-weighted benchmark: v1 vs. v2"); ax.legend(frameon=False); ax.set_xlabel("")
    fig.tight_layout(); fig.savefig(FIG / "v1_vs_v2.png", dpi=180); plt.close(fig)

if __name__ == "__main__":
    import sys
    label = sys.argv[1] if len(sys.argv) > 1 else "multifactor"
    tag = "" if label == "multifactor" else "_" + label
    _save = plt.Figure.savefig
    plt.Figure.savefig = lambda self, p, **k: _save(self, str(p).replace(".png", tag + ".png"), **k)
    res = pd.read_parquet(OUT / f"returns_{label}.parquet")
    W = pd.read_parquet(OUT / f"weights_{label}.parquet")
    sleeves = {f: pd.read_parquet(OUT / f"returns_{f}.parquet") for f in FACTORS}
    ff = french_factors()
    rf = ff["RF"].reindex(res.index).ffill()
    m = metrics(res.net, res.bench, rf)
    st = stress(res.net, res.bench, {"Aug 2011 (US downgrade)": ("2011-08", "2011-09"), "2015-16 (China/oil)": ("2015-08", "2016-02"),
                                     "Q4 2018": ("2018-10", "2018-12"), "COVID crash (Feb-Mar 2020)": ("2020-02", "2020-03"),
                                     "2022 bear market": ("2022-01", "2022-12")})
    cal = calendar(res.net, res.bench)
    reg, r2 = ff_regression(res.net - res.bench)
    expo = exposures(W, {f: pd.read_parquet(PROC / f"{f}.parquet") for f in FACTORS})
    sl = pd.DataFrame({f: metrics(sleeves[f].net, sleeves[f].bench, rf)[["Excess return", "Tracking error", "Information ratio"]] for f in FACTORS}).T
    for name, obj in [("metrics", m), ("stress", st), ("calendar", cal), ("ff_regression", reg), ("exposures", expo), ("sleeves", sl)]:
        obj.to_csv(OUT / f"{name}{tag}.csv")
    pd.Series({"r2": r2}).to_csv(OUT / f"ff_r2{tag}.csv")
    charts(res, cal, expo, sleeves)
    if label != "multifactor":
        compare_chart(pd.read_parquet(OUT / "returns_multifactor.parquet"), res)
    pd.set_option("display.float_format", lambda x: f"{x:.3f}")
    print(m.to_string()); print(); print(st.to_string()); print(); print(cal.to_string()); print()
    print(reg.to_string(), f"\nR2 {r2:.2f}"); print(); print(sl.to_string())
    print("\navg active exposure:\n", expo.mean().to_string())
