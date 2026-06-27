# -*- coding: utf-8 -*-
"""
Nelson-Siegel-Svensson Calibration
===================================
*Fit the six-parameter Nelson-Siegel-Svensson functional form to each
bootstrapped spot curve by nonlinear least squares, and persist the
parameters and fit error for every date.*

"""
from __future__ import annotations

import logging
import sqlite3

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from src.config import DB_PATH

__all__ = ["nss_rate", "fit_nss", "main"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

PARAM_NAMES = ['b0', 'b1', 'b2', 'b3', 'tau1', 'tau2']


def nss_rate(t, b0, b1, b2, b3, tau1, tau2):
    """Evaluate the Nelson-Siegel-Svensson spot rate.

    Parameters
    ----------
    t : float or numpy.ndarray
        Maturity in years (must be positive).
    b0, b1, b2, b3 : float
        Level, slope, and two curvature coefficients.
    tau1, tau2 : float
        Decay parameters for the two curvature terms.

    Returns
    -------
    out : float or numpy.ndarray
        Spot rate at ``t``.
    """
    t = np.asarray(t, dtype=float)
    x1 = t / tau1
    x2 = t / tau2
    term1 = (1.0 - np.exp(-x1)) / x1
    term2 = term1 - np.exp(-x1)
    term3 = (1.0 - np.exp(-x2)) / x2 - np.exp(-x2)
    return b0 + b1 * term1 + b2 * term2 + b3 * term3


def fit_nss(tenors, spots):
    """Calibrate NSS parameters to one spot curve.

    Parameters
    ----------
    tenors : array-like
        Maturities in years.
    spots : array-like
        Continuously compounded spot rates at ``tenors``.

    Returns
    -------
    params : numpy.ndarray
        Fitted ``[b0, b1, b2, b3, tau1, tau2]``.
    rmse : float
        Root mean squared residual of the fit.
    """
    tenors = np.asarray(tenors, dtype=float)
    spots = np.asarray(spots, dtype=float)

    def residuals(theta):
        return nss_rate(tenors, *theta) - spots

    x0 = [spots[-1], spots[0] - spots[-1], 0.0, 0.0, 2.0, 5.0]
    lower = [-1.0, -1.0, -1.0, -1.0, 0.05, 0.05]
    upper = [1.0, 1.0, 1.0, 1.0, 30.0, 30.0]

    sol = least_squares(
        residuals, x0, bounds=(lower, upper), method='trf', max_nfev=10000,
    )
    rmse = float(np.sqrt(np.mean(sol.fun ** 2)))
    return sol.x, rmse


def main() -> None:
    """Fit NSS to every dated spot curve and persist parameters."""
    logger.info("Calibrating Nelson-Siegel-Svensson curves")
    with sqlite3.connect(DB_PATH) as conn:
        sc = pd.read_sql("SELECT * FROM spot_curves ORDER BY date, tenor", conn)

    rows = []
    for date, group in sc.groupby('date'):
        params, rmse = fit_nss(group['tenor'].values, group['spot'].values)
        record = {'date': date}
        record.update(dict(zip(PARAM_NAMES, params)))
        record['rmse'] = rmse
        rows.append(record)
    params_df = pd.DataFrame(rows)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM nss_params")
        params_df.to_sql('nss_params', conn, if_exists='append', index=False)

    logger.info(f"Fitted {len(params_df):,} curves")
    logger.info(f"  median RMSE: {params_df['rmse'].median() * 1e4:.2f} bp")
    logger.info(f"  max RMSE:    {params_df['rmse'].max() * 1e4:.2f} bp")
    latest = params_df.iloc[-1]
    logger.info(f"  latest {latest['date']}: b0={latest['b0']:.4f} b1={latest['b1']:.4f} "
                f"b2={latest['b2']:.4f} b3={latest['b3']:.4f} "
                f"tau1={latest['tau1']:.2f} tau2={latest['tau2']:.2f}")
    logger.info("Done")


if __name__ == '__main__':
    main()
