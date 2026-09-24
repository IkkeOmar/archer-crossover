"""Synthetic-market null control plots."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Re-run the 30-sim synthetic test and save data + plots
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.synthetic import gbm, trending, mean_reverting, regime_switching, block_bootstrap
from src.archer_engine import backtest_arrows, buy_and_hold
from src.data_loader import fetch_yfinance

PARAMS = {'n_mu': 3, 'x_zero': 0.75, 'fast_period': 9, 'slow_period': 21, 'bear_alloc': 1.0}
N = 2500
N_SIMS = 50

df = fetch_yfinance('SPY', '1d', start='2015-01-01', end='2024-12-31')
spy_returns = np.log(df['close'] / df['close'].shift(1)).dropna()

tests = {
    'Pure GBM': lambda seed: gbm(n=N, mu=0.0, sigma=0.02, seed=seed).values,
    'Trending (mild)': lambda seed: trending(n=N, annual_drift=0.10, annual_vol=0.15, seed=seed).values,
    'Trending (strong)': lambda seed: trending(n=N, annual_drift=0.20, annual_vol=0.20, seed=seed).values,
    'Mean-reverting': lambda seed: mean_reverting(n=N, speed=0.05, sigma=0.02, seed=seed).values,
    'Regime-switching': lambda seed: regime_switching(n=N, seed=seed).values,
    'Block bootstrap (SPY)': lambda seed: block_bootstrap(spy_returns, n=N, block_size=20, seed=seed).values,
}

records = []
for name, gen in tests.items():
    for s in range(N_SIMS):
        prices = gen(s)
        arch = backtest_arrows(prices, **PARAMS)
        bh = buy_and_hold(prices)
        records.append({
            'market': name,
            'sim': s,
            'archer_return': arch.total_return,
            'bh_return': bh.total_return,
            'archer_n_trades': arch.n_trades,
        })

df_sim = pd.DataFrame(records)
df_sim.to_csv('results/synthetic_null_control.csv', index=False)
print(f'Saved: results/synthetic_null_control.csv ({len(df_sim)} rows)')

plots_dir = Path('results/plots/synthetic')
plots_dir.mkdir(parents=True, exist_ok=True)

fig, ax = plt.subplots(figsize=(11, 5.5))
markets = list(tests.keys())
positions = np.arange(len(markets))
width = 0.35

arch_means = [df_sim[df_sim['market']==m]['archer_return'].mean() * 100 for m in markets]
arch_stds = [df_sim[df_sim['market']==m]['archer_return'].std() * 100 for m in markets]
bh_means = [df_sim[df_sim['market']==m]['bh_return'].mean() * 100 for m in markets]
bh_stds = [df_sim[df_sim['market']==m]['bh_return'].std() * 100 for m in markets]

ax.bar(positions - width/2, arch_means, width, yerr=arch_stds, capsize=3, label='Archer', color='seagreen', alpha=0.85)
ax.bar(positions + width/2, bh_means, width, yerr=bh_stds, capsize=3, label='Buy & Hold', color='steelblue', alpha=0.85)
ax.set_xticks(positions)
ax.set_xticklabels(markets, rotation=20, ha='right', fontsize=9)
ax.set_ylabel('Mean total return (%) over 50 sims')
ax.set_title('Phase 3 -- Synthetic Market Null Control\nArcher n=3,x=0.75 vs Buy & Hold on 6 market types (50 sims each)')
ax.axhline(0, color='black', linewidth=0.5)
ax.grid(True, alpha=0.3, axis='y')
ax.legend()
plt.tight_layout()
out = plots_dir / 'synthetic_null_control.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'Saved: {out}')

# Summary table as PNG
fig, ax = plt.subplots(figsize=(10, 4))
ax.axis('off')
table_data = []
table_data.append(['Market type', 'Archer mean', 'Archer std', 'B&H mean', 'B&H std', 'Edge (A-B)', 'A>B?'])
for m in markets:
    a_m = df_sim[df_sim['market']==m]['archer_return'].mean() * 100
    a_s = df_sim[df_sim['market']==m]['archer_return'].std() * 100
    b_m = df_sim[df_sim['market']==m]['bh_return'].mean() * 100
    b_s = df_sim[df_sim['market']==m]['bh_return'].std() * 100
    edge = a_m - b_m
    table_data.append([m, f'{a_m:+.1f}%', f'{a_s:.1f}%', f'{b_m:+.1f}%', f'{b_s:.1f}%', f'{edge:+.1f} pp', 'YES' if edge > 0 else 'no'])
table = ax.table(cellText=table_data, loc='center', cellLoc='center', colWidths=[0.22, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13])
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.0, 1.5)
for i in range(len(table_data[0])):
    cell = table[(0, i)]
    cell.set_facecolor('#404040')
    cell.set_text_props(color='white', weight='bold')
plt.tight_layout()
out = plots_dir / 'synthetic_summary_table.png'
plt.savefig(out, dpi=130)
plt.close()
print(f'Saved: {out}')
