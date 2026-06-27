CREATE TABLE IF NOT EXISTS yield_curves(
    date TEXT NOT NULL,
    tenor REAL NOT NULL,        -- maturity in years
    par_yield REAL,             -- CMT par yield as a decimal
    PRIMARY KEY (date, tenor)
);

CREATE TABLE IF NOT EXISTS spot_curves(
    date TEXT NOT NULL,
    tenor REAL NOT NULL,        -- maturity in years (semiannual grid)
    spot REAL,                  -- continuously compounded zero rate
    forward REAL,               -- continuously compounded forward rate
    disc REAL,                  -- discount factor
    PRIMARY KEY (date, tenor)
);

CREATE TABLE IF NOT EXISTS nss_params(
    date TEXT NOT NULL,
    b0 REAL,                    -- long-run level
    b1 REAL,                    -- short-end slope
    b2 REAL,                    -- first curvature
    b3 REAL,                    -- second curvature
    tau1 REAL,                  -- first decay
    tau2 REAL,                  -- second decay
    rmse REAL,                  -- fit error vs bootstrapped spot curve
    PRIMARY KEY (date)
);

CREATE TABLE IF NOT EXISTS bonds(
    bond_id TEXT NOT NULL,
    coupon REAL,
    maturity REAL,
    face REAL,
    freq INTEGER,
    PRIMARY KEY (bond_id)
);

CREATE TABLE IF NOT EXISTS bond_analytics(
    date TEXT NOT NULL,
    bond_id TEXT NOT NULL,
    price REAL,
    ytm REAL,
    mac_dur REAL,
    mod_dur REAL,
    convexity REAL,
    dv01 REAL,
    krd_2y REAL,
    krd_5y REAL,
    krd_10y REAL,
    krd_20y REAL,
    krd_30y REAL,
    PRIMARY KEY (date, bond_id)
);

CREATE TABLE IF NOT EXISTS pca_factors(
    tenor REAL NOT NULL,
    pc1 REAL,                   -- level loading
    pc2 REAL,                   -- slope loading
    pc3 REAL,                   -- curvature loading
    PRIMARY KEY (tenor)
);

CREATE TABLE IF NOT EXISTS pca_variance(
    pc INTEGER NOT NULL,        -- 1, 2, 3, ...
    eigenvalue REAL,
    explained REAL,             -- fraction of variance explained
    cumulative REAL,
    PRIMARY KEY (pc)
);

CREATE TABLE IF NOT EXISTS stress_results(
    scenario TEXT NOT NULL,
    bond_id TEXT NOT NULL,
    base_price REAL,
    shocked_price REAL,
    pnl REAL,
    PRIMARY KEY (scenario, bond_id)
);
