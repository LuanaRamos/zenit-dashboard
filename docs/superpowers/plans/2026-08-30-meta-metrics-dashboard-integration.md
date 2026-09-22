# Meta Metrics Dashboard Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the completed Instagram foundation and Paid Ads contracts into one auditable dashboard, reconcile it privately against controlled Meta data, remove legacy mixed flows, and merge only the exact verified PR head.

**Architecture:** This plan starts after Foundation Task 8 and Paid Task 7. It consumes `schemas.metrics`, `schemas.instagram`, `schemas.meta`, and `api.meta_ads_parser` literally; it does not recreate those contracts or introduce replacement transport/parser layers. A single snapshot carries each source report independently, including the separate paid-demographics reports introduced by Paid Task 6; presenters produce explicit view models, and Streamlit renders organic media, account totals, Instagram paid, and all-Meta paid without cross-scope arithmetic.

**Tech Stack:** Python 3.11, Pydantic v2 contracts from the completed foundation/paid plans, Streamlit, pandas, Plotly, requests, pytest, Ruff `0.12.11`, GitHub Actions, Meta Graph API/Marketing API v26.0 with a private v25.0 comparison probe.

**Spec:** [`docs/superpowers/specs/2026-08-30-meta-metric-contract-design.md`](../specs/2026-08-30-meta-metric-contract-design.md)

## Required Starting State

- Foundation Task 8 is committed and green. `schemas.metrics` and `schemas.instagram` are the only sources of shared/Instagram contract types.
- Paid Task 7 is committed and green. `schemas.meta` is the only source of Ads contract types and `api.meta_ads_parser` is the only paid parser module.
- The completed clients expose report-producing methods; integration calls them but never reclassifies their payloads.
- If either prerequisite is missing, stop before Task 1 and finish its existing plan. Do not recreate the missing type here.
- PR #2 remains draft until the two live gates in Tasks 7 and 9 pass.

## Global Constraints

- Media organic, media insights, account totals including ads, paid Instagram, and paid all-Meta remain separate through schema, snapshot, presenter, and UI.
- `None` renders `N/D`. A partial subtotal is allowed only with `Subtotal parcial (N de M itens)`; it is never presented as complete.
- Unique reach is never summed. Per-item reach may be summed only as `Soma de alcances por item — não deduplicada`, subject to the partial-subtotal rule.
- Paid mapping is described only as an `ID de mídia recuperável`. It does not prove that media is published, and an unmapped item is not automatically a dark post.
- Instagram comparison consumes a `PaidAdsReport` with `platform_scope="instagram"`; the Ads module consumes a separate report with `platform_scope="all_meta"`.
- Paid demographics consumes two separate `PaidDemographicsReport` instances: one with `platform_scope="instagram"` and one with `platform_scope="all_meta"`. It is never read from `PaidAdsReport`.
- UI must not restore `verify=False`, one-page pagination, root-click overwrites, generic CPA, aggregate-plus-subtype leads, or an unconfirmed WhatsApp label.
- Raw payloads, account/ad/media IDs, values, client configuration, tokens, and Authorization headers are never uploaded, committed, printed, or added to Actions artifacts.
- Legacy adapters stay until the first live gate passes. They are removed in Task 8, followed by the second live gate on the new commit.
- Normal CI is secret-free. Live reconciliation needs an explicitly authorized protected environment or authorized local execution.

## Consumed Contracts

Do not copy these into integration modules:

- `schemas.metrics`: `DatasetMeta`, `DatasetStatus`, `MetricIssue`, `MetricScope`, `PeriodBasis`, `PeriodWindow`, `ScopedMetricGroup`.
- `schemas.instagram`: completed Media, Account, Story, demographics, and comments report types from Foundation Task 8.
- `schemas.meta`: `PaidAdsReport`, `PaidDemographicsReport`, `PaidCampaign`, `PaidCreative`, `PaidMediaSummary`, paid metric/action types, and any creative-audience type actually exposed by Paid Task 7.
- `api.meta_ads_parser`: all paid parsing/action indexing. Integration never parses raw Ads action dictionaries.

---

### Task 1: Integrate canonical paid demographics and optional creative audience

**Files:**
- Create: `src/dashboard/ui/paid_capabilities.py`
- Create: `tests/unit/ui/test_paid_capabilities.py`

**Produces:**

```python
@dataclass(frozen=True)
class PaidCapabilities:
    creative_audience: bool

def detect_paid_capabilities(creative: PaidCreative) -> PaidCapabilities: ...
def paid_demographic_groups(
    report: PaidDemographicsReport,
) -> tuple[PaidDemographicGroup, ...]: ...
def paid_creative_audience(creative: PaidCreative) -> object | None: ...
```

- [ ] **RED: test canonical demographics and inventory only creative audience**

```bash
python - <<'PY'
from schemas.meta import PaidDemographicsReport, PaidCreative
print(sorted(PaidDemographicsReport.model_fields))
print(sorted(PaidCreative.model_fields))
PY
```

Assert `PaidDemographicsReport` has canonical `groups`, `paid_demographic_groups(report)` returns `report.groups` unchanged, and group metadata/status/issues remain intact for both platform scopes. Demographics is mandatory at the contract level; an unavailable API result is represented by report/group status and `N/D`, not by capability detection.

Keep exactly two deterministic branches for creative audience. If `PaidCreative` exposes its canonical audience field, capability is true and the accessor returns it unchanged. If absent, capability is false, the accessor returns `None`, and UI shows `N/D — audiência do criativo não exposta pelo contrato pago atual`. Assert no legacy `_fetch_ads_real_audience`, `get_demographics_insights`, or `get_creative_real_audience` call, no raw-dict parsing, and no candidate-field-name guessing.

- [ ] **RED verify**

```bash
python -m pytest tests/unit/ui/test_paid_capabilities.py -q
```

Expected: FAIL because `ui.paid_capabilities` does not exist.

- [ ] **GREEN: implement access only to fields exposed by the completed contract**

Return `report.groups` directly for demographics. Use only `PaidCreative.model_fields` to detect the one inventoried creative-audience field; when present, access exactly it, otherwise return `None`. Do not modify `schemas.meta`.

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/unit/ui/test_paid_capabilities.py tests/unit/schemas -q
rg -n '_fetch_ads_real_audience|get_demographics_insights|get_creative_real_audience|actions.*get\(' src/dashboard/ui/paid_capabilities.py
```

Expected: tests PASS and no search matches.

- [ ] **Commit**

```bash
git add src/dashboard/ui/paid_capabilities.py tests/unit/ui/test_paid_capabilities.py
git commit -m "refactor: align paid UI capabilities with report contracts"
```

### Task 2: Build one source-preserving dashboard snapshot

**Files:**
- Create: `src/dashboard/schemas/dashboard.py`
- Create: `src/dashboard/ui/dataset_context.py`
- Modify: `src/dashboard/ui/data_loader.py`
- Create: `tests/fixtures/integration/dashboard_reports.py`
- Create: `tests/integration/test_dashboard_snapshot.py`
- Create: `tests/unit/ui/test_dataset_context.py`

**Consumes:** completed media, account, Story, Instagram demographics, comments, `PaidAdsReport`, and `PaidDemographicsReport` types.

**Produces:**

```python
class DashboardPeriodRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: Literal["last_30d", "maximum", "custom"]
    publication_since: date | None
    publication_until: date | None
    measurement_since: date
    measurement_until: date
    ads_date_preset: str
    ads_time_range: dict[str, str] | None


class MediaComparison(BaseModel):
    model_config = ConfigDict(frozen=True)
    identity: MediaIdentity
    organic: ScopedMetricGroup[OrganicMediaMetrics]
    media_insights: ScopedMetricGroup[MediaInsightMetrics]
    visible_counters: ScopedMetricGroup[VisibleMediaCounters]
    paid: PaidMediaSummary | None = None


class DashboardSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    media: InstagramMediaReport
    account: InstagramAccountReport
    story: InstagramStoryReport
    demographics: InstagramDemographicsReport
    comments: InstagramCommentReport
    paid_instagram: PaidAdsReport
    paid_all_meta: PaidAdsReport
    paid_demographics_instagram: PaidDemographicsReport
    paid_demographics_all_meta: PaidDemographicsReport
    media_comparisons: tuple[MediaComparison, ...]
    period_request: DashboardPeriodRequest
    collected_at: AwareDatetime

@dataclass(frozen=True)
class DatasetContextVM:
    source: str
    scope: str
    platform: str
    status: str
    requested_period: str
    effective_period: str
    period_basis: str
    retrieved_at: str
    timezone: str
    currency: str
    warnings: tuple[str, ...]

def build_dataset_context(
    meta: DatasetMeta,
    group: ScopedMetricGroup[Any] | PaidDemographicGroup | None = None,
) -> DatasetContextVM: ...

def resolve_dashboard_period(
    date_preset: str,
    time_range: dict[str, str] | None,
    *,
    today: date,
) -> DashboardPeriodRequest: ...

def build_media_comparisons(
    media: InstagramMediaReport,
    paid_instagram: PaidAdsReport,
) -> tuple[MediaComparison, ...]: ...

def load_dashboard_snapshot(
    *,
    instagram_client: InstagramClient,
    ads_client: MetaAdsClient,
    request: DashboardPeriodRequest,
    clock: Callable[[], datetime],
) -> DashboardSnapshot: ...

@st.cache_data(ttl=900)
def fetch_dashboard_snapshot_cached(
    date_preset: str,
    time_range: dict[str, str] | None,
    client_name: str,
) -> DashboardSnapshot: ...
```

Use the literal Foundation Task 8 class names for demographics/comments. If their final names differ from those annotations, change only imports/annotations to the exact names; do not define aliases or replacement contracts.

- [ ] **RED: create report fakes and orchestration/context tests**

`dashboard_reports.py` builds immutable sanitized reports with one complete and one partial media item, partial Account group, active Story, independent Instagram-demographics/comments metadata, paid Instagram with one recoverable and one unrecoverable media ID, paid all-Meta containing Instagram/Facebook delivery, paid-demographics Instagram groups, and distinct paid-demographics all-Meta groups.

Assert inclusive last-30-day and exact custom periods. For `maximum`, assert the request delegates source-specific effective windows to report metadata instead of claiming a global window. Recording fakes must show one fetch each for media, account, Story, Instagram demographics, comments, paid Instagram, paid all-Meta, paid-demographics Instagram, and paid-demographics all-Meta. Ads-report calls must be:

```python
assert paid_ads_calls == [
    {"date_preset": request.ads_date_preset, "time_range": request.ads_time_range, "platform_scope": "instagram"},
    {"date_preset": request.ads_date_preset, "time_range": request.ads_time_range, "platform_scope": "all_meta"},
]

assert paid_demographics_calls == [
    {"date_preset": request.ads_date_preset, "time_range": request.ads_time_range, "platform_scope": "instagram"},
    {"date_preset": request.ads_date_preset, "time_range": request.ads_time_range, "platform_scope": "all_meta"},
]
```

Assert reports are not mutated/copied into one another. `build_media_comparisons()` joins exclusively on `item.identity.id` against `paid_instagram.by_instagram_media_id`, leaves an unmatched publication with `paid=None`, and does not remove paid IDs absent from the publication selection: those remain in `PaidAdsReport`. For `build_dataset_context(meta, group)`, group `partial` overrides dataset `ok`, warnings merge once, and only `can_display=True` issues appear. A `ScopedMetricGroup` supplies its own metric scope; a `PaidDemographicGroup` keeps `meta.metric_scope` and supplies its own `platform_scope`.

- [ ] **RED verify**

```bash
python -m pytest tests/integration/test_dashboard_snapshot.py tests/unit/ui/test_dataset_context.py -q
```

Expected: FAIL on missing snapshot/context modules.

- [ ] **GREEN: orchestrate without cross-source joins or fallbacks**

Call the completed Foundation methods in this order so comments use the exact selected media identities:

```python
media = instagram_client.get_media_report(
    publication_since=request.publication_since,
    publication_until=request.publication_until,
    limit=100,
)
account = instagram_client.get_account_report(
    requested_since=request.measurement_since,
    requested_until=request.measurement_until,
)
story = instagram_client.get_active_story_report()
demographics = instagram_client.get_demographics_report()
comments = instagram_client.get_media_comments(
    tuple(item.identity.id for item in media.items)
)
```

Call `MetaAdsClient.get_paid_ads_report()` twice and `MetaAdsClient.get_paid_demographics_report()` twice with the respective `instagram` and `all_meta` scopes. Keep all nine reports independent. Do not use `model_copy(update=...)`, sum reach, reconstruct mapping from publications, read demographics from `PaidAdsReport`, or swallow report issues.

After all source reports exist, call `build_media_comparisons(media, paid_instagram)`. This is the only cross-source join and copies no paid field into an Instagram media item.

Mapping labels are exactly:

- `Investimento com ID de mídia recuperável`
- `Investimento sem ID de mídia recuperável`
- `Cobertura de IDs recuperáveis`

Never use `associado a mídia publicada`, `dark posts cobertos`, or `mídia orgânica encontrada`.

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/integration/test_dashboard_snapshot.py tests/unit/ui/test_dataset_context.py tests/unit/schemas -q
rg -n 'model_copy|associado a mídia publicada|dark posts cobertos' src/dashboard/schemas/dashboard.py src/dashboard/ui/data_loader.py src/dashboard/ui/dataset_context.py
```

Expected: tests PASS and no search matches.

- [ ] **Commit**

```bash
git add src/dashboard/schemas/dashboard.py src/dashboard/ui/dataset_context.py src/dashboard/ui/data_loader.py tests/fixtures/integration/dashboard_reports.py tests/integration/test_dashboard_snapshot.py tests/unit/ui/test_dataset_context.py
git commit -m "refactor: orchestrate source-preserving dashboard reports"
```

### Task 3: Build explicit view models and migrate all Streamlit metric views

**Files:**
- Create: `src/dashboard/ui/dashboard_presenters.py`
- Modify: `src/dashboard/ui/components.py`
- Modify: `src/dashboard/ui/organic_components.py`
- Modify: `src/dashboard/ui/creatives_components.py`
- Modify: `src/dashboard/ui/demographics_components.py`
- Modify: `src/dashboard/ui/layouts.py`
- Modify: `src/dashboard/app.py`
- Create: `tests/unit/ui/test_dashboard_presenters.py`
- Create: `tests/integration/apps/dashboard_app.py`
- Create: `tests/integration/test_streamlit_dashboard.py`

**Produces:**

```python
@dataclass(frozen=True)
class SubtotalVM:
    value: int | float | None
    formatted_value: str
    completeness: Literal["complete", "partial", "unavailable"]
    contributing_items: int
    expected_items: int
    label_suffix: str

@dataclass(frozen=True)
class MetricCardVM:
    label: str
    value: str
    caption: str
    help_text: str
    status: Literal["ok", "partial", "unavailable", "empty"]

@dataclass(frozen=True)
class TableVM:
    title: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, object], ...]
    currency_code: str | None
    empty_message: str

@dataclass(frozen=True)
class SectionVM:
    title: str
    context: DatasetContextVM
    cards: tuple[MetricCardVM, ...]
    tables: tuple[TableVM, ...]
    notices: tuple[str, ...]

@dataclass(frozen=True)
class DashboardVM:
    organic_media: SectionVM
    media_insights: SectionVM
    account_total: SectionVM
    paid_instagram: SectionVM
    paid_all_meta: SectionVM
    media_comparison: SectionVM
    stories: SectionVM
    instagram_demographics: SectionVM
    paid_demographics_instagram: SectionVM
    paid_demographics_all_meta: SectionVM
    comments: SectionVM
    creatives: SectionVM

def build_subtotal(
    values: Sequence[int | float | None],
    statuses: Sequence[DatasetStatus],
) -> SubtotalVM: ...

def build_dashboard_view(snapshot: DashboardSnapshot) -> DashboardVM: ...
def render_dashboard(view: DashboardVM) -> None: ...
```

Subtotal rules:

- no available values → `N/D`, `unavailable`;
- every expected value present and every status `ok`/`empty` → complete subtotal;
- at least one value plus any missing/partial/unavailable item → partial subtotal with `Subtotal parcial (N de M itens)`;
- zero remains `0` under `ok`/`empty`;
- unique reach never uses `build_subtotal`; only the explicitly non-deduplicated per-item reach row may use it.

- [ ] **RED: test view-model semantics and UI copy**

Assert exact section titles:

- `Conteúdo orgânico — Media Insights`
- `Métricas da mídia — escopo documentado`
- `Total da conta — inclui anúncios/impulsionados`
- `Pago — Ads Insights (Instagram)`
- `Pago — Ads Insights (todas as plataformas Meta)`

Assert `None → N/D`, `0 → 0`, all subtotal states, dynamic BRL/USD formatting, organic-only fields in organic cards, no Account `orgânico` label, and strict separation of the two paid reports.

Mapping notice is exactly:

`Um ID recuperável permite relacionar a entrega paga ao identificador retornado pela Meta; ele não comprova que a mídia esteja publicada. Um item sem ID recuperável também não é, por si só, um dark post.`

Paid demographics must be built canonically from `snapshot.paid_demographics_instagram.groups` and `snapshot.paid_demographics_all_meta.groups`, with separate dataset contexts and platform labels. If either report/group is unavailable, render `N/D` from its status rather than hiding the section or querying a fallback. Only creative audience remains optional: if Task 1 reports it absent, UI says `N/D — audiência do criativo não exposta pelo contrato pago atual` and makes no fallback request.

Use `AppTest.from_file("tests/integration/apps/dashboard_app.py")`. Assert source, effective period, retrieval time, platform, timezone, currency, and partial warnings are visible. Assert these strings are absent:

```text
100% de precisão real
Orgânico + pago
Alcance Total
Cliques no Criativo
CPA médio
WhatsApp iniciados
Dark Posts / Impulsionados
associado a mídia publicada
```

- [ ] **RED verify**

```bash
python -m pytest tests/unit/ui/test_dashboard_presenters.py tests/integration/test_streamlit_dashboard.py -q
```

Expected: FAIL on missing presenter/render entry point.

- [ ] **GREEN: implement presenters first and render only view models**

`render_metric_card` accepts preformatted value/status. `render_glass_table` displays `N/D` and formats currency only with a currency code. Replace Instagram's multiple fetches and Ads' separate overview/creative/demographic fetches with one snapshot/view. Never source paid demographic rows from `PaidAdsReport`.

Render Instagram in three primary blocks: organic media, account total, paid Instagram. Render media insight, Story, Instagram demographics, comments, `snapshot.media_comparisons`, and paid-demographics Instagram as subordinate blocks with their own contexts. The comparison table may show paid data only when the immutable ID join found it; it never removes paid IDs outside the selected publication window from the paid report. Render general Ads/campaigns/creatives from `paid_all_meta` and its audience delivery only from `paid_demographics_all_meta`.

Use `Cliques — todos`, `Cliques no link`, `Cliques de saída`, and `Conversas por mensagem`. Use `Conversas no WhatsApp` only with confirmed destination. Every cost names its denominator. Rename the history option to `Maior histórico disponível por fonte` and explain publication snapshot versus ad delivery windows.

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/unit/ui tests/integration/test_dashboard_snapshot.py tests/integration/test_streamlit_dashboard.py -q
rg -n '100% de precisão real|Orgânico \+ pago|Cliques no Criativo|CPA médio|WhatsApp iniciados|Dark Posts / Impulsionados|associado a mídia publicada' src/dashboard/app.py src/dashboard/ui
```

Expected: tests PASS and no visible-copy matches.

- [ ] **Commit**

```bash
git add src/dashboard/ui/dashboard_presenters.py src/dashboard/ui/components.py src/dashboard/ui/organic_components.py src/dashboard/ui/creatives_components.py src/dashboard/ui/demographics_components.py src/dashboard/ui/layouts.py src/dashboard/app.py tests/unit/ui/test_dashboard_presenters.py tests/integration/apps/dashboard_app.py tests/integration/test_streamlit_dashboard.py
git commit -m "feat: render audited Meta datasets without mixed totals"
```

### Task 4: Secure or remove side flows and sanitize Sentry

**Files:**
- Create: `src/dashboard/observability.py`
- Modify: `src/dashboard/app.py`
- Modify: `src/dashboard/api/instagram_client.py`
- Modify: `src/dashboard/api/meta_client.py`
- Modify: `src/dashboard/ui/catalog_components.py`
- Modify: `src/dashboard/ui/data_loader.py`
- Create: `tests/unit/test_observability.py`
- Create: `tests/integration/test_side_flow_safety.py`

**Scope:** catalog, comments/media-ID pagination, lead-form pagination, and the current `organic_leads` UI flow.

**Produces:**

```python
SENSITIVE_KEYS = frozenset({
    "access_token", "token", "authorization", "client_secret",
    "app_secret", "meta_master_token", "clients_json",
})

def redact_sensitive(value: object) -> object: ...
def sanitize_sentry_event(event: dict, hint: dict | None) -> dict | None: ...
```

- [ ] **RED: test side-flow TLS, pagination, contracts, and sanitization**

With fake pages, assert catalog/comments use the safe request path already delivered by Foundation/Paid, never pass `verify=False`, follow cursors fully, stop a repeated cursor, and expose partial status rather than silently truncating.

If the literal Paid Task 7 contract includes lead-form delivery, assert all pages are represented under that named paid action. Because current `organic_leads` is outside the approved organic contract, assert `fetch_organic_leads_cached` and combined `Pagos | Orgânicos` lead card are absent.

Test recursive, case-insensitive Sentry redaction. Remove Authorization, client JSON, tokens, raw Meta payloads, and sensitive breadcrumbs while preserving safe exception type/message, issue code/subcode, and `fbtrace_id`.

- [ ] **RED verify**

```bash
python -m pytest tests/unit/test_observability.py tests/integration/test_side_flow_safety.py -q
```

Expected: FAIL on missing sanitizer, unsafe/truncated side flow, or uncontracted organic leads.

- [ ] **GREEN: migrate contracted flows and remove uncontracted lead totals**

Reuse client safety/pagination delivered by Foundation/Paid; do not create `graph_transport.py`, `meta_parsers.py`, or another paid parser. Move catalog/comments behind completed safe client methods. Show lead forms only if represented in `schemas.meta`; otherwise remove request, loader, and UI.

Wire `sanitize_sentry_event` to `before_send`. Remove raw `st.exception(e)` for Meta failures; render structured safe issues and send only sanitized events.

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/unit/test_observability.py tests/integration/test_side_flow_safety.py tests/integration/test_streamlit_dashboard.py -q
rg -n 'verify\s*=\s*False|fetch_organic_leads_cached|Pagos \|.*Orgânicos|st\.exception\(' src/dashboard
```

Expected: tests PASS and no matches.

- [ ] **Commit**

```bash
git add src/dashboard/observability.py src/dashboard/app.py src/dashboard/api/instagram_client.py src/dashboard/api/meta_client.py src/dashboard/ui/catalog_components.py src/dashboard/ui/data_loader.py tests/unit/test_observability.py tests/integration/test_side_flow_safety.py
git commit -m "fix: secure auxiliary Meta flows and telemetry"
```

### Task 5: Enforce pinned full-file Ruff for ACMRT Python files and deterministic CI

**Files:**
- Modify: `requirements.txt`
- Create: `scripts/ruff_acmrt.py`
- Create: `tests/unit/test_ruff_acmrt.py`
- Modify: `.github/workflows/main.yml`
- Create: `tests/integration/test_ci_workflow.py`

**Produces:**

```python
def changed_python_files(base_sha: str, head_sha: str) -> tuple[str, ...]: ...
def run_ruff(paths: tuple[str, ...]) -> int: ...
```

CLI: `python scripts/ruff_acmrt.py --base BASE_SHA --head HEAD_SHA`. It runs full-file Ruff on existing Python files with git status Added, Copied, Modified, Renamed, or Type-changed. It never filters diagnostics by line.

- [ ] **RED: test ACMRT selection, full-file failure, and CI identity/cleanliness**

Assert `git diff --name-only --diff-filter=ACMRT` selects rename destinations, excludes deletions, preserves spaces, and invokes Ruff once with all existing `.py` paths. A diagnostic on an unchanged line in a modified file must fail.

Workflow tests require checkout `fetch-depth: 0`, exact PR/push head checkout, base/head environment SHAs validated by `^[0-9a-f]{40}$` and `git cat-file`, all-zero/missing push-base fallback to root, `ruff==0.12.11` installed only from requirements, non-live pytest, external bytecode cache, clean tree before/after, no live secret names, and no artifact upload.

- [ ] **RED verify**

```bash
python -m pytest tests/unit/test_ruff_acmrt.py tests/integration/test_ci_workflow.py -q
```

Expected: FAIL against current CI/missing script.

- [ ] **GREEN: implement pinned full-file ACMRT lint and clean-tree CI**

Replace unpinned `ruff` with exactly `ruff==0.12.11`. CI sets:

```yaml
env:
  CI_BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}
  CI_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}
```

Validate/fetch SHAs, then run:

```bash
test -z "$(git status --porcelain)"
python scripts/ruff_acmrt.py --base "$CI_BASE_SHA" --head "$CI_HEAD_SHA"
PYTHONPYCACHEPREFIX="$RUNNER_TEMP/zenit-pycache" python -m compileall -q src/dashboard
python -m pytest -m "not live" -q
test -z "$(git status --porcelain)"
```

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/unit/test_ruff_acmrt.py tests/integration/test_ci_workflow.py -q
BASE_SHA=$(git merge-base origin/main HEAD)
python scripts/ruff_acmrt.py --base "$BASE_SHA" --head HEAD
PYTHONPYCACHEPREFIX=/tmp/zenit-ci-pycache python -m compileall -q src/dashboard
python -m pytest -m "not live" -q
test -z "$(git status --porcelain)"
```

Expected: all commands exit 0.

- [ ] **Commit**

```bash
git add requirements.txt scripts/ruff_acmrt.py tests/unit/test_ruff_acmrt.py .github/workflows/main.yml tests/integration/test_ci_workflow.py
git commit -m "ci: lint complete changed files and run contract tests"
```

### Task 6: Add private local v25/v26 reconciliation without publishing data

**Files:**
- Create: `src/dashboard/reconciliation.py`
- Create: `scripts/reconcile_meta_local.py`
- Modify: `.gitignore`
- Create: `tests/unit/test_reconciliation.py`
- Create: `tests/live/test_meta_reconciliation.py`

**Produces:**

```python
class SettledPeriod(BaseModel):
    since: date
    until: date

class BaselineContext(BaseModel):
    exported_at: AwareDatetime
    settled_period: SettledPeriod
    active_story_as_of: AwareDatetime
    currency: str
    timezone: str
    attribution_fingerprint: str


ControlledAssetKind = Literal[
    "unpromoted_media", "promoted_media", "image_media", "carousel_media",
    "reel_media", "legacy_video_media", "active_story", "one_ad_media",
    "multi_ad_media", "cross_platform_ad", "recoverable_paid_id",
    "unrecoverable_paid_id",
]


class ControlledAsset(BaseModel):
    model_config = ConfigDict(frozen=True)
    alias: str
    kind: ControlledAssetKind
    private_id: SecretStr


class ControlledAssets(BaseModel):
    model_config = ConfigDict(frozen=True)
    assets: tuple[ControlledAsset, ...]


class ExpectedMetric(BaseModel):
    model_config = ConfigDict(frozen=True)
    asset_alias: str | None = None
    dataset: Literal[
        "media_organic", "media_insights", "account", "story",
        "paid_delivery", "paid_demographics", "paid_media_identity",
    ]
    platform_scope: Literal["instagram", "all_meta"] | None = None
    metric_path: tuple[str, ...]
    expected: float
    absolute_tolerance: float = Field(ge=0)
    required_versions: tuple[Literal["v25.0", "v26.0"], ...]


class ReconciliationBaseline(BaseModel):
    context: BaselineContext
    controlled_assets: ControlledAssets
    expectations: tuple[ExpectedMetric, ...]

class ReconciliationSummary(BaseModel):
    candidate_sha: str
    baseline_sha256: str
    api_versions: tuple[str, ...]
    settled_period: SettledPeriod
    active_story_as_of: AwareDatetime
    required_checks: int
    passed_checks: int
    failed_checks: int
    status: Literal["passed", "failed"]

def canonical_baseline_hash(baseline_bytes: bytes) -> str: ...
def reconcile_private(
    snapshot_v25: DashboardSnapshot,
    snapshot_v26: DashboardSnapshot,
    baseline: ReconciliationBaseline,
    candidate_sha: str,
) -> ReconciliationSummary: ...
```

CLI:

```bash
python scripts/reconcile_meta_local.py \
  --baseline-env META_RECON_BASELINE_JSON \
  --candidate-sha CANDIDATE_SHA \
  --versions v25.0 v26.0
```

The CLI keeps payloads, IDs, and expected/actual values in memory. It prints only candidate SHA, full baseline SHA-256, period/as-of context, counts, and final status.

- [ ] **RED: test privacy, context separation, both paid scopes, and minimum gate**

Use fake v25/v26 clients and a baseline with one unique private alias for every `ControlledAssetKind`, plus paid-demographics expectations for both platform scopes. Validate alias uniqueness, require every kind, ensure each `ExpectedMetric.asset_alias` resolves when present, require `platform_scope` for every paid dataset, and reject a negative tolerance or an empty `required_versions` tuple.

Assert settled period ends at least two complete days earlier; `active_story_as_of` remains separate; each version requests `get_paid_ads_report()` for Instagram/all-Meta and `get_paid_demographics_report()` for Instagram/all-Meta; currency/timezone/attribution fingerprint matches; hash uses exact baseline bytes; v26 minimum gate covers media organic, account, Story-as-of, both paid delivery scopes, both paid-demographics report scopes, mapping, click separation, and named actions; v25 covers overlap without weakening v26.

Assert serialized summary/stdout/exceptions/logs contain no IDs, values, payloads, tokens, or client JSON. Invalid/private leak exits 2, mismatch exits 1, pass exits 0. Mark credentialed test `@pytest.mark.live`.

- [ ] **RED verify**

```bash
python -m pytest tests/unit/test_reconciliation.py -q
```

Expected: FAIL on missing private reconciler.

- [ ] **GREEN: implement in-memory reconciliation and summary-only output**

Ignore `.reconciliation-private/`. Do not write raw responses, snapshots, view models, manifests, IDs, or values. Read baseline JSON directly from the named environment variable and use separate v25/v26 clients. The only optional local file is `.reconciliation-private/summary.json`, mode `0600`, containing only `ReconciliationSummary`. Never add artifact-upload commands.

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/unit/test_reconciliation.py -q
python -m pytest -m "not live" -q
rg -n 'controlled_assets|expectations|expected_value|actual_value|upload-artifact' .reconciliation-private 2>/dev/null && exit 1 || true
git check-ignore .reconciliation-private/summary.json
```

Expected: tests PASS, no private field match, private path ignored.

- [ ] **Commit**

```bash
git add src/dashboard/reconciliation.py scripts/reconcile_meta_local.py .gitignore tests/unit/test_reconciliation.py tests/live/test_meta_reconciliation.py
git commit -m "test: add private Meta v25 v26 reconciliation"
```

### Task 7: Bootstrap and execute the first authorized live gate

**Files:**
- Create: `.github/workflows/meta-live-reconciliation.yml`
- Create: `tests/integration/test_live_workflow.py`

**Workflow interface:**

```yaml
on:
  workflow_dispatch:
    inputs:
      candidate_sha:
        required: true
        type: string
run-name: Meta private reconciliation ${{ inputs.candidate_sha }}
```

The workflow runs from `main`, validates 40-char lowercase hex SHA, checks out that exact commit, confirms `git rev-parse HEAD`, uses protected environment `meta-reconciliation`, invokes the private runner for paid delivery and paid demographics in both platform scopes, emits allowed summary only, and never uploads artifacts.

- [ ] **RED: test workflow secrecy and candidate binding**

Assert manual-only trigger, `contents: read`, protected environment, exact SHA validation/checkout, secret mapping without echo, both API versions, no `pull_request_target`, schedule, artifact upload, private cache, or raw output.

- [ ] **RED verify**

```bash
python -m pytest tests/integration/test_live_workflow.py -q
```

Expected: FAIL because workflow is missing.

- [ ] **GREEN: implement the protected workflow**

Keep PR #2 draft. Implement the workflow and its policy test without dispatching an uncommitted candidate.

- [ ] **GREEN verify**

```bash
python -m pytest tests/integration/test_live_workflow.py -q
python -m pytest -m "not live" -q
```

Expected: PASS.

- [ ] **Commit**

```bash
git add .github/workflows/meta-live-reconciliation.yml tests/integration/test_live_workflow.py
git commit -m "ci: add protected private Meta reconciliation gate"
```

- [ ] **REFACTOR: bootstrap, execute, and record the pre-removal gate safely**

After pushing the committed candidate, read `main:.github/workflows/meta-live-reconciliation.yml` via GitHub connector/API.

If present, dispatch for the committed PR head. If absent:

1. run the identical gate locally with explicitly authorized credentials;
2. keep PR #2 draft regardless of result;
3. create a separate branch from current `main` containing only this workflow;
4. review and merge that workflow-only bootstrap change;
5. re-read it from `main`, then dispatch for the same committed PR head.

The main-hosted workflow checks out the candidate SHA, so bootstrap contains no application code. Capture only candidate SHA, run ID/URL/conclusion, baseline SHA-256, passed/required counts, settled-period dates, and Story as-of. Do not copy logs/payloads/IDs/values into the repo or PR. Require `success` for that exact pre-removal SHA; keep PR draft.

### Task 8: Remove legacy metric adapters after the first live gate

**Files:**
- Modify: `src/dashboard/ui/data_loader.py`
- Modify: `src/dashboard/api/instagram_client.py`
- Modify: `src/dashboard/api/meta_client.py`
- Modify: `src/dashboard/schemas/instagram.py`
- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/ui/organic_components.py`
- Modify: `src/dashboard/ui/components.py`
- Modify: `src/dashboard/ui/creatives_components.py`
- Modify: `src/dashboard/ui/demographics_components.py`
- Create: `tests/integration/test_no_legacy_metric_adapters.py`

**Precondition:** Task 7 has a successful main-hosted run ID for the exact current PR SHA, including `PaidDemographicsReport` reconciliation in `instagram` and `all_meta` scopes. Otherwise stop.

- [ ] **RED: encode removal boundary**

Assert absent loaders: `fetch_campaigns_v8`, `load_page_data`, `fetch_instagram_ads_mapping_cached`, `fetch_instagram_paid_totals_cached`, `fetch_organic_v12`, `fetch_active_stories`, `fetch_account_insights_cached`, `fetch_followers_history_cached`, `fetch_organic_leads_cached`.

Assert absent patterns:

```text
model_copy(update=update_data)
paid_other_clicks
clicks = link_clicks + profile_visits
leads = site_leads + native_leads
verify=False
organic_reach =
Orgânico + pago
100% de precisão real
```

Delete legacy `CampaignInsight`, `CreativePerformance`, `InstagramMedia`, and `InstagramStory` only after zero runtime imports.

- [ ] **RED verify**

```bash
python -m pytest tests/integration/test_no_legacy_metric_adapters.py -q
```

Expected: FAIL while adapters remain.

- [ ] **GREEN: migrate remaining consumers and remove proven-unused code**

```bash
rg -n 'fetch_campaigns_v8|load_page_data|fetch_instagram_ads_mapping_cached|fetch_instagram_paid_totals_cached|fetch_organic_v12|fetch_active_stories|fetch_account_insights_cached|fetch_followers_history_cached|fetch_organic_leads_cached|CampaignInsight|CreativePerformance|InstagramMedia|InstagramStory' src/dashboard
```

Migrate legitimate matches to literal completed contracts, then remove adapters/obsolete fields. Retain auth and catalog/comments only if Task 4 made them TLS-safe, paginated, and status-aware.

- [ ] **GREEN/REFACTOR verify**

```bash
python -m pytest tests/integration/test_no_legacy_metric_adapters.py -q
BASE_SHA=$(git merge-base origin/main HEAD)
python scripts/ruff_acmrt.py --base "$BASE_SHA" --head HEAD
PYTHONPYCACHEPREFIX=/tmp/zenit-removal-pycache python -m compileall -q src/dashboard
python -m pytest -m "not live" -q
rg -n 'model_copy\(update=update_data\)|paid_other_clicks|clicks = link_clicks \+ profile_visits|leads = site_leads \+ native_leads|verify\s*=\s*False|Orgânico \+ pago|100% de precisão real' src/dashboard
```

Expected: tests/checks PASS and prohibited scan empty.

- [ ] **Commit**

```bash
git add src/dashboard tests/integration/test_no_legacy_metric_adapters.py
git commit -m "refactor: remove legacy mixed metric adapters"
```

### Task 9: Execute post-removal live gate and merge the exact verified head

**Files:**
- Verify/integrate only; no code/document changes.

**Required identities:**

- `LOCAL_SHA`: local Task 8 head.
- `REMOTE_HEAD_OID`: PR #2 `headRefOid` from GitHub connector/API.
- `CI_RUN_ID`: successful normal CI run with `headSha=REMOTE_HEAD_OID`.
- `LIVE_RUN_ID`: successful private run whose exact candidate input/title is `REMOTE_HEAD_OID`.

Do not assume `gh` exists. Use GitHub connector/API for PR state, dispatch/listing, checks, readiness, and merge.

- [ ] **RED gate: bind local and remote candidate**

```bash
LOCAL_SHA=$(git rev-parse HEAD)
test -z "$(git status --porcelain)"
```

Read PR #2 `headRefOid`. If different, push intended commit through authorized GitHub workflow, re-read OID, and restart. Never validate one SHA and merge another.

- [ ] **GREEN: full local gate on remote OID**

```bash
test "$(git rev-parse HEAD)" = "$REMOTE_HEAD_OID"
BASE_SHA=$(git merge-base origin/main HEAD)
python scripts/ruff_acmrt.py --base "$BASE_SHA" --head "$REMOTE_HEAD_OID"
PYTHONPYCACHEPREFIX=/tmp/zenit-final-pycache python -m compileall -q src/dashboard
python -m pytest -m "not live" -q
git diff --check origin/main...HEAD
test -z "$(git status --porcelain)"
```

Expected: all exit 0.

- [ ] **GREEN: execute second private live gate**

Dispatch main-hosted workflow via GitHub Actions connector/API with `candidate_sha=REMOTE_HEAD_OID`. Locate by workflow ID and exact run title; retain `run_id`; wait for completion.

Require success, exact candidate, v26 minimum gate for organic/account/Story-as-of, paid delivery Instagram/all-Meta, paid demographics Instagram/all-Meta, mapping/clicks/named actions, v25 overlap completion, unchanged baseline hash/context unless separately reviewed, and no published private data. On failure, leave PR draft and stop.

- [ ] **REFACTOR gate: bind normal CI and live run IDs to unchanged OID**

Fetch current `headRefOid`, normal checks for that exact SHA, and `LIVE_RUN_ID` with exact candidate. Require unchanged OID and success. Record only run IDs/URLs, SHA, hash, periods/as-of, counts, conclusions.

- [ ] **Mark ready and merge using GitHub connector/API**

Mark PR #2 ready now. Merge with expected head SHA `REMOTE_HEAD_OID` and method `merge`. If head changed, a check failed, protection blocks, or state is non-mergeable, re-read and restart gates; never retry blindly.

- [ ] **Post-merge verification**

```bash
git fetch origin main
git merge-base --is-ancestor "$REMOTE_HEAD_OID" origin/main
```

In a clean `origin/main` worktree:

```bash
PYTHONPYCACHEPREFIX=/tmp/zenit-main-pycache python -m compileall -q src/dashboard
python -m pytest -m "not live" -q
test -z "$(git status --porcelain)"
```

Expected: exact verified head is in main; compile/tests PASS; worktree clean.
