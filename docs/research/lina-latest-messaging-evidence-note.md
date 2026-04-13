---
owner: cinnamoroll
created: 2026-04-14
last_reviewed: 2026-04-14
source_issue: DGG-918
status: current
---

# Lina Latest Messaging — Evidence Crosswalk

> DGG-918 AC1/AC3 — buyer-facing claim ↔ model/evidence 매핑
> 기준일: 2026-04-14 | canon: Lina 4/9~4/13 messaging + current demo Stage 1-5

## Claim-to-Evidence Crosswalk

### ✅ 지금 바로 써도 되는 문구 (Safe to Use)

| # | Claim | Product Surface | Evidence | Assumptions/Bounds | Copy Guardrail |
|---|-------|----------------|----------|---------------------|----------------|
| 1 | "Decision Pack = auditable decisions" | Stage 3 Decision Pack output | `src/lib/showcase-stage3.ts`에서 decision audit trail 생성. 각 의사결정에 KPI, evidence, rationale 필드 포함. 코드에 구현 완료. | demo showcase 기준. production 환경에서는 persistence layer 필요 | 기능 구현 완료. "every decision is traceable" OK |
| 2 | "AI predicts. We decide." | 전체 product positioning | Entity Flow 아키텍처: AI는 recommendation만 제공, 최종 결정은 human. Stage 5 reversal도 human alert 구조. | 포지셔닝 문구. 기술적 근거 정확 — AI autonomy 없음 | 안전. 이 포지셔닝 그대로 사용 가능 |
| 3 | "$56M+ TAM" | Sales one-pager, pitch deck | 산술: WI CAH 58개 × avg revenue + rural hospital market size. 공개 데이터(HRSA, AHA) 기반 | CAH-only TAM. 전체 WI hospital 포함 시 더 큼. Methodology 공개 가능 | "검증 가능한 산술"로 표현. 벤치마크 출처와 함께 |
| 4 | "$500K-$4.5M avoided cost" (CAH tier) | ROI calculator, value-prop.md | Industry average 기반: denied claims recovery, throughput 개선, agency staffing 절감. Becker's Hospital Review + CMA guidelines 참조 | Specific hospital 실적 아님. Industry benchmark range. "estimated" 또는 "based on industry averages" disclaimer 필수 | "up to" 또는 "estimated range"로 한정. "guaranteed" 금지 |

### ⚠️ 과장 위험 있는 문구 (Use with Qualification)

| # | Claim | Product Surface | Evidence | Assumptions/Bounds | Copy Guardrail |
|---|-------|----------------|----------|---------------------|----------------|
| 5 | "12-107x ROI" | ROI calculator table | ROI = Avoided Cost / Investment. CAH tier: $42K investment / $500K-$4.5M avoided cost = 12-107x | 107x는 *optimistic end*. 모든 가정이 맞아야 도달. CAH 샘플 작아 variability 큼 | Range로만 표시. "up to 107x"도 위험 — "12-50x range, up to 100x under optimal conditions" 권장 |
| 6 | "Reversal conditions built into every decision" | Stage 5 showcase | Spec은 `reversal-trigger-spec.md`에 정의. `src/lib/showcase-stage5.ts`에 구현. | Demo script의 "35 min / 3 consecutive weeks" ≠ 코드 구현 threshold (denial rate, bed capacity, LOS 사용). Spec-code 불일치 존재 | "designed to include reversal conditions"로 표현. "automatically monitors"는 OK, 구체 수치는 demo 기준으로만 |
| 7 | "Tornado chart: what makes this decision wrong" | Stage 4 showcase | `src/engine/analysis/sensitivity.ts` + `SensitivityService.ts`에서 one-way sensitivity analysis 구현. Tornado bar chart 생성됨 | Sensitivity parameter coeff가 expert placeholder (base=1.0, low=0.7-0.9, high=1.1-1.3). Calibrated data 아님 | "modeled sensitivity"로 표현. "proven sensitivity" 금지. "helps identify key drivers" OK |

### 🔴 보류할 문구 (Hold — Insufficient Evidence)

| # | Claim | Product Surface | Evidence | Why Hold | Resolution |
|---|-------|----------------|----------|----------|------------|
| 8 | "40+ hours saved" (mid-size COO) | Sales copy, one-pager | 근거 산출 내역 없음. 어느 workflow, 몇 개 decision, 어떤 기준으로 40h인지 불명 | 계산 방법이 명시되지 않음. Guess estimate | 제거 또는 근거 계산 필요: decision count × time-per-decision × frequency |
| 9 | "Real-time optimization" | Product description | Dashboard는 구현되어 있으나 "real-time"은 batch/periodic update일 가능성. 데이터 refresh rate 불명 | "Real-time"의 정의가 모호. 연속 vs. daily/weekly batch | "continuous monitoring" 또는 "automated tracking"으로 변경. refresh rate 확인 후 재검토 |
| 10 | "Proven ROI" (implied in some copy) | Various | ROI가 아직 pilot/실적 기반이 아님. Industry benchmark + model 기반. | "Proven"은 실적 data 필요. 현재는 projected | "projected ROI based on industry benchmarks"로 변경. 첫 customer 실적 후 "proven" 가능 |

## Methodology

- Source: Lina 4/9~4/13 messaging + current demo Stage 1-5 code review
- 각 claim은 `product surface → model evidence → assumption bounds → copy guardrail` 4레이어로 검증
- Evidence tier: ✅ 코드 구현 확인 > ⚠️ 구현+한계 있음 > 🔴 근거 부족
- 이 문서는 DGG-918 AC1/AC3 검증용 SSOT

## Open Items

- [ ] "40+ hours saved" 근거 계산 or 제거
- [ ] "Real-time" 데이터 refresh rate 확인
- [ ] 첫 customer pilot 후 "proven ROI" 전환 검증
- [ ] Demo script (35min/3wk) ↔ code threshold 불일치 해소
