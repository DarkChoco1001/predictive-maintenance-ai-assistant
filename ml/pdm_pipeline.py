# %% [markdown]
# # Predictive Maintenance & Reliability Analysis — NASA Turbofan Engines (C-MAPSS FD001)
#
# **Goal:** Use sensor time-series from 100 turbofan engines run to failure to:
# 1. Do a **reliability analysis**: lifetime distribution, MTTF/MTBF, Weibull fit, B10 life, availability.
# 2. Detect **early degradation** with unsupervised **anomaly detection** (Isolation Forest).
# 3. Predict **Remaining Useful Life (RUL)** with **regression** (Gradient Boosting).
# 4. Predict **"failure within 30 cycles"** with **classification**, the alarm a maintenance planner acts on.
# 5. Turn model output into a **maintenance decision** and estimate its business value.
#
# Data: A. Saxena and K. Goebel (2008), "Turbofan Engine Degradation Simulation Data Set",
# NASA Ames Prognostics Data Repository. FD001 = 1 operating condition, 1 fault mode (HPC degradation).

# %%
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, IsolationForest
from sklearn.metrics import (classification_report, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
DATA = ROOT / "data" / "raw" / "cmapss"
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
metrics = {}

RUL_CAP = 125        # common practice: RUL is flat early in life (engine is "healthy")
ALARM_HORIZON = 30   # classification target: will the engine fail within 30 cycles?
WINDOW = 10          # rolling window (cycles) for trend features

# %% [markdown]
# ## 1. Load data

# %%
cols = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]

def load(name):
    return pd.read_csv(DATA / name, sep=r"\s+", header=None, names=cols)

train = load("train_FD001.txt")
test = load("test_FD001.txt")
test_rul = pd.read_csv(DATA / "RUL_FD001.txt", header=None, names=["RUL"])
test_rul["unit"] = np.arange(1, len(test_rul) + 1)

print(f"Train: {train.unit.nunique()} engines, {len(train):,} rows | Test: {test.unit.nunique()} engines")

# Label: remaining useful life = cycles left until failure (train engines run to failure)
train["RUL"] = train.groupby("unit")["cycle"].transform("max") - train["cycle"]

# Drop sensors that never change (no information)
sensors = [c for c in cols[5:] if train[c].std() > 1e-4]
print("Informative sensors:", sensors)

# %% [markdown]
# ## 2. Reliability analysis (MTTF/MTBF, Weibull, B10, availability)
#
# Each training engine runs until failure, so its last cycle is its **time to failure**.
# These engines are not repaired, so the right metric is **MTTF**. For a repairable asset
# restored to "as good as new", MTTF equals **MTBF**.

# %%
life = train.groupby("unit")["cycle"].max()
mttf = life.mean()

# 2-parameter Weibull fit (location fixed at 0)
beta, _, eta = stats.weibull_min.fit(life, floc=0)
b10 = eta * (-np.log(0.9)) ** (1 / beta)  # age by which 10% of the fleet has failed

# Availability = MTBF / (MTBF + MTTR). The dataset has no repair times, so MTTR is an ASSUMPTION
# used only to show the calculation.
MTTR_ASSUMED = 5  # cycles of downtime per unplanned failure (illustrative)
availability = mttf / (mttf + MTTR_ASSUMED)

metrics["reliability"] = {
    "engines": int(life.size),
    "MTTF_cycles": round(float(mttf), 1),
    "min_life": int(life.min()), "max_life": int(life.max()),
    "weibull_beta_shape": round(float(beta), 2),
    "weibull_eta_scale": round(float(eta), 1),
    "B10_life_cycles": round(float(b10), 1),
    "MTTR_assumed_cycles": MTTR_ASSUMED,
    "inherent_availability": round(float(availability), 4),
}
print(json.dumps(metrics["reliability"], indent=2))
print(f"Weibull beta = {beta:.2f} -> {'wear-out (increasing failure rate)' if beta > 1 else 'random/early failures'}")

t = np.linspace(0, life.max() * 1.1, 300)
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].hist(life, bins=20, density=True, alpha=0.6, label="Observed lifetimes")
ax[0].plot(t, stats.weibull_min.pdf(t, beta, scale=eta), "r-", label=f"Weibull β={beta:.1f}, η={eta:.0f}")
ax[0].axvline(mttf, color="k", ls="--", label=f"MTTF = {mttf:.0f}")
ax[0].set(title="Time-to-failure distribution", xlabel="Cycles", ylabel="Density"); ax[0].legend()
t2 = t[t <= life.max()]
ax[1].plot(t2, stats.weibull_min.sf(t2, beta, scale=eta), color="C0", label="Reliability R(t)")
ax[1].axvline(b10, color="r", ls="--", label=f"B10 life = {b10:.0f}")
ax[1].set(title="Reliability & hazard rate", xlabel="Cycles", ylabel="R(t) = P(still running)")
ax[1].legend(loc="center left")
ax2 = ax[1].twinx()  # hazard on its own axis so both curves are readable
ax2.plot(t2, stats.weibull_min.pdf(t2, beta, scale=eta) / stats.weibull_min.sf(t2, beta, scale=eta),
         color="C1", label="Hazard rate h(t)")
ax2.set_ylabel("Failures per cycle", color="C1"); ax2.legend(loc="upper right")
plt.tight_layout(); plt.savefig(FIG / "01_reliability_weibull.png", dpi=120); plt.close()

# %% [markdown]
# **Interpretation (RCM view):** β > 1 means the failure rate **rises with age**: this is wear-out
# degradation. Under RCM decision logic, a wear-out failure that gives warning signs in the
# sensors is a good candidate for **condition-based / predictive maintenance**, not run-to-failure
# and not fixed-interval replacement. Fixed-interval replacement at B10 would throw away a lot of
# useful life, because lifetimes vary widely.

# %% [markdown]
# ## 3. Exploratory analysis: how sensors degrade

# %%
fig, axes = plt.subplots(3, 4, figsize=(14, 8)); axes = axes.ravel()
for ax, s in zip(axes, sensors[:12]):
    for u in [1, 20, 40, 60, 80]:
        d = train[train.unit == u]
        ax.plot(d["RUL"], d[s], lw=0.8)
    ax.invert_xaxis(); ax.set_title(s, fontsize=9); ax.set_xlabel("RUL", fontsize=8)
plt.suptitle("Sensor trends vs remaining useful life (5 engines)"); plt.tight_layout()
plt.savefig(FIG / "02_sensor_trends.png", dpi=120); plt.close()

corr = train[sensors + ["RUL"]].corr()["RUL"].drop("RUL").sort_values()
print("Correlation of each sensor with RUL:\n", corr.round(2))

# %% [markdown]
# ## 4. Feature engineering: rolling trend features per engine

# %%
def add_features(df):
    df = df.sort_values(["unit", "cycle"]).copy()
    g = df.groupby("unit")
    for s in sensors:
        df[f"{s}_mean"] = g[s].transform(lambda x: x.rolling(WINDOW, min_periods=1).mean())
        df[f"{s}_std"] = g[s].transform(lambda x: x.rolling(WINDOW, min_periods=1).std()).fillna(0)
        df[f"{s}_slope"] = g[s].transform(lambda x: x.diff(WINDOW - 1) / (WINDOW - 1)).fillna(0)
    return df

train_f = add_features(train)
test_f = add_features(test)
features = ["cycle"] + sensors + [f"{s}_{k}" for s in sensors for k in ("mean", "std", "slope")]
print(f"{len(features)} features")

# Evaluate on each test engine's LAST observed cycle (the official benchmark setup)
test_last = test_f.groupby("unit").tail(1).merge(test_rul, on="unit")

# %% [markdown]
# ## 5. Early degradation detection: Isolation Forest (unsupervised anomaly detection)
#
# Train only on **healthy** data (each engine's first 30 cycles), then score every cycle.
# The detector raises an alert when the anomaly score stays above threshold for 5 cycles in a row.
# **Lead time** = how many cycles before failure the alert fired.

# %%
hi_cols = [f"{s}_mean" for s in sensors]  # smoothed sensors make a less noisy health indicator
healthy = train_f.loc[train_f.cycle <= 30, hi_cols]
scaler = StandardScaler().fit(healthy)
iso = IsolationForest(n_estimators=300, contamination=0.01, random_state=42)
iso.fit(scaler.transform(healthy))

train_f["anomaly_score"] = -iso.score_samples(scaler.transform(train_f[hi_cols]))
healthy_scores = train_f.loc[train_f.cycle <= 30, "anomaly_score"]
threshold = healthy_scores.quantile(0.99)

def first_alert(d, persist=5):
    above = (d["anomaly_score"] > threshold).astype(int)
    run = above.groupby((above != above.shift()).cumsum()).cumsum()
    hit = d.loc[run >= persist]
    return hit["RUL"].iloc[0] if len(hit) else np.nan

lead = train_f.groupby("unit")[["anomaly_score", "RUL"]].apply(first_alert)
metrics["anomaly_detection"] = {
    "engines_alerted_before_failure_pct": round(float(lead.notna().mean() * 100), 1),
    "median_lead_time_cycles": round(float(lead.median()), 1),
    "p10_lead_time_cycles": round(float(lead.quantile(0.1)), 1),
}
print(json.dumps(metrics["anomaly_detection"], indent=2))

fig, ax = plt.subplots(figsize=(9, 4))
for u in [1, 20, 40, 60, 80]:
    d = train_f[train_f.unit == u]
    ax.plot(d["RUL"], d["anomaly_score"], lw=0.9, label=f"Engine {u}")
ax.axhline(threshold, color="r", ls="--", label="Alert threshold")
ax.invert_xaxis(); ax.set(xlabel="Remaining useful life (cycles)", ylabel="Anomaly score",
                          title="Health indicator rises as engines degrade"); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(FIG / "03_anomaly_health_index.png", dpi=120); plt.close()

# %% [markdown]
# ## 6. RUL prediction: regression
#
# Validation uses **GroupKFold by engine**, so no engine appears in both train and validation.
# Splitting rows at random would leak data and make the scores look better than they are.

# %%
X, y, groups = train_f[features], train_f["RUL"].clip(upper=RUL_CAP), train_f["unit"]
reg = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=42)
cv_pred = cross_val_predict(reg, X, y, groups=groups, cv=GroupKFold(n_splits=5))
reg.fit(X, y)

pred_test = np.clip(reg.predict(test_last[features]), 0, None)
true_test = test_last["RUL"].clip(upper=RUL_CAP).values

def nasa_score(y_true, y_pred):
    """PHM08 asymmetric score: late predictions (over-estimating RUL) are penalised more."""
    d = y_pred - y_true
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))

metrics["rul_regression"] = {
    "cv_rmse": round(float(np.sqrt(mean_squared_error(y, cv_pred))), 2),
    "test_rmse": round(float(np.sqrt(mean_squared_error(true_test, pred_test))), 2),
    "test_mae": round(float(mean_absolute_error(true_test, pred_test)), 2),
    "test_nasa_score": round(nasa_score(true_test, pred_test), 1),
}
print(json.dumps(metrics["rul_regression"], indent=2))

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].scatter(true_test, pred_test, s=15)
ax[0].plot([0, RUL_CAP], [0, RUL_CAP], "r--")
ax[0].set(title="Test set: predicted vs true RUL", xlabel="True RUL", ylabel="Predicted RUL")
order = np.argsort(true_test)
ax[1].plot(true_test[order], "o-", ms=3, label="True"); ax[1].plot(pred_test[order], "x", ms=4, label="Predicted")
ax[1].set(title="100 test engines (sorted by true RUL)", xlabel="Engine", ylabel="RUL"); ax[1].legend()
plt.tight_layout(); plt.savefig(FIG / "04_rul_prediction.png", dpi=120); plt.close()

# %% [markdown]
# ## 7. Failure-within-30-cycles: classification (the maintenance alarm)

# %%
y_cls = (train_f["RUL"] <= ALARM_HORIZON).astype(int)
clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42)
cv_proba = cross_val_predict(clf, X, y_cls, groups=groups, cv=GroupKFold(n_splits=5), method="predict_proba")[:, 1]
clf.fit(X, y_cls)

test_proba = clf.predict_proba(test_last[features])[:, 1]
test_true_cls = (test_last["RUL"] <= ALARM_HORIZON).astype(int)
test_pred_cls = (test_proba >= 0.5).astype(int)

metrics["failure_classification"] = {
    "cv_roc_auc": round(float(roc_auc_score(y_cls, cv_proba)), 3),
    "test_roc_auc": round(float(roc_auc_score(test_true_cls, test_proba)), 3),
    "test_precision": round(float(precision_score(test_true_cls, test_pred_cls)), 3),
    "test_recall": round(float(recall_score(test_true_cls, test_pred_cls)), 3),
    "test_f1": round(float(f1_score(test_true_cls, test_pred_cls)), 3),
}
print(json.dumps(metrics["failure_classification"], indent=2))
print(classification_report(test_true_cls, test_pred_cls, target_names=["healthy", "fail<=30"]))

# %% [markdown]
# ## 8. From prediction to maintenance decision: business value
#
# Policy: **schedule maintenance when predicted RUL ≤ 30 cycles**. The costs below are ILLUSTRATIVE
# relative units, used to show how to present value to a customer:
# unplanned failure = 10, planned maintenance = 1.

# %%
COST_FAIL, COST_PLANNED = 10, 1
alarm = pred_test <= ALARM_HORIZON
truly_at_risk = test_last["RUL"].values <= ALARM_HORIZON
caught = int((alarm & truly_at_risk).sum())
missed = int((~alarm & truly_at_risk).sum())
early = int((alarm & ~truly_at_risk).sum())

cost_reactive = truly_at_risk.sum() * COST_FAIL                     # run-to-failure
cost_pdm = caught * COST_PLANNED + missed * COST_FAIL + early * COST_PLANNED
metrics["maintenance_policy"] = {
    "engines_at_risk": int(truly_at_risk.sum()), "caught": caught, "missed": missed, "early_alarms": early,
    "cost_run_to_failure": int(cost_reactive), "cost_predictive": int(cost_pdm),
    "cost_reduction_pct": round(float((1 - cost_pdm / cost_reactive) * 100), 1),
}
print(json.dumps(metrics["maintenance_policy"], indent=2))

# Top drivers (simple permutation importance on the test-last set)
from sklearn.inspection import permutation_importance
pi = permutation_importance(reg, test_last[features], true_test, n_repeats=5, random_state=42)
top = pd.Series(pi.importances_mean, index=features).sort_values(ascending=False).head(10)
metrics["top_features"] = top.round(3).to_dict()
top[::-1].plot.barh(figsize=(7, 4), title="Top 10 drivers of RUL prediction")
plt.tight_layout(); plt.savefig(FIG / "05_feature_importance.png", dpi=120); plt.close()

# %%
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "reports" / "metrics.json").write_text(json.dumps(metrics, indent=2))
print("Saved reports/metrics.json and figures to reports/figures/")
