"""archer-crossover Python package.

Vectorized EMA-crossover strategy with stochastic delay.
"""

# Modules:
#   data_loader.py  - fetch OHLCV from yfinance + ccxt, cache to CSV
#   archer_engine.py - vectorized backtest with 4D parameter support
#   metrics.py      - Sharpe, CAGR, max DD, Calmar, win rate
#   sweep.py        - parallel parameter sweep runner
#   montecarlo.py   - robustness simulation
#   synthetic.py    - synthetic market generators (GBM, bootstrap, trending, OU)
#   plots.py        - heatmaps, 3D surfaces, equity curves (log scale)
#   report.py       - aggregate results into CSV/LaTeX-ready tables
