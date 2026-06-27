# -*- coding: utf-8 -*-
"""
Visualisation
=============
*Generate reporting figures from the yield curve, NSS fits, and stress
results. Outputs the par-yield surface, NSS fit panels, and stress P&L chart
as PNG files to the ``figures/`` directory. The PCA loadings figure is
produced separately by the R script.*

"""
from __future__ import annotations

import logging
import sqlite3

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import DB_PATH, FIGURES_DIR
from src.nss import nss_rate

__all__ = [
    "plot_yield_surface", "plot_nss_fit", "plot_stress_pnl", "main",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

COLORS = {
    'actual':   '#0072B2',
    'nss':      '#D55E00',
    'positive': '#009E73',
    'negative': '#CC2929',
}

FIGURES_DIR.mkdir(exist_ok=True)


def plot_yield_surface() -> None:
    """Heatmap of the par yield curve over time, highlighting inversion."""
    with sqlite3.connect(DB_PATH) as conn:
        yc = pd.read_sql("SELECT * FROM yield_curves ORDER BY date, tenor", conn)

    pivot = yc.pivot(index='tenor', columns='date', values='par_yield').sort_index()
    dates = pd.to_datetime(pivot.columns)

    fig, ax = plt.subplots(figsize=(14, 6))
    mesh = ax.pcolormesh(
        dates, pivot.index.values, pivot.values * 100,
        cmap='RdYlGn_r', shading='auto',
    )
    ax.set_yscale('log')
    ax.set_ylim(pivot.index.min(), pivot.index.max())
    ax.set_yticks([0.25, 0.5, 1, 2, 5, 10, 30])
    ax.set_yticklabels(['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y'])
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.set_title('US Treasury Par Yield Surface', fontsize=13, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Tenor')
    fig.colorbar(mesh, ax=ax, label='Par yield (%)')

    plt.tight_layout()
    out = FIGURES_DIR / '01_yield_surface.png'
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved {out}")


def _representative_dates(dates: list, n: int = 4) -> list:
    """Return ``n`` evenly spaced dates spanning the sample."""
    idx = np.linspace(0, len(dates) - 1, n).round().astype(int)
    return [dates[i] for i in idx]


def plot_nss_fit() -> None:
    """Four-panel comparison of NSS fitted curves against bootstrapped spots."""
    with sqlite3.connect(DB_PATH) as conn:
        sc = pd.read_sql("SELECT * FROM spot_curves ORDER BY date, tenor", conn)
        params = pd.read_sql("SELECT * FROM nss_params ORDER BY date", conn)

    params = params.set_index('date')
    panel_dates = _representative_dates(sorted(sc['date'].unique()))

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    grid = np.linspace(0.5, 30, 200)
    for ax, date in zip(axes.ravel(), panel_dates):
        curve = sc[sc['date'] == date]
        theta = params.loc[date, ['b0', 'b1', 'b2', 'b3', 'tau1', 'tau2']].values.astype(float)
        rmse = float(params.loc[date, 'rmse'])

        ax.scatter(curve['tenor'], curve['spot'] * 100, s=18,
                   color=COLORS['actual'], label='Bootstrapped spot', zorder=3)
        ax.plot(grid, nss_rate(grid, *theta) * 100,
                color=COLORS['nss'], linewidth=1.8, label='NSS fit', zorder=2)
        ax.set_title(f"{date}  (RMSE {rmse * 1e4:.1f} bp)", fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)

    for ax in axes[-1, :]:
        ax.set_xlabel('Tenor (years)')
    for ax in axes[:, 0]:
        ax.set_ylabel('Rate (%)')
    fig.suptitle('Nelson-Siegel-Svensson Fit vs Bootstrapped Spot Curve',
                 fontsize=13, fontweight='bold')

    plt.tight_layout()
    out = FIGURES_DIR / '02_nss_fit.png'
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved {out}")


def plot_stress_pnl() -> None:
    """Bar chart of portfolio P&L under each stress scenario."""
    with sqlite3.connect(DB_PATH) as conn:
        st = pd.read_sql(
            "SELECT scenario, SUM(pnl) AS pnl FROM stress_results GROUP BY scenario", conn,
        )
    if st.empty:
        logger.warning("stress_results empty; run stress.py first")
        return

    st = st.sort_values('pnl')
    colors = [COLORS['negative'] if v < 0 else COLORS['positive'] for v in st['pnl']]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(st['scenario'], st['pnl'] / 1e3, color=colors,
                  alpha=0.85, edgecolor='black')
    ax.axhline(0, color='black', linewidth=0.8)

    for bar, value in zip(bars, st['pnl']):
        offset = 3 if value >= 0 else -3
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + offset * 0.0,
                f"${value / 1e3:,.0f}k", ha='center',
                va='bottom' if value >= 0 else 'top', fontsize=10, fontweight='bold')

    ax.set_ylabel('Portfolio P&L ($000s)')
    ax.set_title('Stress Scenario Portfolio P&L', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    plt.xticks(rotation=20)

    plt.tight_layout()
    out = FIGURES_DIR / '04_stress_pnl.png'
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved {out}")


def main() -> None:
    """Generate the Python reporting figures."""
    logger.info("Generating figures")
    plot_yield_surface()
    plot_nss_fit()
    plot_stress_pnl()
    logger.info("Done")


if __name__ == '__main__':
    main()
