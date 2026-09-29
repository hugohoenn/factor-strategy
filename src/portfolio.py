"""Long-only, sector-neutral factor tilt with a single-name cap, turnover cap and t-costs.

Target weights each month:   w_i  ∝  cap_i · exp(λ · score_i)
  1. tilt cap weights by composite score
  2. rescale each sector to the benchmark's sector weight   (sector neutrality)
  3. cap single names at MAX_WEIGHT, redistribute pro-rata (iterate to convergence)
Trading: move from drifted holdings toward the target, scaled so that one-way turnover
≤ TURNOVER_CAP. Cost = TCOST_BPS × dollars traded (buys + sells).
"""
import numpy as np, pandas as pd
from config import TILT_STRENGTH, MAX_WEIGHT, TURNOVER_CAP, TCOST_BPS

def cap_weights(mktcap_row, invest_row):
    w = mktcap_row.where(invest_row).fillna(0.0)
    return w / w.sum()

def apply_cap(w, cap=MAX_WEIGHT, iters=50):
    w = w.copy()
    for _ in range(iters):
        over = w > cap
        if not over.any(): break
        excess = (w[over] - cap).sum()
        w[over] = cap
        under = ~over & (w > 0)
        w[under] += excess * w[under] / w[under].sum()
    return w / w.sum()

def sector_rescale(w, bench, sectors):
    bsec = bench.groupby(sectors).sum(); tsec = w.groupby(sectors).sum()
    scale = (bsec / tsec).replace([np.inf, -np.inf], 0).fillna(0)
    w = w * sectors.map(scale).fillna(0).values
    return w / w.sum()

def beta_match(w, bench, beta_row, sectors, cap=MAX_WEIGHT, iters=3):
    """Re-tilt weights by exp(gamma*(beta-1)) so ex-ante portfolio beta equals the benchmark's,
    re-imposing sector neutrality and the name cap. gamma found by bisection."""
    b = beta_row.reindex(w.index).fillna(1.0)
    target = (bench * b).sum()
    for _ in range(iters):
        def pbeta(g):
            x = w * np.exp(g * (b - 1)); x = apply_cap(sector_rescale(x / x.sum(), bench, sectors), cap)
            return (x * b).sum() - target, x
        lo, hi = -8.0, 8.0
        for _ in range(40):
            mid = (lo + hi) / 2
            f, _x = pbeta(mid)
            if f > 0: hi = mid
            else: lo = mid
        _, w = pbeta((lo + hi) / 2)
    return w

def target_weights(score_row, mktcap_row, invest_row, sectors, lam=TILT_STRENGTH, beta_row=None):
    bench = cap_weights(mktcap_row, invest_row)
    ok = invest_row & score_row.notna()
    tilt = (mktcap_row * np.exp(lam * score_row)).where(ok).fillna(0.0)
    w = apply_cap(sector_rescale(tilt / tilt.sum(), bench, sectors))
    if beta_row is not None:                    # v2: beta-neutral construction
        w = beta_match(w, bench, beta_row, sectors)
    return w, bench

def trade_toward(w_old, w_target, cap=TURNOVER_CAP):
    """Partial rebalance so that one-way turnover <= cap. Returns new weights, one-way turnover."""
    full = 0.5 * (w_target - w_old).abs().sum()
    alpha = 1.0 if full <= cap else cap / full
    w_new = w_old + alpha * (w_target - w_old)
    return w_new, alpha * full

def drift(w, ret_row):
    """Let holdings drift with realised returns; missing return -> treated as 0."""
    g = w * (1 + ret_row.reindex(w.index).fillna(0.0))
    return g / g.sum()

def tcost(one_way_turnover, bps=TCOST_BPS):
    return 2 * one_way_turnover * bps / 1e4
