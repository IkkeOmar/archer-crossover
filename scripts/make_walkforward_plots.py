"""Walk-forward plot: bar chart of positive-test-Sharpe fraction + summary table."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

df_wf = pd.read_csv('results/walkforward_all_tickers.csv')
plots_dir = Path('results/plots/walkforward')
plots_dir.mkdir(parents=True, exist_ok=True)

# Bar chart: positive-test-Sharpe fraction
fig, axes = plt.subplots(2, 1, figsize=(10, 8))
tickers = df_wf['ticker'].tolist()
pos_frac = df_wf['positive_test_sharpe_frac'].values * 100
mean_sharpe = df_wf['mean_test_sharpe'].values
mean_ret = df_wf['mean_test_return'].values * 100
worst = df_wf['worst_test_return'].values * 100
consistency = df_wf['param_consistency'].values * 100

ax = axes[0]
x = np.arange(len(tickers))
bars = ax.bar(x, pos_frac, color='seagreen', alpha=0.85)
bars[5].set_color('darkorange')  # BTC
bars[6].set_color('darkorange')  # ETH
ax.axhline(50, color='red', linestyle='--', alpha=0.5, label='50% threshold')
ax.set_xticks(x)
ax.set_xticklabels(tickers, rotation=30, ha='right')
ax.set_ylabel('% test windows with Sharpe > 0')
ax.set_title('Walk-Forward Validation: Archer n=3,x=0.75 EMA-cross\n252d train / 63d test, rolling quarterly across 9 tickers')
ax.set_ylim(0, 100)
ax.grid(True, alpha=0.3, axis='y')
ax.legend(loc='lower right')
for i, v in enumerate(pos_frac):
    ax.text(i, v + 1, f'{v:.0f}%', ha='center', fontsize=9)

ax = axes[1]
ax.bar(x - 0.2, mean_sharpe, 0.4, label='Mean test Sharpe', color='steelblue', alpha=0.85)
ax.bar(x + 0.2, mean_ret / 10, 0.4, label='Mean test return / 10 (%)', color='coral', alpha=0.85)
ax.axhline(1.0, color='red', linestyle='--', alpha=0.5, label='Sharpe = 1.0')
ax.set_xticks(x)
ax.set_xticklabels(tickers, rotation=30, ha='right')
ax.set_ylabel('Sharpe / Return % (rescaled)')
ax.set_title('Mean test Sharpe and return per quarter (per ticker)')
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
out = plots_dir / 'walkforward_summary.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'Saved: {out}')

# Per-window plot for SPY
wf_spy = pd.read_csv('results/walkforward_SPY_1d.csv')
fig, ax = plt.subplots(figsize=(11, 5))
test_starts = wf_spy['test_start'].values
ax.plot(test_starts, wf_spy['test_sharpe'].values, 'o-', label='Test Sharpe', alpha=0.8)
ax.axhline(0, color='red', linewidth=0.5, alpha=0.5)
ax.fill_between(test_starts, 0, wf_spy['test_sharpe'].values,
                where=(wf_spy['test_sharpe'] > 0), color='green', alpha=0.2)
ax.fill_between(test_starts, 0, wf_spy['test_sharpe'].values,
                where=(wf_spy['test_sharpe'] < 0), color='red', alpha=0.2)
ax.set_xlabel('Test window start index')
ax.set_ylabel('Out-of-sample Sharpe')
ax.set_title('SPY 1d Walk-Forward (35 windows): test Sharpe per window\nGreen = positive, Red = negative')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
out = plots_dir / 'walkforward_SPY_per_window.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'Saved: {out}')
