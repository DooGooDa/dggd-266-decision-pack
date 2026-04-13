---
owner: cinnamoroll
created: 2026-04-12
last_reviewed: 2026-04-14
review_cycle: monthly
ssot: repo://docs
source: "DGG-656 | src/engine/analysis/sensitivity.ts, SensitivityService.ts"
status: current
refresh_log: "DGG-918 AC2 — 2026-04-14 crosswalk refresh. parameter coeff가 expert placeholder임을 명시. copy guardrail 추가."
---

# Tornado Variable Specification

> DGG-656 AC1 — Stage 4 Tornado chart variables
> Crosswalk: see `lina-latest-messaging-evidence-note.md` Claim #7

## Engine Sensitivity Parameters

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

## Implementation Map

| File | Role |
|------|------|
| `src/engine/analysis/sensitivity.ts` | One-way sensitivity analysis engine |
| `src/services/sensitivity/SensitivityService.ts` | PSA service + tornado data generation |
| `src/types/analysis.ts` | SensitivityParameter types + DEFAULT_SENSITIVITY_PARAMETERS |
| `src/components/showcase/tornado/` | Tornado chart UI component |

## DGG-918 Refresh Assessment (2026-04-14)

- **Status:** Current. Parameter set과 코드 매핑은 유효.
- **Critical note:** Sensitivity parameter coefficients (base=1.0, low=0.7-0.9, high=1.1-1.3) are **expert placeholders**, not calibrated from empirical data. Tornado chart의 swing width는 이 placeholder 값에 의존.
- **Copy guardrail:** "modeled sensitivity"로 표현. "proven" / "calibrated" 금지. "helps identify key decision drivers" OK.
- **Open:** Empirical calibration 필요 (첫 customer data 확보 후).

## Gaps / Open Items

- [ ] Parameter coeff empirical calibration
- [ ] PSA (Probabilistic Sensitivity Analysis) 결과와 tornado 1-way 결과 비교 검증
- [ ] Demo tornado shows top 3-5 — parameter selection criteria 명확화
