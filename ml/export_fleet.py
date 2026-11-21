"""Train the models and export a replayable "live fleet" for the demo app.

The 12 fleet engines are held out of training, so the app shows predictions on
engines the models have never seen. Output is plain JSON: the backend never loads
pickled models, which removes a deserialization attack surface (OWASP A08).

Usage:  python export_fleet.py
Output: ../backend/app/data/fleet.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "raw" / "cmapss"
OUT = ROOT.parent / "backend" / "app" / "data" / "fleet.json"

RUL_CAP, HORIZON, WINDOW, HEALTHY_CYCLES = 125, 30, 10, 30
N_FLEET, SEED = 12, 7

# Sensors shown in the app, with their C-MAPSS names (Saxena et al., 2008)
DISPLAY_SENSORS = {
    "s3": "T30 HPC outlet temp",
    "s4": "T50 LPT outlet temp",
    "s7": "P30 HPC outlet pressure",
    "s9": "Nc core speed",
    "s11": "Ps30 HPC static pressure",
    "s12": "phi fuel flow ratio",
    "s15": "BPR bypass ratio",
}

COLS = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, sep=r"\s+", header=None, names=COLS)


def add_features(df: pd.DataFrame, sensors: list[str]) -> pd.DataFrame:
    df = df.sort_values(["unit", "cycle"]).copy()
    g = df.groupby("unit")
    for s in sensors:
        df[f"{s}_mean"] = g[s].transform(lambda x: x.rolling(WINDOW, min_periods=1).mean())
        df[f"{s}_std"] = g[s].transform(lambda x: x.rolling(WINDOW, min_periods=1).std()).fillna(0)
        df[f"{s}_slope"] = g[s].transform(lambda x: x.diff(WINDOW - 1) / (WINDOW - 1)).fillna(0)
    return df


def main() -> None:
    train = load("train_FD001.txt")
    train["RUL"] = train.groupby("unit")["cycle"].transform("max") - train["cycle"]
    sensors = [c for c in COLS[5:] if train[c].std() > 1e-4]
    df = add_features(train, sensors)
    features = ["cycle"] + sensors + [f"{s}_{k}" for s in sensors for k in ("mean", "std", "slope")]

    rng = np.random.default_rng(SEED)
    fleet_units = sorted(rng.choice(df["unit"].unique(), size=N_FLEET, replace=False).tolist())
    fit = df[~df["unit"].isin(fleet_units)]
    fleet = df[df["unit"].isin(fleet_units)].copy()

    # Health indicator: Isolation Forest trained on healthy early-life data only
    hi_cols = [f"{s}_mean" for s in sensors]
    healthy = fit.loc[fit["cycle"] <= HEALTHY_CYCLES, hi_cols]
    scaler = StandardScaler().fit(healthy)
    iso = IsolationForest(n_estimators=300, contamination=0.01, random_state=42).fit(scaler.transform(healthy))
    score_fit = -iso.score_samples(scaler.transform(fit[hi_cols]))
    s_good = float(np.median(score_fit[fit["cycle"].values <= HEALTHY_CYCLES]))
    s_alarm = float(np.quantile(score_fit[fit["cycle"].values <= HEALTHY_CYCLES], 0.99))
    s_fail = float(np.median(score_fit[fit["RUL"].values == 0]))

    def to_health(score: np.ndarray) -> np.ndarray:
        """Map anomaly score to 0-100 (100 = like new, 0 = typical failure state)."""
        return 100 * (1 - np.clip((score - s_good) / (s_fail - s_good), 0, 1))

    reg = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=42)
    reg.fit(fit[features], fit["RUL"].clip(upper=RUL_CAP))
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42)
    clf.fit(fit[features], (fit["RUL"] <= HORIZON).astype(int))

    fleet["health"] = to_health(-iso.score_samples(scaler.transform(fleet[hi_cols])))
    fleet["rul_pred"] = np.clip(reg.predict(fleet[features]), 0, None)
    fleet["fail_prob"] = clf.predict_proba(fleet[features])[:, 1]

    # Sensor deviation (z-score) vs the healthy fleet baseline, used to explain alerts
    base_mean = fit.loc[fit["cycle"] <= HEALTHY_CYCLES, list(DISPLAY_SENSORS)].mean()
    base_std = fit.loc[fit["cycle"] <= HEALTHY_CYCLES, list(DISPLAY_SENSORS)].std()

    engines = []
    for i, unit in enumerate(fleet_units):
        d = fleet[fleet["unit"] == unit]
        z = ((d[[f"{s}_mean" for s in DISPLAY_SENSORS]].values - base_mean.values) / base_std.values)
        engines.append({
            "id": i + 1,
            "name": f"ENG-{101 + i}",
            "source_unit": int(unit),
            "failure_cycle": int(d["cycle"].max()),
            "timeline": {
                "cycle": d["cycle"].astype(int).tolist(),
                "health": d["health"].round(1).tolist(),
                "rul_pred": d["rul_pred"].round(1).tolist(),
                "fail_prob": d["fail_prob"].round(3).tolist(),
                "sensors": {s: d[s].round(3).tolist() for s in DISPLAY_SENSORS},
                "z": {s: np.round(z[:, j], 2).tolist() for j, s in enumerate(DISPLAY_SENSORS)},
            },
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "meta": {
            "dataset": "NASA C-MAPSS FD001 (Saxena & Goebel, 2008)",
            "alert_health": round(float(to_health(np.array([s_alarm]))[0]), 1),
            "rul_alert": HORIZON,
            "sensor_names": DISPLAY_SENSORS,
        },
        "engines": engines,
    }, separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB), fleet units {fleet_units}")


if __name__ == "__main__":
    main()
