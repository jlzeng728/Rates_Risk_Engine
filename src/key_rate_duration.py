# -*- coding: utf-8 -*-
"""
DV01 and Key Rate Duration
===========================
*Compute each bond's dollar value of a basis point under a parallel curve
shift and its key rate durations under localised, tent-shaped shifts at the
configured key tenors, then update the analytics table.*

"""
from __future__ import annotations

import logging
import sqlite3

import numpy as np
import pandas as pd

from src.bond_analytics import cash_flows, price_off_curve, spot_interpolator
from src.config import DB_PATH, KEY_RATE_TENORS, SHOCK_BP

__all__ = ["tent_shift", "key_rate_durations", "curve_dv01", "main"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def tent_shift(tenors, key, key_tenors, shock_bp: float = SHOCK_BP) -> np.ndarray:
    """Build a tent-shaped spot shift peaking at one key tenor.

    The shift equals ``shock_bp`` at ``key`` and decays linearly to zero at the
    adjacent key tenors, so summing the shifts over all key tenors reproduces a
    parallel shift across the covered range.

    Parameters
    ----------
    tenors : array-like
        Curve maturities to shift.
    key : float
        Key tenor at which the shift peaks.
    key_tenors : list of float
        All key tenors, used to locate the neighbouring anchors.
    shock_bp : float, optional
        Peak shift in basis points (default :data:`SHOCK_BP`).

    Returns
    -------
    out : numpy.ndarray
        Additive spot shift (decimal) at each tenor.
    """
    tenors = np.asarray(tenors, dtype=float)
    shift = shock_bp * 1e-4
    lower = max([k for k in key_tenors if k < key], default=key)
    upper = min([k for k in key_tenors if k > key], default=key)

    out = np.zeros_like(tenors)
    for i, t in enumerate(tenors):
        if t == key:
            out[i] = shift
        elif lower < t < key:
            out[i] = shift * (t - lower) / (key - lower)
        elif key < t < upper:
            out[i] = shift * (upper - t) / (upper - key)
    return out


def curve_dv01(times, amounts, tenors, spots, base_price, shock_bp: float = SHOCK_BP) -> float:
    """Compute DV01 by fully repricing under a parallel ``shock_bp`` shift.

    Parameters
    ----------
    times, amounts : numpy.ndarray
        Bond cash flow schedule.
    tenors, spots : array-like
        Base spot curve.
    base_price : float
        Bond price on the unshifted curve.
    shock_bp : float, optional
        Parallel shift in basis points.

    Returns
    -------
    out : float
        Price change per basis point (positive for a long bond).
    """
    shifted = spot_interpolator(tenors, np.asarray(spots) + shock_bp * 1e-4)
    bumped_price = price_off_curve(times, amounts, shifted)
    return -(bumped_price - base_price) / shock_bp


def key_rate_durations(times, amounts, tenors, spots, base_price,
                       key_tenors=KEY_RATE_TENORS, shock_bp: float = SHOCK_BP) -> dict:
    """Compute key rate durations by repricing under each tent-shaped shift.

    Parameters
    ----------
    times, amounts : numpy.ndarray
        Bond cash flow schedule.
    tenors, spots : array-like
        Base spot curve.
    base_price : float
        Bond price on the unshifted curve.
    key_tenors : list of float, optional
        Key tenors to bump.
    shock_bp : float, optional
        Peak shift in basis points.

    Returns
    -------
    out : dict
        Mapping from key tenor to price change per basis point.
    """
    spots = np.asarray(spots, dtype=float)
    krd = {}
    for key in key_tenors:
        shifted = spot_interpolator(tenors, spots + tent_shift(tenors, key, key_tenors, shock_bp))
        bumped_price = price_off_curve(times, amounts, shifted)
        krd[key] = -(bumped_price - base_price) / shock_bp
    return krd


def main() -> None:
    """Compute DV01 and key rate durations and update the analytics table."""
    logger.info("Computing DV01 and key rate durations")
    with sqlite3.connect(DB_PATH) as conn:
        sc = pd.read_sql("SELECT * FROM spot_curves ORDER BY date, tenor", conn)
        bonds = pd.read_sql("SELECT * FROM bonds", conn).to_dict('records')
        valuation_date = pd.read_sql("SELECT MAX(date) AS d FROM bond_analytics", conn)['d'].iloc[0]

    curve = sc[sc['date'] == valuation_date]
    tenors = curve['tenor'].values
    spots = curve['spot'].values
    base_fn = spot_interpolator(tenors, spots)

    summary = []
    with sqlite3.connect(DB_PATH) as conn:
        for bond in bonds:
            times, amounts = cash_flows(bond)
            base_price = price_off_curve(times, amounts, base_fn)
            dv01 = curve_dv01(times, amounts, tenors, spots, base_price)
            krd = key_rate_durations(times, amounts, tenors, spots, base_price)

            conn.execute(
                "UPDATE bond_analytics SET krd_2y=?, krd_5y=?, krd_10y=?, krd_20y=?, krd_30y=? "
                "WHERE date=? AND bond_id=?",
                (krd[2.0], krd[5.0], krd[10.0], krd[20.0], krd[30.0],
                 valuation_date, bond['bond_id']),
            )
            summary.append({
                'bond_id': bond['bond_id'], 'dv01_parallel': dv01,
                'krd_sum': sum(krd.values()),
            })
        conn.commit()

    summary_df = pd.DataFrame(summary)
    summary_df['abs_err'] = (summary_df['dv01_parallel'] - summary_df['krd_sum']).abs()
    logger.info(f"Valuation date {valuation_date}")
    logger.info("Additivity check (sum of KRD should match parallel DV01):")
    logger.info("\n%s", summary_df.round(2).to_string(index=False))
    logger.info(f"Max additivity error: {summary_df['abs_err'].max():.4f} per bp")
    logger.info("Done")


if __name__ == '__main__':
    main()
