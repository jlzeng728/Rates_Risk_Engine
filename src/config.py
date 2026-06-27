# -*- coding: utf-8 -*-
"""
Configuration
=============
*Yield curve tenors, FRED series mapping, bond portfolio definition, model
parameters, and filesystem paths.*

"""
from pathlib import Path

# FRED constant-maturity Treasury (CMT) par-yield series mapped to tenor in years.
# Insertion order is ascending tenor and is relied on downstream.
FRED_SERIES = {
    'DGS1MO': 1 / 12,
    'DGS3MO': 3 / 12,
    'DGS6MO': 6 / 12,
    'DGS1': 1.0,
    'DGS2': 2.0,
    'DGS3': 3.0,
    'DGS5': 5.0,
    'DGS7': 7.0,
    'DGS10': 10.0,
    'DGS20': 20.0,
    'DGS30': 30.0,
}
TENORS = list(FRED_SERIES.values())

START_DATE = '2016-01-01'
END_DATE = '2025-12-31'

# Bond portfolio. ``coupon`` is the annual coupon rate, ``maturity`` the
# remaining life in years, ``face`` the notional, ``freq`` coupons per year.
BOND_PORTFOLIO = [
    {'bond_id': 'UST_2Y',   'coupon': 0.0425, 'maturity': 2.0,  'face': 1_000_000, 'freq': 2},
    {'bond_id': 'UST_3Y',   'coupon': 0.0400, 'maturity': 3.0,  'face': 1_000_000, 'freq': 2},
    {'bond_id': 'UST_5Y',   'coupon': 0.0400, 'maturity': 5.0,  'face': 1_000_000, 'freq': 2},
    {'bond_id': 'UST_7Y',   'coupon': 0.0410, 'maturity': 7.0,  'face': 1_000_000, 'freq': 2},
    {'bond_id': 'UST_10Y',  'coupon': 0.0425, 'maturity': 10.0, 'face': 2_000_000, 'freq': 2},
    # 10Y Treasury STRIP (zero-coupon): Macaulay duration equals maturity in
    # closed form, used as an analytic benchmark for the duration calculation.
    {'bond_id': 'UST_10Y_STRIP', 'coupon': 0.0000, 'maturity': 10.0, 'face': 1_000_000, 'freq': 2},
    {'bond_id': 'UST_20Y',  'coupon': 0.0450, 'maturity': 20.0, 'face': 1_000_000, 'freq': 2},
    {'bond_id': 'UST_30Y',  'coupon': 0.0450, 'maturity': 30.0, 'face': 2_000_000, 'freq': 2},
    {'bond_id': 'CORP_5Y',  'coupon': 0.0550, 'maturity': 5.0,  'face': 1_000_000, 'freq': 2},
    {'bond_id': 'CORP_10Y', 'coupon': 0.0575, 'maturity': 10.0, 'face': 1_000_000, 'freq': 2},
]

COUPON_FREQ = 2

# Key-rate buckets (years) and the perturbation size used for DV01 / KRD.
KEY_RATE_TENORS = [2.0, 5.0, 10.0, 20.0, 30.0]
SHOCK_BP = 1.0

# Stress scenarios. Each maps a curve region to a shift in basis points.
# Regions: short (tenor <= 2y), mid (2y < tenor < 10y), long (tenor >= 10y).
STRESS_SCENARIOS = {
    'parallel_up_100':   {'short': 100, 'mid': 100, 'long': 100},
    'parallel_down_100': {'short': -100, 'mid': -100, 'long': -100},
    'steepener':         {'short': -50, 'mid': 0, 'long': 50},
    'flattener':         {'short': 50, 'mid': 0, 'long': -50},
    'butterfly':         {'short': 50, 'mid': -50, 'long': 50},
}

DB_PATH = Path('data/yield_curve.db')
SQL_SCHEMA_PATH = Path('sql/schema.sql')
FIGURES_DIR = Path('figures')
REPORT_PATH = Path('report/yield_curve_report.pdf')
