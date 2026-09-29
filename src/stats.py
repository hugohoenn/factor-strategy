"""Statistical honesty checks: block-bootstrap CI on the information ratio and a split-sample test.
Run for v1 (4-factor tilt) and v2 (3-factor, beta-neutral). Reported whatever they say."""
import numpy as np, pandas as pd
from config import OUT
from analytics import metrics, french_factors

def block_bootstrap_ir(act, n=10000, block=12, seed=0):
    rng = np.random.default_rng(seed); a = act.values; T = len(a); nb = int(np.ceil(T / block))
    irs = np.empty(n)
    for i in range(n):
        starts = rng.integers(0, T - block + 1, nb)
        samp = np.concatenate([a[s:s + block] for s in starts])[:T]
        irs[i] = samp.mean() / samp.std() * 12 ** .5
    return np.percentile(irs, [5, 50, 95]), (irs > 0).mean()

def split_sample(r, b, rf, cut="2018-12-31"):
    rows = {}
    for name, (s, e) in {"2011-2018": (None, cut), "2019-2026": (pd.Timestamp(cut) + pd.Timedelta(days=1), None)}.items():
        rs, bs = r.loc[s:e], b.loc[s:e]
        m = metrics(rs, bs, rf.reindex(rs.index).ffill())
        rows[name] = m[["Excess return", "Tracking error", "Information ratio", "Sharpe", "Benchmark Sharpe", "Beta"]]
    return pd.DataFrame(rows).T

if __name__ == "__main__":
    rf = french_factors()["RF"]
    out = []
    for label, f in [("v1 four-factor tilt", "multifactor"), ("v2 beta-neutral, 3-factor", "v2_betaneutral")]:
        res = pd.read_parquet(OUT / f"returns_{f}.parquet"); act = res.net - res.bench
        (lo, med, hi), p = block_bootstrap_ir(act)
        ir = act.mean() / act.std() * 12 ** .5
        print(f"{label}: IR {ir:+.2f}   90% bootstrap CI [{lo:+.2f}, {hi:+.2f}]   P(IR>0) = {p:.0%}")
        ss = split_sample(res.net, res.bench, rf); print(ss.round(3).to_string()); print()
        ss["version"] = label; out.append(ss)
        pd.Series({"IR": ir, "CI5": lo, "CI95": hi, "P_IR_pos": p}).to_csv(OUT / f"bootstrap_{f}.csv")
    pd.concat(out).to_csv(OUT / "split_sample.csv")
