---
owner: cinnamoroll
last_reviewed: 2026-04-14
review_cycle: monthly
ssot: repo://docs
source: "DGG-656 | CEO Lina Song, Slack #5_sales 2026-04-12 | src/lib/showcase-stage5.ts"
refresh_log: "DGG-918 AC2 — 2026-04-14 crosswalk refresh. demo-script vs code threshold 불일치 확인됨. 본문 변경 없음, Gaps 섹션에 DGG-918 판단 추가."
---

# Reversal Trigger Specification

> DGG-656 AC2 — Stage 5 Reversal condition standardization
> Source: CEO Lina Song demo-talking-points.md Stage 5 + src/lib/showcase-stage5.ts runtime implementation

## 1. Concept

Reversal triggers define when a previously optimal decision should be reconsidered.
They are set at decision time and monitored continuously. The system alerts when conditions cross defined thresholds.

Core principle: *"Most decisions are made once and never revisited. Entity Flow bakes in the reversal conditions at the time of the decision."* — Lina Song

---

## 2. Stage 5 Demo Script (Source of Truth)

> "If wait times exceed 35 minutes for 3 consecutive weeks — the system flags it. You don't have to remember to check." — Lina Song, Stage 5

This framing guides the standardization: **KPI + threshold × duration**.

---

## 3. Standard Reversal Conditions

### 3.1 Primary Reversal Conditions (Production-Grade)

| ID | KPI / Trigger | Condition | Threshold | Unit | Monitoring Window | Action on Trigger |
|----|--------------|-----------|-----------|------|-------------------|-------------------|
| `rev-denial` | Denial Rate Spike | Payer-specific denial rate exceeds pre-authorization benchmark | ≥ +5pp | pp (percentage points) | Ongoing (rolling) | Escalate to payer relations; pause new authorization protocols |
| `rev-bed-gap` | Post-Acute Bed Availability | Post-acute SNF bed availability falls below critical threshold | < 80% | % | Ongoing (rolling) | Re-evaluate DC Closure impact; divert to alternate SNF partners |
| `rev-los` | Length of Stay Drift | Average LOS increases vs intervention target | > +0.5d | days | Weekly (rolling 4-week avg) | Conduct root cause analysis; pause ED Fast Track if necessary |

### 3.2 Monitoring Signals (Real-Time Dashboard Indicators)

| ID | Signal | Display Unit | Alert Threshold | Status Indicator |
|----|--------|-------------|-----------------|-----------------|
| `sig-boarding` | ED Boarding Hours | hours | > 4.5h → alert | alert/normal/watch |
| `sig-recovery` | Revenue Recovery (Est.) | $K | trending | normal |
| `sig-staff` | Staff Readiness | % | < 75% → watch | watch/normal |

### 3.3 Revisit Triggers (Scheduled Review)

| ID | Condition | Rationale | Suggested Review Date | Priority |
|----|-----------|-----------|----------------------|----------|
| `rt-1` | Q2 Denial Rate Review | Contract renewal window — benchmark may shift | Apr 15, 2026 | high |
| `rt-2` | ROI Verification | Validate projected recovery against actual P&L variance | May 30, 2026 | medium |

---

## 4. Stage 4 Tornado Variables

> DGG-656 AC1 — Stage 4 Tornado chart variables and their mapping to engine sensitivity analysis

### 4.1 Demo Script Reference

> "This answers the question every COO has but rarely gets: 'What's the one variable that could make this decision wrong?'" — Lina Song, Stage 4

### 4.2 Engine Sensitivity Parameters (from src/engine/analysis/sensitivity.ts)

One-way sensitivity analysis: each parameter varied ±10% while others held at base.

| Parameter ID | Name | Base | Low | High | Unit | ICER Range Impact |
|-------------|------|------|-----|------|------|-------------------|
| `cost_per_unit` | Cost per Unit | 1.0 | 0.8 | 1.2 | multiplier | High |
| `demand_rate` | Demand Rate | 1.0 | 0.8 | 1.2 | multiplier | High |
| `capacity` | Capacity | 1.0 | 0.9 | 1.1 | multiplier | Medium |
| `coverage` | Coverage | 1.0 | 0.85 | 1.0 | multiplier | Medium |
| `effect_magnitude` | Effect Magnitude | 1.0 | 0.7 | 1.3 | multiplier | Highest |
| `discount_rate` | Discount Rate | 0.03 | 0.0 | 0.05 | rate | Low |
| `time_horizon` | Time Horizon | 1.0 | 0.5 | 2.0 | multiplier | Medium |
| `overhead_cost` | Overhead Cost | 1.0 | 0.8 | 1.2 | multiplier | Medium |

### 4.3 Demo-Specific Tornado Display (Stage 4)

Demo tornado chart shows **top 3-5 most sensitive variables** ranked by swing width.
Code: `src/services/sensitivity/SensitivityService.ts` + `src/components/showcase/tornado/`

Engine computes ICER (Incremental Cost-Effectiveness Ratio) at each parameter bound.
Tornado bars sorted by `icerRange` descending. Largest swing = widest bar = most decision-critical variable.

---

## 5. ROI / Value Prop Assumptions and Limitations

> DGG-656 AC3 — ROI Calculator assumptions documentation

### 5.1 ROI Table (from docs/sales/roi-calculator.md)

| Tier | Investment | Avoided Cost | ROI | Payback |
|------|-----------|-------------|-----|---------|
| CAH (25-50 beds) | $42K | $500K-$4.5M | 12-107x | < 12 months |
| Mid-size (100-300 beds) | $96K | $1M-$5M | 10-52x | < 12 months |
| Large (300+ beds) | $150K | $2M-$10M | 13-67x | < 12 months |

### 5.2 Key Assumptions

These ROI figures are **illustrative ranges based on aggregate benchmarks**, not hospital-specific projections. Required assumptions for figures to hold:

**Population:**
- CAH: 25-50 licensed beds, independent, rural, >= 35 miles from next hospital
- Mid-size: 100-300 beds, mid-market suburban/urban, regional system or independent
- Large: 300+ beds, academic or large regional system

**Decision Type:**
- Service line viability (highest ROI due to capital at risk)
- Staffing model changes (OR scheduling, nurse ratios)
- Capital allocation (equipment, facility investment)

**Data Quality Prerequisites:**
- Minimum 12 months of operational data (throughput, cost, quality metrics)
- Decision-makers with authority to implement changes
- No major external shocks (pandemic, regulatory change, payer mix shift > 20%)

**Calculational Basis:**
- ROI = (Avoided Cost / Investment) — based on decision-specific cost modeling
- Avoided Cost estimates derived from literature on operational improvement ROI in hospital settings
- Ranges reflect uncertainty: CAH variability higher due to smaller sample size

**Known Limitations:**
- Figures do not account for implementation friction (staff adoption, governance approval)
- "Avoided cost" requires operational definition — savings materialize only if recommendations are acted upon
- Payback < 12 months assumes mid-point of avoided cost range ($2M for CAH midpoint)
- No adjustment for risk-adjusted discount rate

### 5.3 Citation / External Reference

- Becker's Hospital Review: operational improvement ROI benchmarks cited in sales discovery guide
- CMA (Certified Medical Accountant) guidelines for healthcare capital allocation
- Literature: "Return on Investment in Healthcare Quality Improvement" — applicable to operational decision support tools

---

## 6. Implementation Map

| File | Role |
|------|------|
| `src/lib/showcase-stage5.ts` | Runtime reversal condition builder |
| `src/engine/analysis/sensitivity.ts` | One-way sensitivity analysis engine |
| `src/services/sensitivity/SensitivityService.ts` | PSA service + tornado data generation |
| `src/types/analysis.ts` | SensitivityParameter types + DEFAULT_SENSITIVITY_PARAMETERS |
| `docs/product/demo-talking-points.md` | Stage 4/5 script source of truth |

---

## 7. Gaps / Open Items

- [ ] `reversal-trigger-spec.md` is defined but not yet linked from any production component
- [ ] No centralized reversal rule registry (conditions defined ad-hoc in showcase-stage5.ts)
- [ ] Stage 5 "35 minutes for 3 consecutive weeks" (from demo script) is NOT reflected in current `showcase-stage5.ts` — uses different thresholds (denial rate, bed capacity, LOS)
- [ ] Recommend: consolidate demo-script-level triggers (35min/3wk) into formal reversal condition schema

### DGG-918 Refresh Assessment (2026-04-14)
- **Status:** Current. Spec 내용은 여전히 유효.
- **Issue:** Demo script(35min/3wk)과 code threshold(denial rate/bed/LOS) 불일치가 unresolved. Buyer-facing copy에서는 "designed to include reversal conditions"로 표현하고, 구체 수치는 demo 기준으로만 사용 권장.
- **Action:** 코드-Spec 정렬은 별도 이슈로 분리 필요. 현재는 copy guardrail로 관리.
