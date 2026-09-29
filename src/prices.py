"""Download daily adjusted prices and unadjusted close for the universe via yfinance.

Adjusted close -> returns. Unadjusted close x shares outstanding -> market cap.
"""
import time
import pandas as pd, yfinance as yf
from config import RAW, START

def download(tickers, start=START, batch=100):
    adj, raw = [], []
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        for attempt in range(3):
            try:
                d = yf.download(chunk, start=start, progress=False, auto_adjust=False,
                                threads=True, group_by="column")
                break
            except Exception as e:
                print("retry", attempt, e); time.sleep(5)
        adj.append(d["Adj Close"]); raw.append(d["Close"])
        print(f"{i + len(chunk)}/{len(tickers)}", flush=True)
    adj = pd.concat(adj, axis=1).sort_index(); raw = pd.concat(raw, axis=1).sort_index()
    adj = adj.dropna(how="all"); raw = raw.loc[adj.index]
    adj.to_parquet(RAW / "adj_close.parquet"); raw.to_parquet(RAW / "close.parquet")
    return adj, raw

if __name__ == "__main__":
    u = pd.read_csv(RAW / "universe.csv")
    adj, raw = download(u["ticker"].tolist())
    print(adj.shape, adj.index.min().date(), adj.index.max().date())
    print("names with data by 2011:", adj.loc["2011-01"].notna().any().sum())
