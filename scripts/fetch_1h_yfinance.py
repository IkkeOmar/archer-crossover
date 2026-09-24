"""Fetch 1h data for SPY/QQQ/IWM/AAPL/GOOGL/GLD/SLV via yfinance (730 days)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import fetch_yfinance, DATA_DIR

TICKERS = ['SPY', 'QQQ', 'IWM', 'AAPL', 'GOOGL', 'GLD', 'SLV']

for tk in TICKERS:
    t0 = time.time()
    try:
        # yfinance 1h max 730 days
        df = fetch_yfinance(tk, '1h', period='730d')
        # Save with explicit suffix to mark it as 730d-limited
        path = DATA_DIR / f"{tk.replace('-', '_')}_1h_730d.csv"
        df.index.name = 'date'
        df.to_csv(path)
        print(f'  {tk:8s} 1h 730d: {len(df)} candles, {df.index[0]} to {df.index[-1]}, {time.time()-t0:.1f}s')
    except Exception as e:
        print(f'  {tk}: FAIL ({e})')
