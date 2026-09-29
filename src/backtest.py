"""Monthly backtest of the multi-factor tilt vs. a cap-weighted benchmark of the same universe.

Also runs four single-factor sleeves (same construction) for attribution.
"""
import numpy as np, pandas as pd
from config import PROC, OUT, RAW, FACTORS, BACKTEST_START, MIN_NAMES, TURNOVER_CAP
from portfolio import target_weights, trade_toward, drift, tcost

def run(score_panel, mktcap, padj, invest, sectors, start=BACKTEST_START, turnover_cap=TURNOVER_CAP, label="strategy", beta=None):
    mret = padj.pct_change(fill_method=None)               # month-end to month-end returns
    dates = score_panel.index[score_panel.index >= pd.Timestamp(start)]
    dates = dates[dates < mret.index[-1]]                  # need a following month
    recs, weights = [], {}
    w = None
    for t in dates:
        nxt = mret.index[mret.index.get_loc(t) + 1]
        inv = invest.loc[t]
        if inv.sum() < MIN_NAMES: continue
        w_tgt, w_bench = target_weights(score_panel.loc[t], mktcap.loc[t], inv, sectors,
                                        beta_row=None if beta is None else beta.loc[t])
        if w is None:
            w, to = w_tgt, 0.0                              # initial build: no cost charged
        else:
            w, to = trade_toward(w, w_tgt, turnover_cap)
        r_next = mret.loc[nxt]
        gross = (w * r_next.fillna(0)).sum()
        cost = tcost(to)
        bench_r = (w_bench * r_next.fillna(0)).sum()
        recs.append({"date": nxt, "gross": gross, "net": gross - cost, "bench": bench_r,
                     "turnover": to, "cost": cost, "names": int((w > 0).sum()),
                     "active_share": 0.5 * (w - w_bench).abs().sum(),
                     "exante_beta": (w * beta.loc[t].reindex(w.index).fillna(1)).sum() if beta is not None else np.nan})
        weights[t] = w
        w = drift(w, r_next)
    res = pd.DataFrame(recs).set_index("date")
    W = pd.DataFrame(weights).T
    res.to_parquet(OUT / f"returns_{label}.parquet"); W.to_parquet(OUT / f"weights_{label}.parquet")
    return res, W

def load():
    P = {k: pd.read_parquet(PROC / f"{k}.parquet") for k in ["composite", "composite3", "beta", "mktcap", "padj", "invest"] + FACTORS}
    uni = pd.read_csv(RAW / "universe.csv").set_index("ticker")
    sectors = uni["sector"].reindex(P["padj"].columns)
    return P, sectors

if __name__ == "__main__":
    P, sectors = load()
    res, W = run(P["composite"], P["mktcap"], P["padj"], P["invest"], sectors, label="multifactor")
    print(res.index[0].date(), "->", res.index[-1].date(), len(res), "months")
    ann = lambda x: (1 + x).prod() ** (12 / len(x)) - 1
    print(f"net ann {ann(res.net):.2%}  bench ann {ann(res.bench):.2%}  "
          f"avg 1-way turnover {res.turnover.mean():.1%}  avg names {res.names.mean():.0f}  "
          f"active share {res.active_share.mean():.1%}")
    res2, W2 = run(P["composite3"], P["mktcap"], P["padj"], P["invest"], sectors, label="v2_betaneutral", beta=P["beta"])
    print(f"v2  net ann {ann(res2.net):.2%}  bench {ann(res2.bench):.2%}  active {ann(res2.net)-ann(res2.bench):+.2%}  "
          f"turnover {res2.turnover.mean():.1%}  ex-ante beta {res2.exante_beta.mean():.3f}")
    for f in FACTORS:                                       # single-factor sleeves
        r, _ = run(P[f], P["mktcap"], P["padj"], P["invest"], sectors, label=f)
        print(f"{f:9s} net ann {ann(r.net):.2%}  active {ann(r.net)-ann(r.bench):+.2%}")
