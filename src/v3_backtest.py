"""v3: the v2 strategy (value + momentum + quality, sector-neutral, beta-neutral) on a survivorship-free,
point-in-time S&P 500 universe from CRSP/Compustat, 1990-2025."""
import numpy as np, pandas as pd
from config import ROOT, FACTORS
from factors import zscore
from portfolio import target_weights, trade_toward, drift, tcost
from wrds_data import P3
O3 = ROOT / "output" / "v3"; O3.mkdir(exist_ok=True)
START = pd.Period("1990-01", "M")

def load():
    D = {k: pd.read_parquet(P3 / f"{k}.parquet") for k in ["ret", "cap", "member", "ceq", "at", "ni", "oancf"]}
    ind = pd.read_parquet(P3 / "industry.parquet")["ff12"]
    return D, ind

def sector_neutral_z(raw, sectors):
    z = zscore(raw); out = z.copy()
    for sec, names in sectors.groupby(sectors).groups.items():
        cols = [c for c in names if c in z.columns]; block = z[cols]; out[cols] = block.sub(block.mean(axis=1), axis=0)
    return zscore(out)

def build_factors(D, ind):
    ret, cap, mem = D["ret"], D["cap"], D["member"]
    invest = mem & cap.notna() & ret.notna()
    px = (1 + ret.fillna(0)).cumprod()                      # total-return index per stock
    mom = px.shift(1) / px.shift(12) - 1
    bm = (D["ceq"] / cap).where(D["ceq"] > 0); ep = D["ni"] / cap
    roe = (D["ni"] / D["ceq"]).where(D["ceq"] > 0); cfoa = D["oancf"] / D["at"]
    sz = lambda x: sector_neutral_z(x.where(invest), ind)
    avg = lambda *xs: pd.concat(xs, axis=1, keys=range(len(xs))).T.groupby(level=1).mean().T
    value = avg(sz(np.log(bm)), sz(ep)); quality = avg(sz(roe), sz(cfoa)); momentum = sz(mom)
    stack = pd.concat({"value": value, "momentum": momentum, "quality": quality}, axis=1)
    comp = stack.T.groupby(level=1).mean().T.where(stack.notna().T.groupby(level=1).sum().T >= 2)
    composite = zscore(comp.reindex(columns=ret.columns).where(invest))
    # 60-month rolling beta vs cap-weighted universe, Vasicek-shrunk
    w = cap.where(mem).div(cap.where(mem).sum(axis=1), axis=0).shift(1)
    mkt = (w * ret).sum(axis=1, min_count=1)
    cov = ret.rolling(60, min_periods=36).cov(mkt); var = mkt.rolling(60, min_periods=36).var()
    beta = (2 / 3) * cov.div(var, axis=0) + (1 / 3)
    return dict(composite=composite, value=value, momentum=momentum, quality=quality, beta=beta, invest=invest & composite.notna(), mkt=mkt)

def run(score, cap, ret, invest, ind, beta, start=START, label="v3"):
    dates = [d for d in score.index if d >= start]; rows, weights, w = [], {}, None
    for i, t in enumerate(dates[:-1]):
        inv = invest.loc[t]
        if inv.sum() < 300: continue
        w_tgt, w_b = target_weights(score.loc[t], cap.loc[t], inv, ind, beta_row=beta.loc[t])
        if w is None: w, to = w_tgt, 0.0
        else: w, to = trade_toward(w, w_tgt)
        nxt = dates[i + 1]; r = ret.loc[nxt].reindex(w.index).fillna(0.0)          # delisting returns already in MthRet
        gross = (w * r).sum(); cost = tcost(to); bench = (w_b * r).sum()
        rows.append({"date": nxt.to_timestamp(how="end").normalize(), "gross": gross, "net": gross - cost, "bench": bench, "turnover": to, "names": int((w > 0).sum()),
                     "active_share": 0.5 * (w - w_b).abs().sum()})
        weights[t] = w; w = drift(w, r)
    res = pd.DataFrame(rows).set_index("date"); res.to_parquet(O3 / f"returns_{label}.parquet"); return res

if __name__ == "__main__":
    D, ind = load(); F = build_factors(D, ind)
    print("investable/month 1990+:", F["invest"].loc[START:].sum(axis=1).describe()[["min", "50%", "max"]].round(0).to_dict())
    res = run(F["composite"], D["cap"], D["ret"], F["invest"], ind, F["beta"])
    ann = lambda x: (1 + x).prod() ** (12 / len(x)) - 1; act = res.net - res.bench
    print(f"v3 {res.index[0]:%b %Y}-{res.index[-1]:%b %Y} {len(res)} months | net {ann(res.net):.2%} bench {ann(res.bench):.2%} excess {ann(res.net)-ann(res.bench):+.2%} | TE {act.std()*12**.5:.2%} IR {act.mean()/act.std()*12**.5:.2f} | turnover {res.turnover.mean():.1%} names {res.names.mean():.0f}")
    for f in ["value", "momentum", "quality"]:
        r = run(F[f], D["cap"], D["ret"], F["invest"], ind, F["beta"], label=f"v3_{f}"); a = r.net - r.bench
        print(f"  {f:9s} excess {ann(r.net)-ann(r.bench):+.2%}  IR {a.mean()/a.std()*12**.5:.2f}")
