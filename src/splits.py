"""Download stock-split history so SEC share counts can be put on yfinance's split-adjusted basis."""
import pandas as pd, yfinance as yf
from config import RAW, START
u = pd.read_csv(RAW / "universe.csv"); tick = u.ticker.tolist()
parts = []
for i in range(0, len(tick), 100):
    d = yf.download(tick[i:i+100], start=START, progress=False, actions=True, auto_adjust=False, group_by="column")
    parts.append(d["Stock Splits"])
sp = pd.concat(parts, axis=1).fillna(0.0)
sp = sp[(sp != 0).any(axis=1)]
sp.to_parquet(RAW / "splits.parquet")
print(sp.shape, "split events:", int((sp != 0).sum().sum()))
print("GE:", sp["GE"][sp["GE"] != 0].to_dict()); print("AAPL:", sp["AAPL"][sp["AAPL"] != 0].to_dict())
