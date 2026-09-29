"""Point-in-time fundamentals from SEC EDGAR XBRL 'companyfacts' (free, no key).

For every reported value we keep the period end ('end') and the date it was first
filed ('filed'). Factors are then built as-of each month-end using only values whose
filing date is <= that month-end, so there is no look-ahead bias.
"""
import time, requests, pandas as pd
from config import RAW, SEC_USER_AGENT

BASE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
HDR = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# concept -> list of acceptable us-gaap tags (first found wins per company)
CONCEPTS = {
    "equity":   ["StockholdersEquity",
                 "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "assets":   ["Assets"],
    "netinc":   ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "revenue":  ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                 "SalesRevenueNet", "RevenuesNetOfInterestExpense"],
    "opinc":    ["OperatingIncomeLoss"],
    "gross":    ["GrossProfit"],
    "ocf":      ["NetCashProvidedByUsedInOperatingActivities"],
}
FLOW = {"netinc", "revenue", "opinc", "gross", "ocf"}   # need 12-month duration

def _extract(facts, tags, flow):
    rows = []
    for tag in tags:
        node = facts.get("us-gaap", {}).get(tag)
        if not node: continue
        for unit, arr in node["units"].items():
            if unit != "USD": continue
            for r in arr:
                if r.get("form") not in ("10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "40-F"): continue
                if flow:
                    if "start" not in r: continue
                    dur = (pd.Timestamp(r["end"]) - pd.Timestamp(r["start"])).days
                    if not 350 <= dur <= 380: continue          # annual (12m) values only
                rows.append((r["end"], r["filed"], r["val"]))
        if rows: break
    if not rows: return None
    df = pd.DataFrame(rows, columns=["end", "filed", "val"])
    df["end"] = pd.to_datetime(df["end"]); df["filed"] = pd.to_datetime(df["filed"])
    df = df.sort_values(["end", "filed"]).drop_duplicates("end", keep="first")  # first disclosure
    return df

SHARE_TAGS = [("dei", "EntityCommonStockSharesOutstanding"),
              ("us-gaap", "CommonStockSharesOutstanding"),
              ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic")]

def _shares(facts):
    rows = []
    for ns, tag in SHARE_TAGS:                       # first tag with data wins
        node = facts.get(ns, {}).get(tag)
        if not node: continue
        rows = [(r["end"], r["filed"], r["val"]) for r in node["units"].get("shares", [])
                if r.get("form", "10-K").startswith(("10-", "20-F", "40-F"))]
        if rows: break
    if not rows: return None
    df = pd.DataFrame(rows, columns=["end", "filed", "val"])
    df["end"] = pd.to_datetime(df["end"]); df["filed"] = pd.to_datetime(df["filed"])
    df = df.groupby(["end", "filed"], as_index=False)["val"].sum()   # sum share classes
    return df.sort_values(["end", "filed"]).drop_duplicates("end", keep="first")

def pull(universe: pd.DataFrame):
    ck = RAW / "fund_checkpoint.parquet"
    out, done = [], set()
    if ck.exists():
        prev = pd.read_parquet(ck); out.append(prev); done = set(prev["ticker"])
    for i, (tkr, cik) in enumerate(zip(universe["ticker"], universe["cik"])):
        if tkr in done: continue
        for attempt in range(3):
            r = requests.get(BASE.format(cik=cik), headers=HDR, timeout=30)
            if r.status_code == 200: break
            time.sleep(2)
        if r.status_code != 200:
            print("miss", tkr, r.status_code); continue
        facts = r.json().get("facts", {})
        for c, tags in CONCEPTS.items():
            df = _extract(facts, tags, c in FLOW)
            if df is not None:
                df["ticker"] = tkr; df["concept"] = c; out.append(df)
        sh = _shares(facts)
        if sh is not None:
            sh["ticker"] = tkr; sh["concept"] = "shares"; out.append(sh)
        time.sleep(0.12)   # stay under SEC's 10 req/s
        if (i + 1) % 25 == 0:
            pd.concat(out, ignore_index=True).to_parquet(ck); print(i + 1, flush=True)
    long = pd.concat(out, ignore_index=True)
    long.to_parquet(RAW / "fundamentals_long.parquet")
    return long

if __name__ == "__main__":
    u = pd.read_csv(RAW / "universe.csv")
    long = pull(u)
    cov = long.groupby("concept")["ticker"].nunique()
    print(cov.to_string())
    print("earliest filed:", long["filed"].min().date())
