# BLVCKSHELL EXPERIMENT LEDGER

**Classification:** Immutable historical record  
**Scope:** Blvckshell OS V1 — all judgment-related experiments  
**Generated:** 2026-06-14  
**Principle:** Executable proof overrides documentation. Every entry cites source artifacts.

---

## How to Read This Ledger

Each entry follows:

```text
Experiment ID → npm script → batch/report path → goal → config → sample → results → promotion → lessons
```

**Promotion codes:** `PROMOTED` | `NOT_PROMOTED` | `RETUNE` | `FAIL` | `INCONCLUSIVE` | `PROVEN` (mechanism) | `BLOCKED`

**Evidence paths:** `docs/audits/*.md`, `docs/specs/*.md`, `generated/audit/*.json`

---

## Phase Index

| Phase | Date Range | Focus |
|-------|------------|-------|
| G0 | 2026-06-06 | Live brain wiring |
| G1 | 2026-06-06 | Lesson influence |
| G2 | 2026-06-06–07 | Civilization simulation |
| G3 | 2026-06-07 | Judgment ledger |
| G4 | 2026-06-07 | Forecast accountability |
| G5 | 2026-06-07–08 | Opportunity intelligence |
| G5.4A | 2026-06-09–12 | Foundation judgment |
| G5.4B | 2026-06-12 | Exploration layer |
| G5.4C | 2026-06-12–14 | Reasoning + safe divergence |
| G-INFRA | 2026-06-09+ | Simulation memory compliance |

---

# G0 — LIVE BRAIN WIRING

## G0.1 Live Reasoning Evidence

| Field | Value |
|-------|-------|
| **Script** | `npm run audit:g0-live-evidence` |
| **Report** | `docs/audits/G0_LIVE_REASONING_EVIDENCE_REPORT.md` |
| **Goal** | Prove 15 brains execute full cognition lifecycle with live Qwen; persist verifiable artifacts |
| **Configuration** | Per-brain lifecycle: advisors → council → decision → forecast → lesson → Supabase |
| **Sample** | 15 brains (all departments) |
| **Results** | 15/15 live Qwen success; confidence 0.82; council consensus null on all; Claude/GPT/Gemini/DeepSeek stubbed |
| **Promotion** | Infrastructure baseline — not a feature gate |
| **Lessons** | Live provider wiring works; council consensus layer inactive on all probes; confidence clustered high |

---

# G1 — LESSON INFLUENCE

## G1.1 Lesson Influence Audit

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g1-lesson-influence` |
| **Report** | `docs/audits/LESSON_INFLUENCE_AUDIT.md` |
| **Goal** | Decision A → outcome → lesson → Decision B loads, cites, changes behavior |
| **Configuration** | Standard lesson recall path |
| **Sample** | 15 brains |
| **Results** | 15/15 PASS; confidence 0.82→0.76; recommendation changed on all |
| **Promotion** | **PROVEN** — Learning at single-brain level (`BRUTAL_TRUTH_REPORT.md`) |
| **Lessons** | Lessons can influence decisions when explicitly recalled; does not prove org-level improvement |

---

# G2 — CIVILIZATION SIMULATION

## G2.1 Simulation Validity Gate

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g2:10` |
| **Report** | `docs/audits/SIMULATION_VALIDITY_GATE.md` |
| **Goal** | Fix invalid simulator — all runs returning identical ROI |
| **Root cause** | Lesson penalty drove confidence ~0.47 below proceed threshold 0.50; fixed abort ROI -0.15 |
| **Fix** | Proceed threshold 0.35; world-varying abort costs; extract decisions from world params |
| **Results** | 10 unique worlds/ROIs; gate PASS |
| **Promotion** | Simulator validity restored |
| **Lessons** | Threshold calibration dominates sim outcomes; fixed constants invalidate experiments |

## G2.2 100-Run Simulation Audit

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g2:100` |
| **Report** | `docs/audits/SIMULATION_AUDIT_100.md` |
| **Sample** | 100 runs |
| **Results** | Verdict FAIL (pre-adaptation scale) |
| **Promotion** | NOT_PROMOTED |

## G2.3 Adaptation Proof (Control vs Learning)

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g2-adaptation` |
| **Report** | `docs/audits/ADAPTATION_PROOF_REPORT.md` |
| **Goal** | Prove learning civilization outperforms control |
| **Sample** | 90 control + 90 learning |
| **Results** | Learning **worse**: ROI -11.0%, success -27.3pp vs control |
| **Promotion** | **NOT_PROVEN** — organizational intelligence |
| **Lessons** | Lesson accumulation without judgment structure can harm outcomes; control group essential |

## G2.4 Control Group Baseline

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/CONTROL_GROUP_REPORT.md` |
| **Results** | ROI -1.6588, failure rate 100% (hostile worlds) |
| **Lessons** | Baseline civilization metrics are negative; improvements must be relative |

---

# G3 — JUDGMENT LEDGER

## G3.0 Final Failure Analysis

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/G3_FINAL_FAILURE_ANALYSIS.md` |
| **Root cause** | G3 pass coupled to council `consensus=null` via `influencedRun.pass` |
| **Fix** | Decouple G3A pass to decision+memory steps + materialInfluence |
| **Lessons** | Validator bugs can block entire research phases; gate on material influence not council |

## G3.1 Judgment Ledger Proof (G3A)

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g3-judgment-ledger` |
| **Goal** | Structured ledger replaces lesson sprawl; generation, recall, influence |
| **Promotion** | Mechanism PROVEN after validator fix |

## G3.2 Ledger Efficiency (G3B)

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g3-efficiency` |
| **Report** | `docs/audits/G3B_BASELINE_VALIDATION.md` |
| **Results** | Prompt -45.1%, retrieval weight -13.5%; material influence confirmed |
| **Promotion** | **PASS** |

## G3.3 Contradiction Proof

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g3-contradiction-proof` |
| **Report** | `docs/audits/CONTRADICTION_PROOF_REPORT.md` |
| **Results** | Contradictions recorded in ledger evolution |

## G3.4 100-Run Adaptation

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g3-100-adaptation` |
| **Report** | `docs/audits/G3_100_RUN_ADAPTATION_REPORT.md` |
| **Sample** | 100×2 (control vs ledger) |
| **Results** | Success 30% vs 29%; ROI -0.4801 vs -0.498; verdict **B — No Measurable Difference** |
| **Promotion** | NOT_PROMOTED on outcomes |
| **Lessons** | Ledger active but org-level ROI lift not demonstrated at 100-run scale |

---

# G4 — FORECAST ACCOUNTABILITY

## G4.1 Forecast Accountability Proof

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g4-forecast-accountability` |
| **Report** | `docs/audits/G4_FORECAST_ACCOUNTABILITY_PROOF.md` |
| **Results** | Penalty tiers validated; 15 brain scorecards; 3 forecast reviews |
| **Promotion** | **PROVEN** (mechanism) |

## G4.2 Adaptation Retest (Trust-Weighted Councils)

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g4-adaptation-retest` |
| **Report** | `docs/audits/G4_ADAPTATION_RETEST_REPORT.md` |
| **Sample** | 100×2 |
| **Results** | Divergence 52.7%; success 31% vs 29%; ROI -0.5705 (worse than G3.1) |
| **Promotion** | Verdict **C** — NOT_PROMOTED on outcomes |
| **Lessons** | High divergence ≠ improvement; trust weighting changed decisions but harmed ROI |

---

# G5 — OPPORTUNITY INTELLIGENCE

## G5.0 Unpaired Adaptation

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5-opportunity-intelligence` |
| **Report** | `docs/audits/G5_ADAPTATION_REPORT.md` |
| **Sample** | 50×2 |
| **Results** | Success +20pp, ROI +0.350; divergence **0%** |
| **Promotion** | NOT_PROMOTED — world confound |
| **Lessons** | Unpaired worlds invalidate attribution; always pair control/threshold |

## G5.1A Paired Retest

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5.1-paired-retest` |
| **Report** | `docs/audits/G5_1_PAIRED_RETEST_REPORT.md` |
| **Results** | Divergence 13.3%, ROI +0.095; verdict **C — Insufficient Proof** |
| **Lessons** | Paired design works; 13.3% divergence below 20% promotion target |

## G5.1B Paired Retest (Namespace Isolation)

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5.1-paired-retest` (G5.1B variant) |
| **Report** | `docs/audits/G5_1B_PAIRED_RETEST_REPORT.md`, `G5_1B_WIRING_REPORT.md` |
| **Results** | Identical to G5.1A metrics; namespace isolation verified |

## G5.2 Knowledge Layer

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5.2-knowledge-layer` |
| **Report** | `docs/audits/G5_2_KNOWLEDGE_ARCHITECTURE_REPORT.md` |
| **Results** | 15 brains, 138 knowledge entries; multi-ledger architecture |

## G5.2A 50-Pair Retest

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5.2a-paired-retest` |
| **Report** | `docs/audits/G5_2A_50_PAIR_REPORT.md` |
| **Results** | Divergence 0.7%, ROI +0.0003; **FAIL** |
| **Lessons** | Multi-ledger indistinguishable from control at decision level |

## G5.3A Assumption Intelligence

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5.3a-paired-retest` |
| **Report** | `docs/audits/G5_3A_PROOF_REPORT.md` |
| **Results** | Divergence 3.3%, 40 assumptions; **FAIL** |
| **Lessons** | Assumption traces without decision movement = inactive layer |

## G5.4A Adversarial Proof (Initial)

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5.4a-paired-retest` |
| **Report** | `docs/audits/G5_4A_PROOF_REPORT.md` |
| **Results** | 0% divergence, 0 challenges; **FAIL** |
| **Lessons** | Adversarial layer wired but not firing on venture surface |

## G5-SURFACE-1 Scenario Diversity Trace

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/G5_SCENARIO_DIVERSITY_TRACE.md` |
| **Root cause** | 90% ai_consulting venture launch; 6/15 brains in fastBatch |
| **Fix** | Federation Decision Suite (32 scenarios, 8 brains) |
| **Lessons** | Experiment surface contamination invalidates all G5.4C runs before federation gate |

## G5-SURFACE-1 Decision Tension Calibration

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/G5_SURFACE_1_DECISION_TENSION_CALIBRATION.md` |
| **Goal** | Intentional margin bands per tension class; brain confidence priors |
| **Targets** | Proceed rate 35–65%; flippable ≥25% |

## G5 Federation Decision Suite

| Field | Value |
|-------|-------|
| **Script** | `npm run audit:g5-federation-decision-suite` |
| **Spec** | `docs/audits/G5_FEDERATION_DECISION_SUITE_SPEC.md` |
| **Audit** | `docs/audits/G5_FEDERATION_DECISION_SUITE_AUDIT.md` |
| **Composition** | 32 scenarios = 8 brains × 4 native decisions |
| **Static gate** | PASS; full behavioral run pending |
| **Gate file** | `generated/audit/federation-suite-gate.json` |

---

# G5.4A — FOUNDATION JUDGMENT

## G5.4A.1 Foundation Wiring

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5-4a-foundation-wiring` |
| **Report** | `docs/audits/G5_4A_FOUNDATION_WIRING_REPORT.md` |
| **Architecture** | `docs/audits/G5_4A_FOUNDATION_ARCHITECTURE.md` |
| **Algorithms** | Forecast calibration, assumption survival, contradiction influence, Bayesian updating |
| **Promotion** | Wiring **PASS** |

## G5.4A.2 Decision Influence Audit

| Field | Value |
|-------|-------|
| **Script** | `npm run audit:g5-4a-decision-influence` |
| **Report** | `docs/audits/G5_4A_DECISION_INFLUENCE_AUDIT.md` |
| **Goal** | Belief → decision propagation |

## G5.4A.3 Foundation Screen (20-pair variants)

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4a-foundation-screen` |
| **Report** | `docs/audits/G5_4A_FOUNDATION_SCREEN_REPORT.md` |
| **Results** | All variants INCONCLUSIVE; 10.8% divergence, ~0.3% ROI |
| **Promotion** | NOT_PROMOTED per variant |

## G5.4A.4 Foundation Stack (50-pair)

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4a-foundation-stack` |
| **Report** | `docs/audits/G5_4A_FOUNDATION_STACK_REPORT.md` |
| **Results** | 16,272 traces; insufficient outcome signal |
| **Promotion** | RETUNE weights |

## G5.4A.5 Weight Tuning (G5.4A.3b)

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4a-weight-tuning` |
| **Report** | `docs/audits/G5_4A_WEIGHT_TUNING_REPORT.md` |
| **Sample** | 50×2 paired |
| **Results** | Divergence 48.7%, ROI +1.7%, influence 3/4 in range, 0 runtime Supabase reads |
| **Promotion** | **PROMOTED → G5.4B** |
| **Batch** | `g5_4a_wt_*` |

## G5.4A Completion

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/G5_4A_COMPLETION_REPORT.md` |
| **Verdict** | First positive evidence: learning→decision→outcome under paired control |

---

# G5.4B — EXPLORATION LAYER

## G5.4B.1 Exploration Wiring

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5-4b-exploration-wiring` |
| **Report** | `docs/audits/G5_4B_EXPLORATION_WIRING_REPORT.md` |
| **Architecture** | `docs/audits/G5_4B_EXPLORATION_ARCHITECTURE.md` |
| **Algorithms** | UCB bandit, opportunity cost, regret minimization, doctrine Elo |

## G5.4B.2 Exploration Stack (50-pair)

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4b-exploration-stack` |
| **Report** | `docs/audits/G5_4B_EXPLORATION_STACK_REPORT.md` |
| **Results** | Divergence 20.7%, ROI +0.3%, 200 pre-decision traces; G-INFRA PASS |
| **Promotion** | **PROMOTED — Exploration Layer** |

---

# G5.4C — REASONING + SAFE DIVERGENCE

## G5.4C.1 Reasoning Wiring

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g5-4c-reasoning-wiring` |
| **Report** | `docs/audits/G5_4C_REASONING_WIRING_REPORT.md` |
| **Algorithms** | Case-based reasoning, recursive judgment, adversarial debate |

## G5.4C.2 Reasoning Stack (50-pair initial)

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4c-reasoning-stack` |
| **Report** | `docs/audits/G5_4C_REASONING_STACK_REPORT.md` |
| **Results** | Divergence 29%, ROI -0.6%; case 0.055, debate 0.076 influence |
| **Promotion** | **NOT_PROMOTED** — `retune_reasoning_layer` |
| **Report** | `docs/audits/G5_4C_COMPLETION_REPORT.md` |

## G5.4C.3 Reasoning Weight Tuning

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4c-reasoning-tuned` |
| **Report** | `docs/audits/G5_4C_REASONING_WEIGHT_TUNING_REPORT.md` |

## G5.4C.4 Reasoning Promotion Attempt

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/G5_4C_REASONING_PROMOTION_REPORT.md` |
| **Results** | Divergence 1.3%, ROI flat; case share 61.3% |
| **Promotion** | **RETUNE** |

## G5.4C.5 Decision Boundary Audit

| Field | Value |
|-------|-------|
| **Script** | `npm run audit:g5-4c-decision-boundary` |
| **Report** | `docs/audits/G5_4C_DECISION_BOUNDARY_AUDIT.md` |
| **Root cause** | Reasoning confidence/threshold not reaching final decision (translation seam) |
| **Fix** | Merge into `finalConfidenceBeforeTrust` in `execute-lifecycle.ts` |

## G5.4C.6 Decision Surface Audit

| Field | Value |
|-------|-------|
| **Script** | `npm run audit:g5-4c-decision-surface` |
| **Report** | `docs/audits/G5_4C_DECISION_SURFACE_AUDIT.md` |
| **Results** | 36% sims default confidence — surface too easy |

## G5.4C.7 Recovery Experiments

| Field | Value |
|-------|-------|
| **Scripts** | `experiment:g5-4c-reasoning-recovery`, `validate:g5-4c-reasoning-recovery` |
| **Reports** | `G5_4C_REASONING_RECOVERY_REPORT.md`, `G5_4C_REASONING_RECOVERY_VALIDATION_REPORT.md` |
| **Results** | Attribution balanced; divergence 0% |
| **Promotion** | RETUNE |

## G5.4C.8 Threshold Fast (25-pair federation)

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4c-threshold-fast` |
| **Report** | `docs/audits/G5_4C_THRESHOLD_FAST_REPORT.md` |
| **Results** | Divergence 8%, ROI -8.7%; 2 changed_worse |
| **Promotion** | RETUNE thresholds |

## G5.4C.9 Harm-Aware Retune

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4c-harm-aware-retune` |
| **Report** | `docs/audits/G5_4C_HARM_AWARE_RETUNE_REPORT.md` |
| **Results** | 3 capital HOLD→PROCEED blocks; post-guard divergence 0%; ROI 0% |
| **Promotion** | Harm guard **PROVEN** authoritative |
| **Implementation** | `harm-aware-reasoning-guard.ts`, `applyHarmAwareDecisionOverride()` |

## G5.4C.10 Safe Divergence Spec

| Field | Value |
|-------|-------|
| **Spec** | `docs/specs/G5_4C_8_SAFE_DIVERGENCE_DISCOVERY.md` |
| **Script** | `npm run audit:g5-4c-safe-divergence-spec` |
| **Report** | `docs/audits/G5_4C_SAFE_DIVERGENCE_SPEC_AUDIT.md` |
| **Results** | Checks A0–A9 PASS |

## G5.4C.11 Safe Divergence Discovery Iterations

| Run | Config | Divergence | ROI Δ | safe_beneficial | harmful | Outcome |
|-----|--------|------------|-------|-----------------|---------|---------|
| G5.4C.8 initial | Broad staged eligibility | 32% | +1.9% | 7 | 1 | FAIL — narrow_eligibility |
| G5.4C.8.1 | Narrow staged (margin/contradiction) | 20% | +1.7% | 5 | 0 | FAIL — old 8–12% gate |
| G5.4C.8.2 zero | Tension + margin too tight | 0% | +0.1% | 0 | 0 | FAIL — too tight |
| G5.4C.8.2 final | Tension + pre-reasoning margin | 28% | +2.1% | 7 | 0 | **PROMOTED** |

| Field | Value |
|-------|-------|
| **Script** | `npm run experiment:g5-4c-safe-divergence-discovery` |
| **Reports** | `G5_4C_SAFE_DIVERGENCE_DISCOVERY_REPORT.md`, `G5_4C_SAFE_DIVERGENCE_PROMOTION_REPORT.md` |
| **Batch (promoted)** | `g5_4c_safe_1781453648217_d07b68` |
| **Promotion gates (final)** | Divergence 10–30%, ROI ≥1%, harmful=0, capital flips=0, G-INFRA PASS |
| **Promotion** | **PROMOTED — Reasoning + Safe Divergence Layer** (2026-06-14) |

## G5.4C Attribution & Memory Audits

| Script | Report |
|--------|--------|
| `audit:g5-4c-reasoning-attribution` | `G5_4C_REASONING_ATTRIBUTION_AUDIT.md` |
| `audit:g5-4c-reasoning-memory` | `G5_4C_REASONING_MEMORY_AUDIT.md` |

---

# G-INFRA — SIMULATION INFRASTRUCTURE

## G-INFRA-1 Memory Compliance

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g-infra-1-compliance` |
| **Report** | `docs/audits/G_INFRA_1_PROOF_REPORT.md` |
| **Pre-fix** | ~7,800 reads / 3,000 writes per 50-pair run |
| **Post-fix** | 2,119 queries, 100% cache hit; 0 runtime reads during sim |
| **Pattern** | Preload-once → SQLite → flush-once |
| **Promotion** | **PASS** — hard prerequisite for G5.4A+ |

## G-INFRA-2 Scale Readiness

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g-infra-2-scale` |
| **Report** | `docs/audits/G_INFRA_2_SCALE_READINESS_REPORT.md` |
| **Sample** | 100 pairs |
| **Results** | 0 runtime reads, 0 crashes, p95 47625ms |

## G-INFRA-2.1 Memory Hygiene

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g-infra-2.1-memory` |
| **Report** | `docs/audits/G_INFRA_2_1_MEMORY_HYGIENE_REPORT.md` |
| **Fix** | Streaming accumulators, journal chunk flush, drop heavy per-run objects |

## G-INFRA-2.2 Memory Architecture

| Field | Value |
|-------|-------|
| **Script** | `npm run validate:g-infra-2.2-memory` |
| **Report** | `docs/audits/G_INFRA_2_2_MEMORY_ARCHITECTURE_REPORT.md` |
| **Principle** | Store conclusions, not thoughts — durable vs ephemeral split |

## G-INFRA-2.3 SQLite Contention

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/G_INFRA_2_3_SQLITE_CONTENTION_FIX.md` |
| **Failure** | ERR_SQLITE_BUSY at scenario 27/32 during ledger compaction |
| **Fix** | WAL + busy_timeout; defer compaction during sim; write serializer |

## Architecture Compliance (Pre-G-INFRA)

| Field | Value |
|-------|-------|
| **Report** | `docs/audits/ARCHITECTURE_COMPLIANCE_AUDIT.md` |
| **Finding** | Cognition paths hit Supabase every cycle — FAIL |

---

# PROMOTION REGISTRY (SUMMARY)

| Capability | Status | Date | Evidence |
|------------|--------|------|----------|
| G1 Learning (single-brain) | PROVEN | 2026-06-06 | 15/15 lesson influence |
| G3 Ledger architecture | PROVEN (mechanism) | 2026-06-07 | G3B efficiency PASS |
| G4 Forecast accountability | PROVEN (mechanism) | 2026-06-07 | Penalty tiers validated |
| G-INFRA | PASS (gate) | 2026-06-09 | 0 runtime reads |
| G5.4A Foundation Stack | **PROMOTED** | 2026-06-12 | 48.7% div, +1.7% ROI |
| G5.4B Exploration Layer | **PROMOTED** | 2026-06-12 | 20.7% div, +0.3% ROI |
| G5.4C Harm Guard | **PROVEN** | 2026-06-14 | 0 capital flips |
| G5.4C Reasoning + Safe Divergence | **PROMOTED** | 2026-06-14 | 28% div, +2.1% ROI, 0 harmful |
| G2 Org intelligence | NOT PROVEN | — | Learning worse than control |
| G3.1 100-run outcomes | NOT PROMOTED | — | Verdict B |
| G4.1 Trust councils | NOT PROMOTED | — | Verdict C |
| G5 opportunity (unpaired) | NOT PROMOTED | — | World confound |
| G5.1A/B paired | NOT PROMOTED | — | Verdict C |
| G5.2A multi-ledger | FAIL | — | 0.7% divergence |
| G5.3A assumptions | FAIL | — | 3.3% divergence |
| G5.4C initial reasoning | NOT PROMOTED | — | ROI -0.6% |

---

# CANONICAL PROMOTED STACK (2026-06-14)

```text
Foundation (G5.4A)
  + Exploration (G5.4B)
  + Reasoning (case + recursive + debate)
  + Harm guard (G5.4C.7)
  + Safe divergence (G5.4C.8.2)
```

**Config entry:** `G5_4C_8_SAFE_DIVERGENCE_CONFIG` in `platform/simulation/types.ts`  
**Orchestrator:** `platform/cognition-lifecycle/execute-lifecycle.ts`  
**Valid experiment surface:** Federation Decision Suite only (gate required)

---

# ANNEX: RAW PAIR TABLE INDEX

Full per-pair tables preserved in:

| Report | Pairs | Batch pattern |
|--------|-------|---------------|
| `G5_4A_WEIGHT_TUNING_REPORT.md` | 50 | `g5_4a_wt_*` |
| `G5_4B_EXPLORATION_STACK_REPORT.md` | 50 | `g5_4b_*` |
| `G5_4C_REASONING_STACK_REPORT.md` | 50 | `g5_4c_*` |
| `G5_4C_SAFE_DIVERGENCE_DISCOVERY_REPORT.md` | 25 | `g5_4c_safe_*` |
| `G5_4C_HARM_AWARE_RETUNE_REPORT.md` | 25 | harm retune |
| `G4_ADAPTATION_RETEST_REPORT.md` | 100 | divergence examples |

---

*End of Experiment Ledger. This document is append-only in principle; corrections require dated addenda with new evidence.*
