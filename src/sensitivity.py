"""Pre-specified sensitivity grid. Reported in full (no cherry-picking): tilt strength,
single-name cap, turnover cap, and a 3-factor variant without low-volatility."""
import pandas as pd, numpy as np
import config
from config import OUT, FACTORS
import portfolio, backtest
from analytics import metrics, french_factors

def run_variant(P, sectors, lam=None, cap=None, tocap=None, drop=None):
    lam0, cap0 = portfolio.TILT_STRENGTH, portfolio.MAX_WEIGHT
    if lam is not None: portfolio.TILT_STRENGTH = lam
    if cap is not None: portfolio.MAX_WEIGHT = cap
    score = P["composite"]
    if drop:
        keep = [f for f in FACTORS if f != drop]
        stack = pd.concat([P[f] for f in keep], axis=1, keys=keep)
        comp = stack.T.groupby(level=1).mean().T.reindex(columns=score.columns)
        from factors import zscore; score = zscore(comp.where(P["invest"]))
    # target_weights reads module globals at call time via default args -> pass explicitly
    orig = portfolio.target_weights
    portfolio.target_weights = lambda s, m, i, sec, lam=portfolio.TILT_STRENGTH: _tw(s, m, i, sec, lam, portfolio.MAX_WEIGHT)
    backtest.target_weights = portfolio.target_weights
    res, _ = backtest.run(score, P["mktcap"], P["padj"], P["invest"], sectors,
                          turnover_cap=tocap if tocap is not None else config.TURNOVER_CAP, label="tmp")
    portfolio.target_weights = orig; backtest.target_weights = orig
    portfolio.TILT_STRENGTH, portfolio.MAX_WEIGHT = lam0, cap0
    return res

def _tw(score_row, mktcap_row, invest_row, sectors, lam, cap):
    bench = portfolio.cap_weights(mktcap_row, invest_row)
    ok = invest_row & score_row.notna()
    tilt = (mktcap_row * np.exp(lam * score_row)).where(ok).fillna(0.0); tilt = tilt / tilt.sum()
    bsec = bench.groupby(sectors).sum(); tsec = tilt.groupby(sectors).sum()
    scale = (bsec / tsec).replace([np.inf, -np.inf], 0).fillna(0)
    w = tilt * sectors.map(scale).fillna(0).values; w = w / w.sum()
    return portfolio.apply_cap(w, cap), bench

if __name__ == "__main__":
    P, sectors = backtest.load()
    rf = french_factors()["RF"]
    grid = {"Base (λ=1, cap 5%, TO 20%)": {},
            "λ = 0.5": {"lam": 0.5}, "λ = 2.0": {"lam": 2.0},
            "No single-name cap": {"cap": 1.0}, "Name cap 3%": {"cap": 0.03},
            "Turnover cap 10%": {"tocap": 0.10}, "No turnover cap": {"tocap": 1.0},
            "3-factor (drop low-vol)": {"drop": "lowvol"}, "3-factor (drop value)": {"drop": "value"}}
    rows = {}
    for name, kw in grid.items():
        r = run_variant(P, sectors, **kw)
        m = metrics(r.net, r.bench, rf.reindex(r.index).ffill())
        rows[name] = {"Excess ret": m["Excess return"], "TE": m["Tracking error"], "IR": m["Information ratio"],
                      "Sharpe": m["Sharpe"], "Beta": m["Beta"], "Max DD": m["Max drawdown"], "1-way TO": r.turnover.mean()}
        print(name, {k: round(v, 3) for k, v in rows[name].items()}, flush=True)
    df = pd.DataFrame(rows).T; df.to_csv(OUT / "sensitivity.csv")
