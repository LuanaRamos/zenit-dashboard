# Meta Metrics Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Zenit Dashboard in which organic, account-total, and paid Meta metrics remain traceable and cannot be silently mixed.

**Architecture:** Execute three dependency-ordered plans. Foundation defines shared contracts and the Instagram v26 reports; Paid Ads then consumes the same contracts; integration replaces legacy loaders/UI, adds CI, and performs live reconciliation.

**Tech Stack:** Python 3.11, Pydantic v2, requests, Streamlit, pytest, Ruff, GitHub Actions.

**Spec:** [`docs/superpowers/specs/2026-08-30-meta-metric-contract-design.md`](../specs/2026-08-30-meta-metric-contract-design.md)

## Global Constraints

- Graph and Marketing API calls are pinned per client instance; production target is `v26.0`.
- Organic means only documented organic Media Insights fields: `comments`, `likes`, `views`, and `total_interactions`.
- Instagram Account Insights is always `account_total_including_ads`.
- Paid Instagram comparisons accept only `publisher_platform=instagram`.
- Unique metrics are never summed across chunks, media, ads, or breakdown rows.
- `None` means unavailable; `0` is valid only with a successful or valid-empty response.
- Every report carries source, scope, requested/effective period, status, retrieval time, timezone, currency when applicable, and structured issues.
- TLS verification remains enabled and secrets never enter fixtures, logs, exceptions, or artifacts.
- Production code is written only after its regression test fails for the expected reason.
- The PR remains draft and `main` remains unchanged until automated and live reconciliation gates pass.

---

## Plan order

1. [Foundation and Instagram v26](2026-08-30-meta-metrics-foundation-instagram.md)
2. [Paid Ads semantics](2026-08-30-meta-metrics-paid-ads.md)
3. [Dashboard integration, CI, and reconciliation](2026-08-30-meta-metrics-dashboard-integration.md)

Foundation Tasks 1–2 must complete first. After that, the remaining Instagram work and the Paid Ads domain work may run in isolated worktrees. Integration starts only after Foundation Task 8 and Paid Ads Task 7 expose their final report interfaces; the cross-plan legacy-removal scan remains in Integration Task 8.

## Final merge gate

- [ ] All non-live tests pass.
- [ ] Pinned Ruff reports no diagnostics in any added, copied, modified, renamed, or type-changed Python file.
- [ ] Compileall exits zero without changing the worktree.
- [ ] Private v26 live reconciliation reports no unexplained mismatch for the exact candidate SHA, without publishing raw IDs, values, payloads, or credentials.
- [ ] Paid totals reconcile with the matching Ads Manager scope, timezone, period, and ad-set attribution context.
- [ ] No forbidden labels remain: “Alcance orgânico” for Account Insights, synthetic “orgânico + pago” unique totals, “WhatsApp” without a confirmed destination, or “100% de precisão real”.
- [ ] PR #2 is marked ready only after the evidence is attached.
- [ ] PR #2 is merged into `main` without force.
