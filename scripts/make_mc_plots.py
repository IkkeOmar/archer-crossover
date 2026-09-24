"""Make Monte Carlo distribution plots per ticker."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

results_dir = Path('results')
plots_dir = results_dir / 'plots' / 'mc'
plots_dir.mkdir(parents=True, exist_ok=True)

df_mc = pd.read_csv('results/monte_carlo_archer_n3_x075.csv')

fig, axes = plt.subplots(2, 1, figsize=(10, 8))
tickers = df_mc['ticker'].tolist()
sharpe_means = df_mc['mc_sharpe_mean'].values
sharpe_stds = df_mc['mc_sharpe_std'].values
return_means = df_mc['mc_return_mean'].values * 100
return_stds = df_mc['mc_return_std'].values * 100

ax = axes[0]
x = np.arange(len(tickers))
ax.bar(x, sharpe_means, yerr=sharpe_stds, capsize=5, color='steelblue', alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels(tickers, rotation=45, ha='right')
ax.set_ylabel('Mean Sharpe')
ax.set_title('Monte Carlo Sharpe mean +/- std (100 sims, Archer n=3,x=0.75)')
ax.axhline(0.7, color='gray', linestyle='--', alpha=0.5, label='Sharpe 0.7')
ax.grid(True, alpha=0.3)
ax.legend()

ax = axes[1]
ax.bar(x, return_means, yerr=return_stds, capsize=5, color='darkorange', alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels(tickers, rotation=45, ha='right')
ax.set_ylabel('Mean total return (%)')
ax.set_title('Monte Carlo total return mean +/- std')
ax.grid(True, alpha=0.3)

plt.tight_layout()
out = plots_dir / 'mc_summary_bars.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'Saved: {out}')

# Robust Sharpe plot
fig, ax = plt.subplots(figsize=(8, 5))
robust = df_mc['mc_robust_sharpe'].values
ax.barh(tickers, robust, color='seagreen', alpha=0.8)
ax.set_xlabel('Robust Sharpe (mean / std across 100 sims)')
ax.set_title('Robust Sharpe per ticker -- higher = more stable edge\n(threshold for "stable": > 1.0)')
ax.axvline(1.0, color='red', linestyle='--', alpha=0.7, label='Threshold = 1.0')
for i, v in enumerate(robust):
    ax.text(v + 2, i, f'{v:.1f}', va='center', fontsize=9)
ax.legend()
ax.grid(True, alpha=0.3, axis='x')
plt.tight_layout()
out = plots_dir / 'mc_robust_sharpe.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'Saved: {out}')
