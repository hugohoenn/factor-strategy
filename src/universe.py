"""Pull the current S&P 500 constituent list (ticker, sector, CIK) from Wikipedia.

Limitation (disclosed in README): this is today's membership, so the backtest has
survivorship bias. The cap-weighted benchmark is built from the same universe so the
strategy-vs-benchmark comparison is apples-to-apples.
"""
import io
import pandas as pd, requests
from config import RAW

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

def get_universe() -> pd.DataFrame:
    html = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}).text
    tbl = pd.read_html(io.StringIO(html))[0]
    df = tbl.rename(columns={"Symbol": "ticker", "Security": "name",
                             "GICS Sector": "sector", "CIK": "cik"})[["ticker", "name", "sector", "cik"]]
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)   # BRK.B -> BRK-B for Yahoo
    df["cik"] = df["cik"].astype(int)
    df.to_csv(RAW / "universe.csv", index=False)
    return df

if __name__ == "__main__":
    u = get_universe()
    print(len(u), "names;", u["sector"].nunique(), "sectors")
    print(u["sector"].value_counts().to_string())

# Wikipedia lists the CIK of a 2026 holding-company reorganisation for Exxon; the operating
# company's historical filings live under the predecessor CIK. Applied in fundamentals pull.
PREDECESSOR_CIK = {"XOM": 34088}
