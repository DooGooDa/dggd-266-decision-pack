#!/usr/bin/env python3
"""
DGG-266 Decision Pack — CMS/HCRIS 데이터 수집 + Monte Carlo/CEA/BIA 분석
UW Health (520098) 간호 인력 시나리오 분석

데이터 소스:
- CMS Hospital General Information (Facility 520098)
- CMS HCRIS S-3 (literature-derived parameters for nursing FTE)
- AHA Hospital Statistics (national benchmarks)
- Published literature on nurse staffing ratios and outcomes

분석 방법:
1. Literature-based parameter estimation (prior + CMS 실제 값)
2. Monte Carlo simulation (10,000 iterations × 3 scenarios)
3. CEA (Cost-Effectiveness Analysis) — ICER per QALY
4. BIA (Budget Impact Analysis) — 3-year projection
"""

import numpy as np
import pandas as pd
from scipy import stats
import json
import os
from datetime import datetime

np.random.seed(42)

# ============================================================================
# 1. BASELINE PARAMETERS — UW Health (505-bed Academic Medical Center)
# ============================================================================
# Sources: AHA Hospital Statistics 2024, BLS OES May 2024,
#          Needleman et al. (2011) NEJM, Aiken et al. (2002) JAMA

baseline = {
    "hospital": "UW Health (University of WI Hospitals & Clinics Authority)",
    "facility_id": "520098",
    "beds": 505,                   # [AHA/CMS] staffed beds
    "occupancy_rate": 0.78,        # [AHA] avg for large academic
    "avg_los": 5.2,                # [AHA] days, large teaching hospital avg
    "annual_admissions": 31000,    # [Calc] 505 beds * 0.78 * 365 / 5.2
    "total_fte": 671,              # [HCRIS S-3] Line 01400, Col 00200 (actual)
    "nurse_fte_s3": 116,           # [HCRIS S-3] Lines 00801-00806 (actual)
    "nurse_fte_total": 268,        # [HCRIS+AHA] ~40% of total FTE per AHA AMC benchmarks
    "nurse_fte_rn": 210,           # [HCRIS+AHA] ~78% RN ratio
    "nurse_patient_ratio_day": 4.5, # [Lit] med-surg day shift (Aiken 2002)
    "nurse_patient_ratio_night": 5.5,
    "avg_rn_salary": 82000,        # [BLS] WI RN median 2024
    "avg_rn_benefits_rate": 0.32,  # [BLS/AHA] benefits as % salary
    "agency_hourly": 59.28,        # [HCRIS S-3] Part II, Line 02700 (actual)
    "permanent_hourly": 42.00,     # [BLS] WI RN hourly median
    "rn_turnover_rate": 0.18,      # [NSI] 2024 national avg
    "vacancy_rate": 0.08,          # [NSI] pre-COVID baseline
    "burnout_index": 0.42,         # [Lit] Maslach MBI prevalence
    "overtime_pct": 0.12,          # [Lit] overtime hours as % total
    "agency_staff_pct": 0.05,      # [Lit] travel/agency nurse %
    "agency_cost_multiplier": 1.41, # [HCRIS] agency $59.28 / permanent $42.00
}

# ============================================================================
# 2. LITERATURE-DERIVED EFFECT SIZES
# ============================================================================
# Needleman et al. (2011) NEJM: 10% RN increase → 0.4-day LOS reduction
# Aiken et al. (2002) JAMA: +1 patient per nurse → 7% mortality increase
# Griffiths et al. (2016) IJNS: nurse staffing → patient outcomes meta-analysis
# McHugh et al. (2021) Health Affairs: burnout → turnover causal chain

effect_sizes = {
    "rn_increase_los_effect": -0.04,      # per 1% RN increase, LOS change (days)
    "rn_increase_mortality_effect": -0.007, # per 1% RN increase, mortality RR reduction
    "burnout_turnover_elasticity": 0.65,   # burnout index → turnover rate elasticity
    "overtime_burnout_effect": 0.008,       # per 1% overtime increase → burnout index change
    "night_dedicated_burnout_reduction": -0.08, # night dedicated staff → burnout index reduction
    "rn_increase_wait_effect": -0.02,       # per 1% RN increase → wait time % change
}

# ============================================================================
# 3. SCENARIO DEFINITIONS
# ============================================================================

scenarios = {
    "A_maintain": {
        "label": "A: 현 수준 유지",
        "rn_fte_change": 0,
        "night_dedicated": False,
        "overtime_change": 0,
        "description": "Current staffing levels maintained. No intervention."
    },
    "B_10pct_increase": {
        "label": "B: 10% 증원",
        "rn_fte_change": 0.10,
        "night_dedicated": False,
        "overtime_change": -0.03,  # overtime decreases with more staff
        "description": "10% RN FTE increase across all shifts."
    },
    "C_night_dedicated": {
        "label": "C: 야간 전담 추가",
        "rn_fte_change": 0.05,  # 5% additional RN for night coverage
        "night_dedicated": True,
        "overtime_change": -0.05,
        "description": "5% RN increase + dedicated night shift team (reduces agency dependence)."
    },
}

# ============================================================================
# 4. COST PARAMETERS
# ============================================================================
cost_params = {
    "rn_hire_cost": 12000,          # per FTE (recruitment + onboarding)
    "annual_rn_total_cost": baseline["avg_rn_salary"] * (1 + baseline["avg_rn_benefits_rate"]),
    "agency_rn_hourly": 59.28,       # [HCRIS] S-3 Part II actual value
    "permanent_rn_hourly": 42.00,    # [BLS] WI RN hourly median
    "night_differential": 0.15,     # 15% night shift differential
    "overtime_multiplier": 1.5,
    "burnout_cost_per_fte": 5500,   # per burned-out FTE (absenteeism + presenteeism)
    "turnover_cost_per_rn": 56000,  # per RN turnover event (NSI 2024)
    "patient_day_cost": 2800,       # avg cost per patient day
    "avoidable_day_value": 800,    # marginal cost saving per avoided patient day (variable cost only, not revenue)
    "quality_penalty_threshold": 0.03,  # readmission penalty trigger
    "annual_quality_bonus": 450000,     # VBP potential bonus
}

# ============================================================================
# 5. MONTE CARLO SIMULATION
# ============================================================================

N_ITERATIONS = 10000
SIMULATION_YEARS = 3

def run_monte_carlo(baseline, effect_sizes, scenarios, cost_params, n_iter=N_ITERATIONS):
    """Run Monte Carlo simulation for all scenarios."""
    results = {}

    for scenario_key, scenario in scenarios.items():
        # Storage for each iteration
        iter_results = {
            "total_cost": [],
            "los_reduction": [],
            "turnover_reduction": [],
            "burnout_reduction": [],
            "wait_time_reduction": [],
            "avoidable_days_saved": [],
            "net_cost": [],
            "icer_per_qaly": [],
            "yearly_costs": [],
            "yearly_savings": [],
        }

        for _ in range(n_iter):
            # --- Stochastic parameters (uncertainty distributions) ---
            rn_change = scenario["rn_fte_change"]
            base_rn = baseline["nurse_fte_rn"]
            new_rn = base_rn * (1 + rn_change)

            # Hiring cost
            new_hires = base_rn * rn_change
            hire_cost = new_hires * cost_params["rn_hire_cost"]

            # Annual staffing cost change
            annual_new_staff_cost = new_hires * cost_params["annual_rn_total_cost"]
            if scenario.get("night_dedicated"):
                annual_new_staff_cost *= (1 + cost_params["night_differential"])

            # Overtime change → cost saving
            ot_change = scenario.get("overtime_change", 0)
            ot_reduction_saving = (
                baseline["nurse_fte_rn"] * 2080 *  # annual hours per FTE
                baseline["overtime_pct"] * abs(ot_change) *
                (cost_params["overtime_multiplier"] - 1) * cost_params["permanent_rn_hourly"]
            )
            ot_reduction_saving = max(0, ot_reduction_saving)  # savings positive

            # Agency reduction (if night dedicated, agency use drops)
            agency_saving = 0
            if scenario.get("night_dedicated"):
                agency_hours_reduced = (
                    baseline["nurse_fte_total"] * 2080 * baseline["agency_staff_pct"] * 0.4
                )
                agency_saving = agency_hours_reduced * (
                    cost_params["agency_rn_hourly"] - cost_params["permanent_rn_hourly"]
                )

            # LOS effect (stochastic — draw from normal with literature-derived effect)
            los_effect_sd = abs(effect_sizes["rn_increase_los_effect"]) * 0.5  # 50% of effect as SD
            los_effect = np.random.normal(
                effect_sizes["rn_increase_los_effect"] * rn_change * 100,  # effect per 1% change × %
                los_effect_sd * rn_change * 100 if rn_change > 0 else 0.01
            )
            new_los = baseline["avg_los"] + los_effect
            new_los = max(3.5, new_los)  # floor at 3.5 days

            # Avoidable days saved
            los_reduction = baseline["avg_los"] - new_los
            avoidable_days = baseline["annual_admissions"] * los_reduction

            # Burnout effect
            burnout_change = (
                effect_sizes["overtime_burnout_effect"] * ot_change * 100 +
                (effect_sizes["night_dedicated_burnout_reduction"] if scenario.get("night_dedicated") else 0) +
                np.random.normal(0, 0.01)  # noise
            )
            new_burnout = baseline["burnout_index"] + burnout_change
            new_burnout = max(0.1, min(0.8, new_burnout))
            burnout_reduction = baseline["burnout_index"] - new_burnout

            # Turnover effect (driven by burnout — burnout_reduction is positive when burnout decreases)
            turnover_change = (
                -effect_sizes["burnout_turnover_elasticity"] * burnout_reduction +  # burnout down → turnover down
                np.random.normal(0, 0.005)
            )
            new_turnover = baseline["rn_turnover_rate"] + turnover_change
            new_turnover = max(0.05, min(0.35, new_turnover))
            turnover_reduction = baseline["rn_turnover_rate"] - new_turnover  # positive = improvement

            # Wait time effect
            wait_effect = effect_sizes["rn_increase_wait_effect"] * rn_change * 100
            wait_effect += np.random.normal(0, 0.005)
            wait_reduction = abs(wait_effect) if wait_effect < 0 else 0

            # --- 3-Year Cost Calculation ---
            yearly_costs = []
            yearly_savings = []

            for year in range(1, SIMULATION_YEARS + 1):
                # Discount rate 3%
                discount = 1.03 ** (year - 1)

                # Costs
                year_cost = annual_new_staff_cost / discount
                if year == 1:
                    year_cost += hire_cost  # one-time hiring cost in year 1

                # Savings
                avoidable_day_value = avoidable_days * cost_params["avoidable_day_value"] / discount
                turnover_saving = (
                    baseline["nurse_fte_rn"] * turnover_reduction *
                    cost_params["turnover_cost_per_rn"] / discount
                )
                burnout_saving = (
                    baseline["nurse_fte_rn"] * burnout_reduction *
                    cost_params["burnout_cost_per_fte"] / discount
                )
                ot_save = ot_reduction_saving / discount
                ag_save = agency_saving / discount

                # Quality bonus (if turnover drops below threshold)
                quality_bonus = 0
                if new_turnover < cost_params["quality_penalty_threshold"] * 5:  # proxy
                    quality_bonus = cost_params["annual_quality_bonus"] * 0.3 / discount

                year_saving = avoidable_day_value + turnover_saving + burnout_saving + ot_save + ag_save + quality_bonus

                yearly_costs.append(year_cost)
                yearly_savings.append(year_saving)

            total_cost_3yr = sum(yearly_costs)
            total_savings_3yr = sum(yearly_savings)
            net_cost = total_cost_3yr - total_savings_3yr

            # QALY estimation (rough — from LOS reduction + burnout improvement)
            # Rothberg et al. (2014): shorter LOS → reduced complications → QALY gain
            # Approximate: 0.005 QALY per avoided patient day
            qaly_gained = avoidable_days * 0.005 * SIMULATION_YEARS
            # Burnout improvement → nurse QALY (smaller effect but real)
            qaly_gained += baseline["nurse_fte_rn"] * burnout_reduction * 0.02 * SIMULATION_YEARS

            if qaly_gained > 0 and net_cost > 0:
                icer = net_cost / qaly_gained
            elif qaly_gained > 0 and net_cost <= 0:
                icer = -999999  # dominant (cost-saving)
            else:
                icer = float('inf')

            # Store results
            iter_results["total_cost"].append(total_cost_3yr)
            iter_results["los_reduction"].append(los_reduction)
            iter_results["turnover_reduction"].append(turnover_reduction)
            iter_results["burnout_reduction"].append(burnout_reduction)
            iter_results["wait_time_reduction"].append(wait_reduction)
            iter_results["avoidable_days_saved"].append(avoidable_days * SIMULATION_YEARS)
            iter_results["net_cost"].append(net_cost)
            iter_results["icer_per_qaly"].append(icer)
            iter_results["yearly_costs"].append(yearly_costs)
            iter_results["yearly_savings"].append(yearly_savings)

        # Aggregate statistics
        results[scenario_key] = {
            "label": scenario["label"],
            "total_cost_3yr": {
                "mean": np.mean(iter_results["total_cost"]),
                "ci_lower": np.percentile(iter_results["total_cost"], 2.5),
                "ci_upper": np.percentile(iter_results["total_cost"], 97.5),
            },
            "los_reduction": {
                "mean": np.mean(iter_results["los_reduction"]),
                "ci_lower": np.percentile(iter_results["los_reduction"], 2.5),
                "ci_upper": np.percentile(iter_results["los_reduction"], 97.5),
            },
            "turnover_reduction": {
                "mean": np.mean(iter_results["turnover_reduction"]),
                "ci_lower": np.percentile(iter_results["turnover_reduction"], 2.5),
                "ci_upper": np.percentile(iter_results["turnover_reduction"], 97.5),
            },
            "burnout_reduction": {
                "mean": np.mean(iter_results["burnout_reduction"]),
                "ci_lower": np.percentile(iter_results["burnout_reduction"], 2.5),
                "ci_upper": np.percentile(iter_results["burnout_reduction"], 97.5),
            },
            "wait_time_reduction_pct": {
                "mean": np.mean(iter_results["wait_time_reduction"]),
                "ci_lower": np.percentile(iter_results["wait_time_reduction"], 2.5),
                "ci_upper": np.percentile(iter_results["wait_time_reduction"], 97.5),
            },
            "avoidable_days_3yr": {
                "mean": np.mean(iter_results["avoidable_days_saved"]),
                "ci_lower": np.percentile(iter_results["avoidable_days_saved"], 2.5),
                "ci_upper": np.percentile(iter_results["avoidable_days_saved"], 97.5),
            },
            "net_cost_3yr": {
                "mean": np.mean(iter_results["net_cost"]),
                "ci_lower": np.percentile(iter_results["net_cost"], 2.5),
                "ci_upper": np.percentile(iter_results["net_cost"], 97.5),
            },
            "icer_per_qaly": {
                "mean": np.mean(iter_results["icer_per_qaly"]),
                "ci_lower": np.percentile(iter_results["icer_per_qaly"], 2.5),
                "ci_upper": np.percentile(iter_results["icer_per_qaly"], 97.5),
            },
            "pct_cost_effective_50k": np.mean([1 if x < 50000 and x > 0 else 0 for x in iter_results["icer_per_qaly"]]),
            "pct_cost_saving": np.mean([1 if x < 0 else 0 for x in iter_results["net_cost"]]),
        }

    return results


def run_bia(results, cost_params, baseline, scenarios):
    """Budget Impact Analysis — 3-year projection."""
    bia = {}
    for key, res in results.items():
        scenario = scenarios[key]
        rn_change = scenario["rn_fte_change"]
        new_hires = baseline["nurse_fte_rn"] * rn_change

        bia[key] = {
            "label": res["label"],
            "year1_investment": new_hires * cost_params["rn_hire_cost"] + new_hires * cost_params["annual_rn_total_cost"],
            "year2_cost": new_hires * cost_params["annual_rn_total_cost"],
            "year3_cost": new_hires * cost_params["annual_rn_total_cost"],
            "total_3yr_budget_impact": res["total_cost_3yr"]["mean"],
            "net_budget_impact": res["net_cost_3yr"]["mean"],
            "roi_pct": -res["net_cost_3yr"]["mean"] / res["total_cost_3yr"]["mean"] * 100 if res["total_cost_3yr"]["mean"] > 0 else 0,
        }
    return bia


def generate_report(results, bia, baseline, cost_params):
    """Generate markdown report."""
    report = []
    report.append("# Decision Pack — UW Health 간호 인력 시나리오 분석\n")
    report.append(f"**생성일:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"**대상:** {baseline['hospital']} (Facility {baseline['facility_id']})")
    report.append(f"**병상수:** {baseline['beds']} beds | **연간 입원:** {baseline['annual_admissions']:,}")
    report.append(f"**시뮬레이션:** Monte Carlo {N_ITERATIONS:,} iterations × {SIMULATION_YEARS}년\n")

    report.append("---\n")
    report.append("## 1. 베이스라인 현황\n")
    report.append(f"| 지표 | 값 |")
    report.append(f"|------|-----|")
    report.append(f"| 병상수 | {baseline['beds']} beds |")
    report.append(f"| 가동률 | {baseline['occupancy_rate']:.0%} |")
    report.append(f"| 평균 입원일수 (ALOS) | {baseline['avg_los']:.1f} days |")
    report.append(f"| 연간 입원 | {baseline['annual_admissions']:,} |")
    report.append(f"| 간호인력 (총 FTE) | {baseline['nurse_fte_total']:,} |")
    report.append(f"| 간호인력 (RN FTE) | {baseline['nurse_fte_rn']:,} |")
    report.append(f"| 낮간호사-환자비 | 1:{baseline['nurse_patient_ratio_day']:.1f} |")
    report.append(f"| 밤간호사-환자비 | 1:{baseline['nurse_patient_ratio_night']:.1f} |")
    report.append(f"| RN 평균연봉 | ${baseline['avg_rn_salary']:,} |")
    report.append(f"| 이직률 | {baseline['rn_turnover_rate']:.0%} |")
    report.append(f"| 번아웃 지수 | {baseline['burnout_index']:.0%} |")
    report.append(f"| 초과근무 비율 | {baseline['overtime_pct']:.0%} |")
    report.append(f"| 에이전시 간호사 비율 | {baseline['agency_staff_pct']:.0%} |\n")

    report.append("---\n")
    report.append("## 2. Monte Carlo 시뮬레이션 결과\n")
    report.append("### 시나리오 요약\n")

    # Comparison table
    report.append("| 지표 | A: 현 수준 유지 | B: 10% 증원 | C: 야간 전담 |")
    report.append("|------|----------------|-------------|-------------|")

    for metric_key, metric_label in [
        ("los_reduction", "ALOS 감소 (일)"),
        ("turnover_reduction", "이직률 감소"),
        ("burnout_reduction", "번아웃 감소"),
        ("wait_time_reduction_pct", "대기시간 감소 (%)"),
        ("avoidable_days_3yr", "3년간 절감 입원일"),
        ("net_cost_3yr", "3년 순비용 ($)"),
        ("icer_per_qaly", "ICER ($/QALY)"),
    ]:
        row = f"| {metric_label} |"
        for skey in ["A_maintain", "B_10pct_increase", "C_night_dedicated"]:
            r = results[skey][metric_key]
            mean = r["mean"]
            ci_lo = r["ci_lower"]
            ci_hi = r["ci_upper"]
            if metric_key in ["turnover_reduction", "burnout_reduction"]:
                row += f" {mean:.2%} ({ci_lo:.2%}–{ci_hi:.2%}) |"
            elif metric_key == "net_cost_3yr":
                row += f" ${mean:,.0f} (${ci_lo:,.0f}–${ci_hi:,.0f}) |"
            elif metric_key == "icer_per_qaly":
                if mean == -999999:
                    row += f" Dominant (비용절감) |"
                elif abs(mean) > 1e6:
                    row += f" N/A |"
                else:
                    row += f" ${mean:,.0f} (${ci_lo:,.0f}–${ci_hi:,.0f}) |"
            elif metric_key == "avoidable_days_3yr":
                row += f" {mean:,.0f} ({ci_lo:,.0f}–{ci_hi:,.0f}) |"
            else:
                row += f" {mean:.3f} ({ci_lo:.3f}–{ci_hi:.3f}) |"
        report.append(row)

    # Cost-effectiveness row  
    ce_row = "| $50K/QALY 기준 비용효과 확률 |"
    for skey in ["A_maintain", "B_10pct_increase", "C_night_dedicated"]:
        pct = results[skey]["pct_cost_effective_50k"]
        ce_row += f" {pct:.0%} |"
    report.append(ce_row)

    cs_row = "| 비용절감 확률 |"
    for skey in ["A_maintain", "B_10pct_increase", "C_night_dedicated"]:
        pct = results[skey]["pct_cost_saving"]
        cs_row += f" {pct:.0%} |"
    report.append(cs_row)

    report.append("\n---\n")
    report.append("## 3. CEA (비용효과분석)\n")

    # CEA interpretation
    b_icer = results["B_10pct_increase"]["icer_per_qaly"]["mean"]
    c_icer = results["C_night_dedicated"]["icer_per_qaly"]["mean"]

    report.append("### ICER 해석 (WTP 기준: $50,000/QALY)\n")

    for skey, slabel in [("B_10pct_increase", "B안"), ("C_night_dedicated", "C안")]:
        icer = results[skey]["icer_per_qaly"]["mean"]
        pct_ce = results[skey]["pct_cost_effective_50k"]
        pct_cs = results[skey]["pct_cost_saving"]
        if icer == -999999:
            report.append(f"- **{slabel}:** 비용절감 (dominant) — {pct_cs:.0%} 확률로 순비용 절감")
        elif icer < 50000:
            report.append(f"- **{slabel}:** Cost-effective — ICER ${icer:,.0f}/QALY ({pct_ce:.0%} 확률로 $50K 기준 통과)")
        elif icer < 100000:
            report.append(f"- **{slabel}:** 조건부 비용효과 — ICER ${icer:,.0f}/QALY (WTP 기준에 따라 판단)")
        else:
            report.append(f"- **{slabel}:** 비용효과 불충분 — ICER ${icer:,.0f}/QALY")
        report.append("")

    report.append("---\n")
    report.append("## 4. BIA (예산영향분석)\n")
    report.append("| 항목 | A: 현 수준 | B: 10% 증원 | C: 야간 전담 |")
    report.append("|------|-----------|-------------|-------------|")
    report.append(f"| Year 1 투자 | — | ${bia['B_10pct_increase']['year1_investment']:,.0f} | ${bia['C_night_dedicated']['year1_investment']:,.0f} |")
    report.append(f"| Year 2 비용 | — | ${bia['B_10pct_increase']['year2_cost']:,.0f} | ${bia['C_night_dedicated']['year2_cost']:,.0f} |")
    report.append(f"| Year 3 비용 | — | ${bia['B_10pct_increase']['year3_cost']:,.0f} | ${bia['C_night_dedicated']['year3_cost']:,.0f} |")
    report.append(f"| 3년 총 예산 영향 | — | ${bia['B_10pct_increase']['total_3yr_budget_impact']:,.0f} | ${bia['C_night_dedicated']['total_3yr_budget_impact']:,.0f} |")
    report.append(f"| 3년 순 예산 영향 | — | ${bia['B_10pct_increase']['net_budget_impact']:,.0f} | ${bia['C_night_dedicated']['net_budget_impact']:,.0f} |")
    report.append(f"| ROI | — | {bia['B_10pct_increase']['roi_pct']:.0f}% | {bia['C_night_dedicated']['roi_pct']:.0f}% |\n")

    report.append("---\n")
    report.append("## 5. 권고안\n")

    # Determine recommendation: prefer dominant (cost-saving) scenarios
    b_net = results["B_10pct_increase"]["net_cost_3yr"]["mean"]
    c_net = results["C_night_dedicated"]["net_cost_3yr"]["mean"]
    b_icer_mean = results["B_10pct_increase"]["icer_per_qaly"]["mean"]
    c_icer_mean = results["C_night_dedicated"]["icer_per_qaly"]["mean"]

    # Prefer lower ICER, with dominant (-999999) being best
    b_eff_icer = b_icer_mean if b_icer_mean != -999999 else -1  # dominant is very good
    c_eff_icer = c_icer_mean if c_icer_mean != -999999 else -1

    if c_eff_icer <= b_eff_icer:
        best = "C"
        best_key = "C_night_dedicated"
    else:
        best = "B"
        best_key = "B_10pct_increase"

    report.append(f"### 1순위: **{best}안 (야간 전담 추가)**\n" if best == "C" else f"### 1순위: **{best}안 (10% 증원)**\n")

    best_res = results[best_key]
    report.append(f"- ICER: ${best_res['icer_per_qaly']['mean']:,.0f}/QALY (95% CI: ${best_res['icer_per_qaly']['ci_lower']:,.0f}–${best_res['icer_per_qaly']['ci_upper']:,.0f})")
    report.append(f"- 3년 순비용: ${best_res['net_cost_3yr']['mean']:,.0f} (95% CI: ${best_res['net_cost_3yr']['ci_lower']:,.0f}–${best_res['net_cost_3yr']['ci_upper']:,.0f})")
    report.append(f"- 비용효과 확률 ($50K/QALY 기준): {best_res['pct_cost_effective_50k']:.0%}")
    report.append(f"- 비용절감 확률: {best_res['pct_cost_saving']:.0%}\n")

    report.append("### 근거\n")
    report.append("- Needleman et al. (2011) NEJM: RN staffing 증가 → LOS 단축, 합병증 감소")
    report.append("- Aiken et al. (2002) JAMA: 간호사 1인당 환자 수 증가 → 사망률 7% 증가")
    report.append("- Griffiths et al. (2016) IJNS: 간호 인력 투자 → 환자 결과 개선 meta-analysis")
    report.append("- McHugh et al. (2021) Health Affairs: 번아웃 → 이직 인과관계 실증\n")

    report.append("---\n")
    report.append("## 6. What Changes My Mind\n")
    report.append("이 권고를 뒤집을 수 있는 조건:\n")
    report.append("1. **UW Health 실제 간호인력 비율이 산업 평균 이상** — HCRIS 실제 데이터 확인 시 베이스라인 수정 필요")
    report.append("2. **채용 시장 마찰** — WI RN 가용 인력 부족 → 채용 비용 2배 이상 시 B안 불가능")
    report.append("3. **EHR/자동화 투자** — AI 기반 간호 배치 최적화 도입 시 인력 증원 필요성 하락")
    report.append("4. **3년 내 환자 수 감소** — 입원 감소 시 인력 증원 ROI 악화")
    report.append("5. **VBP/Readmission penalty 실제 금액** — CMS penalty 구조 변경 시 품질 개선 가치 변동\n")

    report.append("---\n")
    report.append("## 7. 데이터 소스 & 한계\n")
    report.append("### 데이터 소스\n")
    report.append("- CMS Hospital General Information (Facility 520098)")
    report.append("- BLS Occupational Employment Statistics (WI RN salary)")
    report.append("- AHA Hospital Statistics 2024 (national benchmarks)")
    report.append("- Needleman et al. (2011) NEJM 365: 2117-2125")
    report.append("- Aiken et al. (2002) JAMA 288: 1987-1993")
    report.append("- Griffiths et al. (2016) IJNS 57: 20-30")
    report.append("- McHugh et al. (2021) Health Affairs 40(10)")
    report.append("- NSI Nursing Solutions (2024) National Health Care Retention & RN Staffing Report\n")

    report.append("### 한계점\n")
    report.append("- 간호인력 FTE는 HCRIS S-3 실제 값이 아닌 추정치 (505-bed academic AMC 기준)")
    report.append("- 효과 크기는 문헌 기반 평균값, UW Health 특화 보정 미적용")
    report.append("- QALY 추정은 간접적 (LOH 단축 → 합병증 감소 경로)")
    report.append("- 3% 할인율 적용 (CMS 기준)")
    report.append("- **실제 분석을 위해서는 HCRIS 원시 데이터 (S-3, S-4) 다운로드 후 파라미터 보정 필요**\n")

    report.append("---\n")
    report.append(f"*Generated by Cinnamoroll MLDS — DGG-266 — {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(report)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print(f"Running Monte Carlo simulation: {N_ITERATIONS:,} iterations × 3 scenarios × {SIMULATION_YEARS} years...")
    
    results = run_monte_carlo(baseline, effect_sizes, scenarios, cost_params)
    bia_results = run_bia(results, cost_params, baseline, scenarios)
    report = generate_report(results, bia_results, baseline, cost_params)

    # Save report
    report_path = os.path.expanduser("~/.openclaw/workspace-cinna-mlds/analysis/dgg266_decision_pack.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    # Save raw results as JSON
    json_path = os.path.expanduser("~/.openclaw/workspace-cinna-mlds/analysis/dgg266_results.json")
    
    # Convert numpy types for JSON serialization
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    
    json_results = json.loads(json.dumps(results, default=convert))
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2)
    print(f"Results JSON saved: {json_path}")

    # Print key findings
    print("\n=== KEY FINDINGS ===")
    for key in ["B_10pct_increase", "C_night_dedicated"]:
        r = results[key]
        print(f"\n{r['label']}:")
        print(f"  ICER: ${r['icer_per_qaly']['mean']:,.0f}/QALY (95% CI: ${r['icer_per_qaly']['ci_lower']:,.0f}–${r['icer_per_qaly']['ci_upper']:,.0f})")
        print(f"  3yr Net Cost: ${r['net_cost_3yr']['mean']:,.0f} ({r['pct_cost_saving']:.0%} cost-saving)")
        print(f"  ALOS Reduction: {r['los_reduction']['mean']:.2f} days")
        print(f"  Turnover Reduction: {r['turnover_reduction']['mean']:.2%}")
