# -*- coding: utf-8 -*-
"""
Stress Scenarios
================
*Apply parallel, steepener, flattener, and butterfly shocks to the spot
curve, fully reprice every bond, and persist the per-bond and portfolio
profit and loss under each scenario.*

"""
from __future__ import annotations

import logging
import sqlite3

import numpy as np
import pandas as pd

from src.bond_analytics import cash_flows, price_off_curve, spot_interpolator
from src.config import DB_PATH, STRESS_SCENARIOS

__all__ = ["region_shift", "main"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def region_shift(tenors, scenario: dict) -> np.ndarray:
    """Map a region-based scenario to an additive spot shift per tenor.

    Tenors are bucketed as short (<= 2y), long (>= 10y), or mid (in between),
    and each bucket receives the scenario's basis-point shift.

    Parameters
    ----------
    tenors : array-like
        Curve maturities.
    scenario : dict
        Mapping with keys ``short, mid, long`` giving shifts in basis points.

    Returns
    -------
    out : numpy.ndarray
        Additive spot shift (decimal) at each tenor.
    """
    tenors = np.asarray(tenors, dtype=float)
    shift = np.empty_like(tenors)
    short = tenors <= 2.0
    long_ = tenors >= 10.0
    mid = ~short & ~long_
    shift[short] = scenario['short'] * 1e-4
    shift[mid] = scenario['mid'] * 1e-4
    shift[long_] = scenario['long'] * 1e-4
    return shift


def main() -> None:
    """Reprice the portfolio under each stress scenario and persist P&L."""
    logger.info("Running stress scenarios")
    with sqlite3.connect(DB_PATH) as conn:
        sc = pd.read_sql("SELECT * FROM spot_curves ORDER BY date, tenor", conn)
        bonds = pd.read_sql("SELECT * FROM bonds", conn).to_dict('records')

    valuation_date = sc['date'].max()
    curve = sc[sc['date'] == valuation_date]
    tenors = curve['tenor'].values
    spots = curve['spot'].values
    base_fn = spot_interpolator(tenors, spots)

    schedules = {b['bond_id']: cash_flows(b) for b in bonds}
    base_price = {bid: price_off_curve(t, c, base_fn) for bid, (t, c) in schedules.items()}

    rows = []
    for name, scenario in STRESS_SCENARIOS.items():
        shifted_fn = spot_interpolator(tenors, spots + region_shift(tenors, scenario))
        for bid, (times, amounts) in schedules.items():
            shocked = price_off_curve(times, amounts, shifted_fn)
            rows.append({
                'scenario': name, 'bond_id': bid,
                'base_price': base_price[bid], 'shocked_price': shocked,
                'pnl': shocked - base_price[bid],
            })
    results = pd.DataFrame(rows)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM stress_results")
        results.to_sql('stress_results', conn, if_exists='append', index=False)

    pivot = results.pivot_table(index='scenario', values='pnl', aggfunc='sum')
    pivot = pivot.reindex(STRESS_SCENARIOS.keys())
    logger.info(f"Valuation date {valuation_date}, portfolio stress P&L:")
    for scenario, pnl in pivot['pnl'].items():
        logger.info(f"  {scenario:<18} {pnl:>14,.0f}")
    logger.info("Done")


if __name__ == '__main__':
    main()
