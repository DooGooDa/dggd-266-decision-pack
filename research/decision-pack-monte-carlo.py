#!/usr/bin/env python3
"""
DGG-266: UW Health Nursing Staffing — Monte Carlo Simulation + CEA/BIA
=======================================================================
Facility: UW Health (Facility 520098) | CMS HCRIS FY2023 + BLS + AHA
Date: 2026-04-10

Model design:
  Total Cost = Direct Staffing Cost + Indirect Cost
  Direct = Σ(scenario FTE × salary)
  Indirect = Agency Cost + Turnover Cost + Overtime Cost + Malpractice Cost

Key insight from literature:
  - Increasing staffing REDUCES indirect costs disproportionately
  - Agency premium: $59.28/hr (HCRIS actual) vs. $39/hr internal
  - High burnout → 18% turnover → $30K/replacement → estimated $8.8M/yr nationally
  - Better staffing reduces: agency utilization, turnover, burnout, adverse events

Scenarios:
  A: Status quo (268 FTE) — current indirect cost burden
  B: +10% staffing (+27 FTE) — reduces indirect costs significantly
  C: Night shift dedicated (+40 FTE) — largest indirect cost reduction
"""

import numpy as np
import pandas as pd

np.random.seed(42)

# ============================================================================
# BASELINE
# ============================================================================

N_ITER = 10000
YEARS = 3
WTP = 50000  # $/QALY

BASE = {
    "beds": 505,
    "admissions": 31000,
    "alos": 5.2,
    "nurse_fte": 268,           # HCRIS S-3 + AHA
    "rn_salary": 82000,         # BLS WI 2024
    "agency_rate": 59.28,       # HCRIS S-3 Part II ($/hr)
    "internal_nurse_rate": 39.0,  # internal RN fully-loaded ($/hr)
    "turnover_rate": 0.18,       # NSI 2024 survey
    "unit_turnover_cost": 30750,  # per-nurse replacement cost (hiring+training)
    "burnout": 0.42,            # prevalence
    "adverse_event_cost": 8500,  # per preventable adverse event
    "hours_per_fte": 2080,
}

SCENARIOS = {
    "A": {"name": "현 수준 유지", "fte_mult": 1.00, "fte_add": 0,
          "burnout_delta": 0.00, "agency_reduction": 0.00, "turnover_delta": 0.00},
    "B": {"name": "10% 증원",   "fte_mult": 1.10, "fte_add": 0,
          "burnout_delta": -0.08, "agency_reduction": 0.30, "turnover_delta": -0.05},
    "C": {"name": "야간 전담",   "fte_mult": 1.00, "fte_add": 40,
          "burnout_delta": -0.20, "agency_reduction": 0.60, "turnover_delta": -0.10},
}


# ============================================================================
# SIMULATION
# ============================================================================

def simulate(scenario_key, n_iter=N_ITER, years=YEARS):
    cfg = SCENARIOS[scenario_key]
    base_fte = BASE["nurse_fte"]
    fte = base_fte * cfg["fte_mult"] + cfg["fte_add"]

    # ---- Annual direct cost (salary) — deterministic ----
    annual_salary = fte * BASE["rn_salary"]

    # ---- Stochastic: agency rate (log-normal, HCRIS ± uncertainty) ----
    agency_rate = BASE["agency_rate"] * np.exp(np.random.normal(0, 0.06, (n_iter, years)))

    # ---- Agency utilization: driven by burnout. High burnout = high agency dependency ----
    # Base: 5% of FTE hours are agency/premium (literature)
    # Burnout reduction reduces this. Noise applied.
    noise = np.random.beta(4, 6, (n_iter, years))  # uncertainty factor
    burnout_effective = max(0.0, BASE["burnout"] + cfg["burnout_delta"]) * (1 - noise * abs(cfg["burnout_delta"]) / BASE["burnout"])
    agency_pct = BASE["burnout"] * 0.12 * (1 - cfg["agency_reduction"] * noise)  # 5% base when burnout=0.42
    agency_pct = np.clip(agency_pct, 0.001, 0.25)

    agency_hours_annual = fte * agency_pct * BASE["hours_per_fte"]
    annual_agency_cost = (agency_hours_annual * agency_rate).mean(axis=1)

    # ---- Turnover cost: driven by effective turnover rate ----
    # Base: 18% annual turnover. Each departure costs $30,750.
    base_turnover = BASE["turnover_rate"]
    # Apply scenario delta with noise
    turnover_rate = base_turnover + cfg["turnover_delta"] * noise
    turnover_rate = np.clip(turnover_rate, 0.02, 0.40)
    annual_turnover_cost = (turnover_rate * fte * BASE["unit_turnover_cost"]).mean(axis=1)

    # ---- Adverse event cost: burnout drives medication errors, falls, infections ----
    # Literature: 5-10% of admissions experience preventable adverse events
    # Burnout is correlated with ~2× higher adverse event rate
    adverse_event_rate_base = 0.06  # 6% of admissions
    burnout_adverse_multiplier = 1 + burnout_effective.mean(axis=1)  # relative to base
    adverse_events_per_year = BASE["admissions"] * adverse_event_rate_base * burnout_adverse_multiplier
    annual_adverse_cost = adverse_events_per_year * BASE["adverse_event_cost"]

    # ---- Overtime cost: understaffing → overtime. Burnout reduction reduces this. ----
    # Assume 5% overtime premium on salary when understaffed (scenario A)
    overtime_pct = max(0.0, 0.05 - cfg["burnout_delta"] * 0.1)  # A: 5%, B: ~4%, C: ~3%
    annual_overtime_cost = annual_salary * overtime_pct

    # ---- Total annual cost ----
    total_annual = annual_salary + annual_agency_cost + annual_turnover_cost + annual_adverse_cost + annual_overtime_cost
    total_3yr = total_annual * years

    # ---- QALY gain ----
    # ALOS reduction: better staffing → shorter stays
    alos_delta = (np.random.beta(3, 7, (n_iter, years))
                  * 0.15 * (cfg["fte_mult"] - 1.0 + cfg["fte_add"] / base_fte))
    alos_delta_3yr = alos_delta.sum(axis=1)
    qaly_alos = (alos_delta / BASE["alos"]) * 0.02 * BASE["admissions"] * years
    qaly_burnout = abs(cfg["burnout_delta"]) * BASE["burnout"] * 0.08 * BASE["admissions"] * years
    qaly_adverse = (1 - burnout_adverse_multiplier / (1 + BASE["burnout"])) * 0.03 * BASE["admissions"] * years
    qaly_3yr = qaly_alos.mean(axis=1) + qaly_burnout + qaly_adverse

    return pd.DataFrame({
        "scenario": scenario_key,
        "name": cfg["name"],
        "fte": fte,
        "total_cost_3yr": total_3yr,
        "salary_3yr": annual_salary * years,
        "agency_3yr": annual_agency_cost * years,
        "turnover_3yr": annual_turnover_cost * years,
        "adverse_3yr": annual_adverse_cost * years,
        "overtime_3yr": annual_overtime_cost * years,
        "qaly_3yr": qaly_3yr,
        "alos_delta_3yr": alos_delta_3yr,
    })


def run_all():
    results = []
    for k in ["A", "B", "C"]:
        print(f"  {k}: {SCENARIOS[k]['name']}...", end=" ", flush=True)
        results.append(simulate(k))
        print("done")
    return pd.concat(results, ignore_index=True)


# ============================================================================
# ANALYSIS
# ============================================================================

def summarize(df):
    rows = []
    for k in ["A", "B", "C"]:
        s = df[df["scenario"] == k]
        cost = s["total_cost_3yr"]
        rows.append({
            "scenario": k,
            "name": SCENARIOS[k]["name"],
            "fte": int(s["fte"].iloc[0]),
            "mean_cost_3yr": cost.mean(),
            "p025": cost.quantile(0.025),
            "p975": cost.quantile(0.975),
            "cost_prob": (cost < 0).mean(),
            "mean_qaly": s["qaly_3yr"].mean(),
            "salary_3yr": s["salary_3yr"].iloc[0],
            "agency_3yr": s["agency_3yr"].mean(),
            "turnover_3yr": s["turnover_3yr"].mean(),
            "adverse_3yr": s["adverse_3yr"].mean(),
        })
    return pd.DataFrame(rows)


def cea(df, summary):
    a_cost = summary.loc[summary.scenario == "A", "mean_cost_3yr"].values[0]
    a_qaly = summary.loc[summary.scenario == "A", "mean_qaly"].values[0]
    results = []
    for k in ["B", "C"]:
        s = summary[summary.scenario == k].iloc[0]
        delta_cost = s["mean_cost_3yr"] - a_cost
        delta_qaly = s["mean_qaly"] - a_qaly

        # Probability B/C is cheaper than A
        a_costs = df[df["scenario"] == "A"]["total_cost_3yr"]
        b_costs = df[df["scenario"] == k]["total_cost_3yr"]
        cost_win_prob = (b_costs.values < a_costs.values.mean()).mean()

        icer = delta_cost / delta_qaly if delta_qaly > 0 else float("inf")
        dominant = delta_cost < 0 and delta_qaly > 0
        results.append({
            "scenario": k,
            "name": s["name"],
            "delta_cost": delta_cost,
            "delta_qaly": delta_qaly,
            "icer": icer,
            "dominant": dominant,
            "cost_win_prob": cost_win_prob,
        })
    return pd.DataFrame(results)


def print_all(summary, cea_df):
    print("\n" + "=" * 72)
    print("UW HEALTH NURSING STAFFING — MONTE CARLO SIMULATION RESULTS")
    print("=" * 72)
    print(f"Facility: UW Health (Facility 520098) | Iterations: {N_ITER:,} | Years: {YEARS}")
    print(f"Baseline: {BASE['nurse_fte']} FTE | Agency rate: ${BASE['agency_rate']}/hr (HCRIS)")
    print()

    print("-" * 72)
    print("3-YEAR TOTAL COST BY SCENARIO")
    print("-" * 72)
    for _, r in summary.iterrows():
        c = r["mean_cost_3yr"]
        print(f"  {r['scenario']}: {r['name']} ({r['fte']} FTE)")
        print(f"       Total 3yr cost:  ${c/1e6:.2f}M  [${r['p025']/1e6:.2f}M – ${r['p975']/1e6:.2f}M]")
        print(f"       Salary (3yr):    ${r['salary_3yr']/1e6:.2f}M  (deterministic)")
        print(f"       Agency (3yr):    ${r['agency_3yr']/1e6:.2f}M")
        print(f"       Turnover (3yr): ${r['turnover_3yr']/1e6:.2f}M")
        print(f"       Adverse (3yr):   ${r['adverse_3yr']/1e6:.2f}M")
        print(f"       QALY gain (3yr): {r['mean_qaly']:.1f}")
        print()

    print("-" * 72)
    print("COST COMPARISON vs. SCENARIO A")
    print("-" * 72)
    a_cost = summary.loc[summary.scenario == "A", "mean_cost_3yr"].values[0]
    a_qaly = summary.loc[summary.scenario == "A", "mean_qaly"].values[0]
    for _, r in summary.iterrows():
        if r["scenario"] == "A":
            continue
        delta = r["mean_cost_3yr"] - a_cost
        delta_qaly = r["mean_qaly"] - a_qaly
        roi = -(delta) / r["salary_3yr"] * 100 if r["scenario"] != "A" else 0
        print(f"  {r['scenario']}: {r['name']}")
        print(f"       ΔCost vs A: ${delta/1e6:+.2f}M  ({'SAVINGS' if delta < 0 else 'COST'})")
        print(f"       ΔQALY vs A: {delta_qaly:+.1f}")
        print(f"       Salary invest: ${(r['salary_3yr'] - summary.loc[summary.scenario=='A','salary_3yr'].values[0])/1e6:+.2f}M")
        print(f"       ROI: {roi:.0f}%")
        print()

    print("-" * 72)
    print("CEA (WTP = $50,000/QALY)")
    print("-" * 72)
    for _, r in cea_df.iterrows():
        if r["dominant"]:
            print(f"  {r['scenario']}: {r['name']} → DOMINANT (saves money + improves health)")
        else:
            print(f"  {r['scenario']}: {r['name']} → ICER ${r['icer']/1e3:.0f}K/QALY")

    print()
    print("-" * 72)
    print("RECOMMENDATION")
    print("-" * 72)
    dom = cea_df[cea_df["dominant"]]
    if len(dom) > 0:
        best = dom.sort_values("cost_win_prob", ascending=False).iloc[0]
        print(f"  → {best['scenario']} ({best['name']}) is DOMINANT")
        print(f"    Cost-savings probability vs A: {best['cost_win_prob']:.0%}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print(f"Monte Carlo | {N_ITER:,} iter × {YEARS}yr × 3 scenarios")
    df = run_all()
    summary = summarize(df)
    cea_df = cea(df, summary)
    print_all(summary, cea_df)

    out = "/Users/albert/workspace/cinna-mlds/research/decision_pack_results.csv"
    df.to_csv(out, index=False)
    print(f"\nRaw results: {out}")
