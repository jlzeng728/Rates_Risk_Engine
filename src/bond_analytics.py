# -*- coding: utf-8 -*-
"""
Bond Pricing and Analytics
==========================
*Price each bond by discounting its cash flows off the bootstrapped spot
curve, solve for yield to maturity, and compute Macaulay duration, modified
duration, convexity, and analytic DV01.*

"""
from __future__ import annotations

import logging
import sqlite3

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from src.config import BOND_PORTFOLIO, DB_PATH

__all__ = [
    "cash_flows", "spot_interpolator", "price_off_curve",
    "yield_to_maturity", "duration_convexity", "main",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def cash_flows(bond: dict):
    """Return the cash flow schedule of a bond.

    Parameters
    ----------
    bond : dict
        Bond record with keys ``coupon, maturity, face, freq``.

    Returns
    -------
    times : numpy.ndarray
        Payment times in years.
    amounts : numpy.ndarray
        Cash flow amounts (coupons plus face at maturity).
    """
    n = int(round(bond['maturity'] * bond['freq']))
    times = np.arange(1, n + 1) / bond['freq']
    amounts = np.full(n, bond['face'] * bond['coupon'] / bond['freq'])
    amounts[-1] += bond['face']
    return times, amounts


def spot_interpolator(tenors, spots) -> PchipInterpolator:
    """Build a monotone interpolator over a spot curve, allowing extrapolation.

    Parameters
    ----------
    tenors : array-like
        Maturities in years.
    spots : array-like
        Continuously compounded spot rates.

    Returns
    -------
    out : scipy.interpolate.PchipInterpolator
        Callable spot rate function.
    """
    return PchipInterpolator(np.asarray(tenors, float), np.asarray(spots, float),
                             extrapolate=True)


def price_off_curve(times, amounts, spot_fn) -> float:
    """Price cash flows by discounting at the curve's continuous spot rates.

    Parameters
    ----------
    times : numpy.ndarray
        Payment times in years.
    amounts : numpy.ndarray
        Cash flow amounts.
    spot_fn : callable
        Function mapping maturity to continuously compounded spot rate.

    Returns
    -------
    out : float
        Present value of the cash flows.
    """
    z = spot_fn(times)
    return float(np.sum(amounts * np.exp(-z * times)))


def yield_to_maturity(times, amounts, price) -> float:
    """Solve for the continuously compounded yield to maturity.

    Parameters
    ----------
    times : numpy.ndarray
        Payment times in years.
    amounts : numpy.ndarray
        Cash flow amounts.
    price : float
        Present value to match.

    Returns
    -------
    out : float
        Yield to maturity (continuous compounding).
    """
    return brentq(lambda y: np.sum(amounts * np.exp(-y * times)) - price, -0.05, 0.50)


def duration_convexity(times, amounts, ytm, price):
    """Compute Macaulay duration, modified duration, and convexity.

    Under continuous compounding modified duration equals Macaulay duration.

    Parameters
    ----------
    times : numpy.ndarray
        Payment times in years.
    amounts : numpy.ndarray
        Cash flow amounts.
    ytm : float
        Continuously compounded yield to maturity.
    price : float
        Present value of the cash flows.

    Returns
    -------
    mac_dur : float
        Macaulay duration in years.
    mod_dur : float
        Modified duration in years.
    convexity : float
        Convexity in years squared.
    """
    pv = amounts * np.exp(-ytm * times)
    mac_dur = float(np.sum(times * pv) / price)
    mod_dur = mac_dur
    convexity = float(np.sum(times ** 2 * pv) / price)
    return mac_dur, mod_dur, convexity


def main() -> None:
    """Price every bond on the latest curve and persist analytics."""
    logger.info("Computing bond pricing and analytics")
    with sqlite3.connect(DB_PATH) as conn:
        sc = pd.read_sql("SELECT * FROM spot_curves ORDER BY date, tenor", conn)
        bonds = pd.read_sql("SELECT * FROM bonds", conn).to_dict('records')

    valuation_date = sc['date'].max()
    curve = sc[sc['date'] == valuation_date]
    spot_fn = spot_interpolator(curve['tenor'].values, curve['spot'].values)

    rows = []
    for bond in bonds:
        times, amounts = cash_flows(bond)
        price = price_off_curve(times, amounts, spot_fn)
        ytm = yield_to_maturity(times, amounts, price)
        mac_dur, mod_dur, convexity = duration_convexity(times, amounts, ytm, price)
        dv01 = mod_dur * price * 1e-4
        rows.append({
            'date': valuation_date, 'bond_id': bond['bond_id'],
            'price': price, 'ytm': ytm,
            'mac_dur': mac_dur, 'mod_dur': mod_dur,
            'convexity': convexity, 'dv01': dv01,
            'krd_2y': None, 'krd_5y': None, 'krd_10y': None,
            'krd_20y': None, 'krd_30y': None,
        })
    analytics = pd.DataFrame(rows)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM bond_analytics WHERE date=?", (valuation_date,))
        analytics.to_sql('bond_analytics', conn, if_exists='append', index=False)

    logger.info(f"Priced {len(analytics)} bonds on {valuation_date}")
    show = analytics[['bond_id', 'price', 'ytm', 'mod_dur', 'convexity', 'dv01']].copy()
    show['ytm'] = (show['ytm'] * 100).round(3)
    logger.info("\n%s", show.round(2).to_string(index=False))
    logger.info("Done")


if __name__ == '__main__':
    main()
