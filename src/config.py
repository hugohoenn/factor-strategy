"""Central configuration for the multi-factor equity strategy."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "output"
FIG = OUT / "figures"
for p in (RAW, PROC, OUT, FIG):
    p.mkdir(parents=True, exist_ok=True)

SEC_USER_AGENT = "Hugo Hoenn hhoenn@syr.edu"   # SEC requires a descriptive UA

START = "2005-01-01"            # price history start (lookback before first rebalance)
BACKTEST_START = "2011-01-31"   # first rebalance: XBRL fundamentals are reliable from ~2010
END = None                      # None = today

# --- Factor definitions ---
FACTORS = ["value", "momentum", "quality", "lowvol"]
MOM_LOOKBACK = 12           # months
MOM_SKIP = 1                # skip most recent month (short-term reversal)
VOL_LOOKBACK_DAYS = 252
WINSOR = 3.0                # z-score clip

# --- Portfolio construction ---
TILT_STRENGTH = 1.0         # lambda in w ~ cap * exp(lambda * score)
MAX_WEIGHT = 0.05           # single-name cap
TURNOVER_CAP = 0.20         # max one-way turnover per rebalance (fraction of portfolio)
TCOST_BPS = 10              # one-way cost per unit of turnover
MIN_NAMES = 200             # minimum investable universe size to trade a month
