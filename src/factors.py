"""Build monthly, point-in-time factor scores for the universe.

Factors (all higher = better):
  value     : mean z of book-to-market and earnings yield (net income / market cap)
  momentum  : 12-1 month total return (skip most recent month)
  quality   : mean z of ROE (net income / equity) and cash-flow return on assets (OCF / assets)
  lowvol    : negative 252-day realised volatility of daily returns
Each raw factor is winsorised, sector-demeaned, and z-scored cross-sectionally each month.
Composite = equal-weighted mean of available factor z's (need >= 3 of 4).
"""
import numpy as np, pandas as pd
from config import RAW, PROC, FACTORS, MOM_LOOKBACK, MOM_SKIP, VOL_LOOKBACK_DAYS, WINSOR

STALE_DAYS = 550   # a fundamental older than ~18 months is treated as missing

def clean_scale_errors(long, max_ratio={"shares": 3.0}, default_ratio=10.0, window=7):
    """Drop observations that deviate from a rolling median of the same series by more than
    a factor (catches XBRL scale errors, e.g. shares reported x1e6)."""
    def flag(g):
        ls = np.log(g["val"].abs().clip(lower=1e-9))
        med = ls.rolling(window, center=True, min_periods=3).median()
        r = max_ratio.get(g.name[1], default_ratio)
        return (ls - med).abs() > np.log(r)
    long = long.sort_values(["ticker", "concept", "end"])
    bad = long.groupby(["ticker", "concept"], group_keys=False).apply(flag)
    return long[~bad.reindex(long.index).fillna(False)]

def load_panels():
    adj = pd.read_parquet(RAW / "adj_close.parquet")
    close = pd.read_parquet(RAW / "close.parquet")
    uni = pd.read_csv(RAW / "universe.csv").set_index("ticker")
    long = pd.read_parquet(RAW / "fundamentals_long.parquet")
    n0 = len(long); long = clean_scale_errors(long)
    print(f"scale-error filter dropped {n0 - len(long)} of {n0} observations")
    return adj, close, uni, long

def month_ends(adj):
    return adj.resample("ME").last().index

def asof_panel(long, concept, mends, tickers):
    """Wide panel (month-end x ticker) of the latest value FILED on or before each month-end."""
    d = long[long["concept"] == concept].sort_values(["ticker", "filed", "end"])
    d = d.drop_duplicates(["ticker", "filed"], keep="last")          # latest period per filing date
    val = d.pivot(index="filed", columns="ticker", values="val")
    end = d.pivot(index="filed", columns="ticker", values="end")
    idx = val.index.union(mends)
    val = val.reindex(idx).ffill().reindex(mends)
    end = end.reindex(idx).ffill().reindex(mends)
    age = (pd.Series(mends, index=mends).to_frame().values - end.values.astype("datetime64[ns]")).astype("timedelta64[D]").astype(float)
    val = val.mask(age > STALE_DAYS)
    return val.reindex(columns=tickers)

def zscore(df, winsor=WINSOR):
    z = df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1), axis=0)
    return z.clip(-winsor, winsor)

def sector_neutral_z(raw, sectors):
    """Winsorise -> demean within sector -> z-score across universe, month by month."""
    z = zscore(raw)                                   # first pass: tame outliers
    out = z.copy()
    for sec, names in sectors.groupby(sectors).groups.items():
        cols = [c for c in names if c in z.columns]
        block = z[cols]
        out[cols] = block.sub(block.mean(axis=1), axis=0)
    return zscore(out)

def build():
    adj, close, uni, long = load_panels()
    tickers = adj.columns
    mends = month_ends(adj)
    padj = adj.resample("ME").last()
    pclose = close.resample("ME").last()
    dret = adj.pct_change(fill_method=None)

    # --- fundamentals as-of each month-end ---
    F = {c: asof_panel(long, c, mends, tickers) for c in ["equity", "assets", "netinc", "ocf", "shares"]}
    # yfinance prices are split-adjusted to today's basis; SEC shares are historical. Multiply
    # historical shares by all splits that occur AFTER each month-end to put them on the same basis.
    sp = pd.read_parquet(RAW / "splits.parquet").reindex(columns=tickers)
    full = sp.index.union(mends)
    Fs = sp.reindex(full).fillna(0.0).replace(0.0, 1.0)
    after = (Fs.iloc[::-1].cumprod().iloc[::-1] / Fs).reindex(mends)
    mktcap = pclose * F["shares"] * after
    mktcap = mktcap.where((mktcap > 0) & (mktcap < 1e13))   # > $10T is a data error

    # --- raw factors ---
    bm = (F["equity"] / mktcap).where(F["equity"] > 0)
    ep = F["netinc"] / mktcap
    roe = (F["netinc"] / F["equity"]).where(F["equity"] > 0)
    cfoa = F["ocf"] / F["assets"]
    mom = padj.shift(MOM_SKIP) / padj.shift(MOM_LOOKBACK) - 1
    vol = dret.rolling(VOL_LOOKBACK_DAYS, min_periods=200).std().resample("ME").last()
    lowvol = -vol

    # --- 252-day rolling beta vs. the cap-weighted universe, Vasicek-shrunk 2/3 toward 1 ---
    wcap = mktcap.div(mktcap.sum(axis=1), axis=0).reindex(dret.index, method="ffill").shift(1)
    mkt_d = (wcap * dret).sum(axis=1, min_count=1)
    cov = dret.rolling(VOL_LOOKBACK_DAYS, min_periods=200).cov(mkt_d)
    var = mkt_d.rolling(VOL_LOOKBACK_DAYS, min_periods=200).var()
    beta = (cov.div(var, axis=0)).resample("ME").last()
    beta = (2 / 3) * beta + (1 / 3) * 1.0

    sectors = uni["sector"].reindex(tickers)
    # investable: has a price this month and a market cap
    invest = padj.notna() & mktcap.notna()

    def sz(x): return sector_neutral_z(x.where(invest), sectors)
    def avg(*xs): return pd.concat(xs, axis=1, keys=range(len(xs))).T.groupby(level=1).mean().T
    value = avg(sz(np.log(bm)), sz(ep))            # log B/M is closer to normal
    quality = avg(sz(roe), sz(cfoa))
    momentum = sz(mom)
    lv = sz(lowvol)
    factors = {"value": value, "momentum": momentum, "quality": quality, "lowvol": lv}

    stack = pd.concat(factors, axis=1)              # columns: (factor, ticker)
    avail = stack.notna().T.groupby(level=1).sum().T   # count of factors per stock
    comp = stack.T.groupby(level=1).mean().T
    comp = comp.where(avail >= 3).reindex(columns=tickers)
    composite = zscore(comp.where(invest))

    # v2 composite: value, momentum, quality only. Low volatility is not a scored return factor;
    # it enters through the beta constraint in portfolio construction (see portfolio.py).
    stack3 = pd.concat({k: factors[k] for k in ["value", "momentum", "quality"]}, axis=1)
    comp3 = stack3.T.groupby(level=1).mean().T.where(stack3.notna().T.groupby(level=1).sum().T >= 2)
    composite3 = zscore(comp3.reindex(columns=tickers).where(invest))

    store = {"composite": composite, "composite3": composite3, "beta": beta, "mktcap": mktcap, "padj": padj,
             "invest": invest & composite.notna(), **factors}
    for k, v in store.items():
        v.to_parquet(PROC / f"{k}.parquet")
    return store

if __name__ == "__main__":
    s = build()
    inv = s["invest"]
    print("investable names per month (2011+):")
    print(inv.loc["2011":].sum(axis=1).describe()[["min", "50%", "max"]].to_string())
    for f in FACTORS:
        print(f, "coverage 2015-01:", int(s[f].loc["2015-01"].notna().sum(axis=1).iloc[0]))
