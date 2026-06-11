"""make_plots.py — auto-generated. Produces the suggested figures from
extracted_cohort.csv (run extract_vitaldb.py first). Edit the column names to
match your extracted features. Requires: pip install pandas matplotlib
"""
import pandas as pd, matplotlib.pyplot as plt

df = pd.read_csv("extracted_cohort.csv")

# Map these to your actual extracted columns:
EXPOSURE_COL = "EXPOSURE_COLUMN"   # e.g. "Solar8000/ART_MBP_min" for intraoperative hypotension
OUTCOME_COL  = "OUTCOME_COLUMN"    # e.g. "death_inhosp" for postoperative AKI
SUBGROUP_COL = "asa"

# 1. distribution of exposure
ax = df[EXPOSURE_COL].plot(kind="hist", bins=24, color="#0f766e", alpha=.85)
ax.set_title("Distribution of intraoperative hypotension"); plt.tight_layout(); plt.savefig("fig1_distribution.png"); plt.close()

# 2. outcome across exposure (binary -> event rate by decile; continuous -> scatter)
d = df.dropna(subset=[EXPOSURE_COL, OUTCOME_COL]).copy()
if d[OUTCOME_COL].dropna().isin([0, 1]).all():
    d["bin"] = pd.qcut(d[EXPOSURE_COL], 10, labels=False, duplicates="drop")
    d.groupby("bin")[OUTCOME_COL].mean().plot(kind="bar", color="#0f766e")
    plt.ylabel("postoperative AKI rate")
else:
    plt.scatter(d[EXPOSURE_COL], d[OUTCOME_COL], s=10, alpha=.35, color="#0f766e")
    plt.ylabel("postoperative AKI")
plt.title("postoperative AKI across intraoperative hypotension"); plt.tight_layout(); plt.savefig("fig2_association.png"); plt.close()

# 3. exposure by subgroup
if SUBGROUP_COL in df:
    df.boxplot(column=EXPOSURE_COL, by=SUBGROUP_COL)
    plt.title("intraoperative hypotension by " + SUBGROUP_COL); plt.suptitle(""); plt.tight_layout()
    plt.savefig("fig3_subgroup.png"); plt.close()
print("wrote figures")
