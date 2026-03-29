import os
import json
import base64
import pandas as pd
import matplotlib.pyplot as plt

# Files expected in the same folder:
# - rq1_results.csv
# - RQ1_Template.ipynb

df = pd.read_csv("rq1_results.csv")
df["regularization"] = df["regularization"].fillna("None")

# -----------------------------
# Figure 1: Baseline scaling
# -----------------------------
baseline = df[df["experiment"].str.startswith("Baseline")].drop_duplicates(
    subset=["experiment"], keep="first"
).copy()

fig, ax1 = plt.subplots(figsize=(8, 5))
ax1.plot(baseline["num_params"], baseline["overfitting_gap"], marker="o")
ax1.set_xscale("log")
ax1.set_xlabel("Number of parameters (log scale)")
ax1.set_ylabel("Overfitting gap (pp)")
ax1.grid(True, alpha=0.3)

for _, r in baseline.iterrows():
    if r["experiment"] in [
        "Baseline 1x64",
        "Baseline 5x64",
        "Baseline 1x256",
        "Baseline 5x256",
        "Baseline 3x1024",
    ]:
        ax1.annotate(
            r["experiment"].replace("Baseline ", ""),
            (r["num_params"], r["overfitting_gap"]),
            fontsize=8,
            xytext=(4, 4),
            textcoords="offset points",
        )

ax2 = ax1.twinx()
ax2.plot(baseline["num_params"], baseline["test_acc"], marker="s", linestyle="--")
ax2.set_ylabel("Test accuracy (%)")
fig.tight_layout()
fig.savefig("fig_baseline_scaling.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# ----------------------------------------
# Figure 2: Trade-off in 2x256 experiments
# ----------------------------------------
reg2 = df[(df["num_layers"] == 2) & (df["hidden_size"] == 256)].copy()
order = [
    "Baseline 2x256",
    "L2_wd=1e-05",
    "L2_wd=0.0001",
    "L2_wd=0.001",
    "L2_wd=0.01",
    "L1_lambda=1e-05",
    "L1_lambda=0.0001",
    "L1_lambda=0.001",
    "L1_lambda=0.01",
    "Dropout_p=0.1",
    "Dropout_p=0.2",
    "Dropout_p=0.3",
    "Dropout_p=0.5",
    "BatchNorm_OFF_2x256",
    "BatchNorm_ON_2x256",
    "EarlyStop_p=3",
    "EarlyStop_p=5",
    "EarlyStop_p=10",
]
reg2 = reg2.set_index("experiment").loc[
    [x for x in order if x in reg2["experiment"].values]
].reset_index()

fig, ax = plt.subplots(figsize=(10, 5))
ax.scatter(reg2["overfitting_gap"], reg2["test_acc"])

for _, r in reg2.iterrows():
    label = (
        r["experiment"]
        .replace("Baseline ", "")
        .replace("BatchNorm_", "BN_")
        .replace("L1_lambda=", "L1=")
        .replace("L2_wd=", "L2=")
        .replace("Dropout_p=", "DO=")
        .replace("EarlyStop_p=", "ES=")
        .replace("_2x256", "")
    )
    ax.annotate(label, (r["overfitting_gap"], r["test_acc"]),
                fontsize=7, xytext=(3, 3), textcoords="offset points")

ax.set_xlabel("Overfitting gap (pp)")
ax.set_ylabel("Test accuracy (%)")
ax.set_ylim(96.5, 98.5)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("fig_regularization_tradeoff.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# ------------------------------------
# Figure 3: Combined methods comparison
# ------------------------------------
combo = df[
    df["experiment"].str.startswith("Combined")
    | df["experiment"].str.contains("BatchNorm_ON_4x256|BatchNorm_OFF_4x256")
].copy()

combo = combo[["experiment", "test_acc", "overfitting_gap"]]
combo["short"] = combo["experiment"].replace(
    {
        "BatchNorm_OFF_4x256": "Baseline 4x256",
        "BatchNorm_ON_4x256": "BatchNorm",
        "Combined_L2_Dropout": "L2+Dropout",
        "Combined_BN_Dropout": "BN+Dropout",
        "Combined_L2_Dropout_ES": "L2+Dropout+ES",
        "Combined_All": "L2+BN+Dropout+ES",
    }
)

combo = combo.set_index("short").loc[
    [
        "Baseline 4x256",
        "BatchNorm",
        "L2+Dropout",
        "BN+Dropout",
        "L2+Dropout+ES",
        "L2+BN+Dropout+ES",
    ]
].reset_index()

fig, ax1 = plt.subplots(figsize=(9, 5))
ax1.bar(combo["short"], combo["overfitting_gap"])
ax1.set_ylabel("Overfitting gap (pp)")
ax1.set_xlabel("Configuration")
ax1.tick_params(axis="x", rotation=25)

ax2 = ax1.twinx()
ax2.plot(combo["short"], combo["test_acc"], marker="o", linestyle="--")
ax2.set_ylabel("Test accuracy (%)")

fig.tight_layout()
fig.savefig("fig_combined_methods.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# ------------------------------------------------
# Extract selected notebook output figures as PNGs
# ------------------------------------------------
with open("RQ1_Template.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

selected = {
    "fig_notebook_baseline_accuracy.png": (21, 1),
    "fig_notebook_l2_validation.png": (23, 4),
    "fig_notebook_dropout_validation.png": (27, 4),
    "fig_notebook_earlystop_validation.png": (31, 3),
}

for fname, (cell_idx, image_idx) in selected.items():
    count = -1
    for output in nb["cells"][cell_idx].get("outputs", []):
        if "data" in output and "image/png" in output["data"]:
            count += 1
            if count == image_idx:
                payload = output["data"]["image/png"]
                if isinstance(payload, list):
                    payload = "".join(payload)
                with open(fname, "wb") as imgf:
                    imgf.write(base64.b64decode(payload))
                break

print("Done. Generated PNG files for Overleaf.")