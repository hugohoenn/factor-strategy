"""v3 data layer: CRSP + Compustat via WRDS. Survivorship-free S&P 500 universe with point-in-time membership.
Raw WRDS files live in data/wrds/ (gitignored; licensed). Only derived panels are saved to data/processed/v3."""
import numpy as np, pandas as pd
from config import ROOT
W = ROOT / "data" / "wrds"; P3 = ROOT / "data" / "processed" / "v3"; P3.mkdir(parents=True, exist_ok=True)
FUND_LAG_MONTHS = 6      # annual statements usable 6 months after fiscal year end (Fama-French convention)
STALE_MONTHS = 18

def ff12(sic):
    """Fama-French 12 industry classification from SIC code (sector-neutralisation groups)."""
    s = pd.to_numeric(sic, errors="coerce")
    out = pd.Series("Other", index=s.index)
    rng = lambda a, b: (s >= a) & (s <= b)
    out[rng(100, 999) | rng(2000, 2399) | rng(2700, 2749) | rng(2770, 2799) | rng(3100, 3199) | rng(3940, 3989)] = "NoDur"
    out[rng(2500, 2519) | rng(2590, 2599) | rng(3630, 3659) | rng(3710, 3711) | rng(3714, 3714) | rng(3716, 3716) | rng(3750, 3751) | rng(3792, 3792) | rng(3900, 3939) | rng(3990, 3999)] = "Durbl"
    out[rng(2520, 2589) | rng(2600, 2699) | rng(2750, 2769) | rng(3000, 3099) | rng(3200, 3569) | rng(3580, 3629) | rng(3700, 3709) | rng(3712, 3713) | rng(3715, 3715) | rng(3717, 3749) | rng(3752, 3791) | rng(3793, 3799) | rng(3830, 3839) | rng(3860, 3899)] = "Manuf"
    out[rng(1200, 1399) | rng(2900, 2999)] = "Enrgy"
    out[rng(2800, 2829) | rng(2840, 2899)] = "Chems"
    out[rng(3570, 3579) | rng(3660, 3692) | rng(3694, 3699) | rng(3810, 3829) | rng(7370, 7379)] = "BusEq"
    out[rng(4800, 4899)] = "Telcm"
    out[rng(4900, 4949)] = "Utils"
    out[rng(5000, 5999) | rng(7200, 7299) | rng(7600, 7699)] = "Shops"
    out[rng(2830, 2839) | rng(3693, 3693) | rng(3840, 3859) | rng(8000, 8099)] = "Hlth"
    out[rng(6000, 6999)] = "Money"
    return out

def build():
    sp = pd.read_csv(W / "sp500_list.csv", parse_dates=["start", "ending"])
    members = set(sp.permno)
    crsp = pd.read_csv(W / "crsp_monthly.csv.gz", usecols=["PERMNO", "PERMCO", "MthCalDt", "MthRet", "MthPrc", "MthCap", "SICCD", "Ticker"],
                       dtype={"PERMNO": int}, parse_dates=["MthCalDt"])
    crsp = crsp[crsp.PERMNO.isin(members)].copy()
    crsp["me"] = pd.to_datetime(crsp.MthCalDt).dt.to_period("M")
    crsp = crsp.sort_values(["PERMNO", "MthCalDt"]).drop_duplicates(["PERMNO", "me"], keep="last")
    ret = crsp.pivot(index="me", columns="PERMNO", values="MthRet")
    cap = crsp.pivot(index="me", columns="PERMNO", values="MthCap") * 1e3          # MthCap in $000s -> $
    prc = crsp.pivot(index="me", columns="PERMNO", values="MthPrc").abs()
    sic = crsp.groupby("PERMNO").SICCD.last()
    # membership panel: True when start <= month-end < ending (ending NaN = still a member)
    mem = pd.DataFrame(False, index=ret.index, columns=ret.columns)
    mend = ret.index.to_timestamp(how="end").normalize()
    for r in sp.itertuples():
        if r.permno not in mem.columns: continue
        ok = (mend >= r.start) & ((mend < r.ending) if pd.notna(r.ending) else True)
        mem.loc[ok, r.permno] = True
    # --- fundamentals -> permno, point in time ---
    fu = pd.read_csv(W / "funda.csv.gz", dtype={"gvkey": str}, parse_dates=["datadate"])
    fu = fu[(fu.indfmt == "INDL") & (fu.datafmt == "STD") & (fu.consol == "C") & (fu.curcd == "USD")]
    lk = pd.read_csv(W / "ccm_link.csv.gz", dtype={"gvkey": str, "LINKENDDT": str}, parse_dates=["LINKDT"])
    lk = lk[lk.LINKTYPE.isin(["LC", "LU"]) & lk.LINKPRIM.isin(["P", "C"])].copy()
    lk["LINKENDDT"] = pd.to_datetime(lk.LINKENDDT.replace("E", "2099-12-31"), errors="coerce").fillna(pd.Timestamp("2099-12-31"))   # "E" = still active
    m = fu.merge(lk[["gvkey", "LPERMNO", "LINKDT", "LINKENDDT"]], on="gvkey")
    m = m[(m.datadate >= m.LINKDT) & (m.datadate <= m.LINKENDDT) & m.LPERMNO.isin(members)]
    m["avail"] = (m.datadate + pd.DateOffset(months=FUND_LAG_MONTHS)).dt.to_period("M")
    m = m.sort_values(["LPERMNO", "avail", "datadate"]).drop_duplicates(["LPERMNO", "avail"], keep="last")
    for c in ["ceq", "at", "ni", "oancf", "revt", "gp"]: m[c] = m[c] * 1e6                 # $ millions -> $
    panels = {}
    for c in ["ceq", "at", "ni", "oancf", "revt", "gp"]:
        v = m.pivot(index="avail", columns="LPERMNO", values=c); d = m.pivot(index="avail", columns="LPERMNO", values="datadate")
        idx = v.index.union(ret.index); v = v.reindex(idx).ffill().reindex(ret.index); d = d.reindex(idx).ffill().reindex(ret.index)
        age = (ret.index.to_timestamp(how="end").values[:, None] - d.values.astype("datetime64[ns]")).astype("timedelta64[D]").astype(float) / 30.4
        panels[c] = v.mask(age > STALE_MONTHS).reindex(columns=ret.columns)
    sich = m.groupby("LPERMNO").sich.last().reindex(ret.columns)
    industry = ff12(sich.fillna(sic.reindex(ret.columns)))
    for k, v in {"ret": ret, "cap": cap, "prc": prc, "member": mem, **panels}.items(): v.to_parquet(P3 / f"{k}.parquet")
    industry.to_frame("ff12").to_parquet(P3 / "industry.parquet")
    print(f"permnos {ret.shape[1]}, months {ret.index[0]}..{ret.index[-1]}; avg members/month {mem.sum(axis=1).loc['1990':].mean():.0f}")
    p95 = pd.Period("1995-01", "M"); print("fundamental coverage among members 1995-01:", int((panels["ceq"].loc[p95].notna() & mem.loc[p95]).sum()), "of", int(mem.loc[p95].sum()))
    print("industry mix:", industry.value_counts().to_dict())
    return ret, cap, mem, panels, industry

if __name__ == "__main__":
    build()
