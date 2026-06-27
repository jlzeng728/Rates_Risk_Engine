# -*- coding: utf-8 -*-
"""
Yield Curve Bootstrap
=====================
*Convert par yields into spot (zero) rates and forward rates by forward
substitution on a semiannual grid, then persist the spot, forward, and
discount-factor curve for every date.*

"""
from __future__ import annotations

import logging
import sqlite3

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

from src.config import COUPON_FREQ, DB_PATH

__all__ = ["bootstrap_curve", "main"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def bootstrap_curve(tenors, par_yields, freq: int = COUPON_FREQ):
    """Bootstrap a single spot/forward curve from par yields.

    The input par yields are interpolated onto a regular ``1/freq``-spaced
    grid with a monotone cubic spline, then discount factors are obtained by
    forward substitution on the par-bond pricing identity

        1 = (c / freq) * sum_{i=1}^{n} D(t_i) + D(t_n).

    Parameters
    ----------
    tenors : array-like
        Observed maturities in years.
    par_yields : array-like
        Par yields (decimal) at ``tenors``.
    freq : int, optional
        Coupon payments per year (default :data:`COUPON_FREQ`).

    Returns
    -------
    grid : numpy.ndarray
        Semiannual maturity grid.
    spot : numpy.ndarray
        Continuously compounded zero rates.
    forward : numpy.ndarray
        Continuously compounded forward rates over each grid interval.
    disc : numpy.ndarray
        Discount factors.
    """
    tenors = np.asarray(tenors, dtype=float)
    par_yields = np.asarray(par_yields, dtype=float)

    spline = PchipInterpolator(tenors, par_yields)
    n_steps = int(round(float(tenors.max()) * freq))
    grid = np.arange(1, n_steps + 1) / freq
    par = spline(grid)

    dt = 1.0 / freq
    disc = np.empty_like(grid)
    running_sum = 0.0
    for i, c in enumerate(par):
        coupon = c * dt
        disc[i] = (1.0 - coupon * running_sum) / (1.0 + coupon)
        running_sum += disc[i]

    spot = -np.log(disc) / grid

    forward = np.empty_like(grid)
    forward[0] = spot[0]
    forward[1:] = (np.log(disc[:-1]) - np.log(disc[1:])) / dt

    return grid, spot, forward, disc


def main() -> None:
    """Bootstrap every dated par curve in the database and persist the result."""
    logger.info("Bootstrapping spot and forward curves")
    with sqlite3.connect(DB_PATH) as conn:
        yc = pd.read_sql("SELECT * FROM yield_curves ORDER BY date, tenor", conn)

    frames = []
    for date, group in yc.groupby('date'):
        grid, spot, forward, disc = bootstrap_curve(
            group['tenor'].values, group['par_yield'].values,
        )
        frames.append(pd.DataFrame({
            'date': date, 'tenor': grid,
            'spot': spot, 'forward': forward, 'disc': disc,
        }))
    spot_df = pd.concat(frames, ignore_index=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM spot_curves")
        spot_df.to_sql('spot_curves', conn, if_exists='append', index=False)
    logger.info(
        f"Bootstrapped {yc['date'].nunique():,} dates into {len(spot_df):,} rows "
        f"(grid size {spot_df['tenor'].nunique()})"
    )

    latest = spot_df[spot_df['date'] == spot_df['date'].max()]
    logger.info(f"Latest curve {spot_df['date'].max()}:")
    for t in (1.0, 2.0, 5.0, 10.0, 30.0):
        row = latest[np.isclose(latest['tenor'], t)]
        if not row.empty:
            logger.info(f"  {t:>4.0f}y  spot {row['spot'].iloc[0]:.4%}  disc {row['disc'].iloc[0]:.4f}")
    logger.info("Done")


if __name__ == '__main__':
    main()
