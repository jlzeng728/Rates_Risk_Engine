# -*- coding: utf-8 -*-
"""
Unit Tests
==========
*Self-contained checks of the bootstrap, NSS, pricing, and key rate duration
routines against analytic benchmarks. These do not require the database or a
network connection.*

"""
from __future__ import annotations

import numpy as np

from src.bond_analytics import (
    cash_flows, duration_convexity, price_off_curve, spot_interpolator,
    yield_to_maturity,
)
from src.bootstrap import bootstrap_curve
from src.key_rate_duration import curve_dv01, key_rate_durations, tent_shift
from src.nss import fit_nss, nss_rate


# Use a single tenor grid for tests.
TENORS = [0.5, 1, 2, 3, 5, 7, 10, 20, 30]


def test_bootstrap_reprices_par_bonds():
    """Discount factors must reprice the input par bonds back to par."""
    par = np.full(len(TENORS), 0.04)
    grid, spot, forward, disc = bootstrap_curve(TENORS, par, freq=2)

    # Flat 4% par yield bonds discounted by the recovered factors equal par.
    for n in range(1, len(grid) + 1):
        coupon = 0.04 / 2
        price = coupon * disc[:n].sum() + disc[n - 1]
        assert abs(price - 1.0) < 1e-9


def test_bootstrap_flat_curve_spot_equals_par():
    """A flat par curve implies an (almost) flat continuous spot curve."""
    par = np.full(len(TENORS), 0.04)
    _, spot, _, disc = bootstrap_curve(TENORS, par, freq=2)
    # Continuous spot of a 4% semiannual par bond ~ 2*ln(1.02) = 3.96%.
    expected = 2 * np.log(1 + 0.04 / 2)
    assert np.allclose(spot, expected, atol=5e-4)


def test_zero_coupon_duration_equals_maturity():
    """Macaulay duration of a zero-coupon bond equals its maturity."""
    bond = {'coupon': 0.0, 'maturity': 10.0, 'face': 1_000_000, 'freq': 2}
    times, amounts = cash_flows(bond)
    spot_fn = spot_interpolator(TENORS, np.full(len(TENORS), 0.04))
    price = price_off_curve(times, amounts, spot_fn)
    ytm = yield_to_maturity(times, amounts, price)
    mac, mod, conv = duration_convexity(times, amounts, ytm, price)
    assert abs(mac - 10.0) < 1e-6
    assert abs(conv - 100.0) < 1e-6


def test_nss_recovers_its_own_parameters():
    """Fitting NSS to data it generated recovers the rates exactly."""
    true = [0.04, -0.01, 0.02, -0.01, 1.5, 6.0]
    grid = np.array([0.5, 1, 2, 3, 5, 7, 10, 20, 30])
    rates = nss_rate(grid, *true)
    _, rmse = fit_nss(grid, rates)
    assert rmse < 1e-6


def test_tent_shift_sums_to_parallel():
    """Tent shifts over all key tenors sum to a flat shift across the range."""
    tenors = np.array([2.0, 3.5, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0])
    keys = [2.0, 5.0, 10.0, 20.0, 30.0]
    total = sum(tent_shift(tenors, k, keys, shock_bp=1.0) for k in keys)
    assert np.allclose(total, 1.0 * 1e-4)


def test_krd_sum_matches_parallel_dv01():
    """Sum of key rate durations reconciles to the parallel DV01."""
    bond = {'coupon': 0.04, 'maturity': 10.0, 'face': 1_000_000, 'freq': 2}
    tenors = np.array([2.0, 5.0, 10.0, 20.0, 30.0])
    spots = np.array([0.030, 0.035, 0.040, 0.043, 0.045])
    times, amounts = cash_flows(bond)
    base_fn = spot_interpolator(tenors, spots)
    base_price = price_off_curve(times, amounts, base_fn)

    dv01 = curve_dv01(times, amounts, tenors, spots, base_price)
    krd = key_rate_durations(times, amounts, tenors, spots, base_price)
    assert abs(sum(krd.values()) - dv01) < 0.05
