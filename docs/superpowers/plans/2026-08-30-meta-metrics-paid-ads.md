# Meta Paid Ads Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build auditable Meta Ads v26 reports that preserve raw action rows, distinguish paid metric semantics, expose platform and attribution scope, and never turn missing, partial, or non-deduplicated data into authoritative numbers.

**Architecture:** `MetaAdsClient` owns HTTP, pagination, and query groups. Pure functions in `api/meta_ads_parser.py` parse raw payloads into canonical Pydantic schemas in `schemas/meta.py`; shared status, issue, period, and provenance schemas come only from `schemas/metrics.py`. Account totals, campaign rows, ad rows, and Instagram-media identity coverage remain independent groups in `PaidAdsReport`; paid demographics remains a separate `PaidDemographicsReport` loaded with the same request context.

**Tech Stack:** Python 3.11, requests, Pydantic, pytest, Ruff, Meta Graph/Marketing API v26.

**Spec:** [`docs/superpowers/specs/2026-08-30-meta-metric-contract-design.md`](../specs/2026-08-30-meta-metric-contract-design.md)

## Global Constraints

- Execute the shared metric foundation plan first. Consume `MetricScope`, `DatasetStatus`, `PeriodBasis`, `IssueReason`, `IssueType`, `MetricIssue`, `PeriodWindow`, and `DatasetMeta` only from `src/dashboard/schemas/metrics.py`.
- `PeriodWindow` uses the four date fields `requested_since`, `requested_until`, `effective_since`, and `effective_until`, plus mandatory `basis=PeriodBasis.AD_DELIVERY_WINDOW`; do not create a competing resolved-period model.
- Canonical Ads schemas live only in `src/dashboard/schemas/meta.py`; canonical Ads parsing lives only in `src/dashboard/api/meta_ads_parser.py`.
- `MetricScope.PAID_ADS` and `PeriodBasis.AD_DELIVERY_WINDOW` apply to every report here.
- `platform_scope` is exactly `"all_meta"` or `"instagram"`. Content comparison accepts only `"instagram"`.
- Preserve one `RawAdsActionRow` for every line returned in `actions`, `action_values`, and `outbound_clicks`. Derived indices must not replace or mutate those rows.
- Preserve root `clicks`, root `inline_link_clicks`, and derived outbound-click count as distinct values.
- Use the auditable names `action_lead`, `action_leadgen`, and `action_pixel_lead`. Do not label them “site”, “instant form”, or a combined lead total until a live reconciliation proves those meanings for the account.
- A WhatsApp-specific count requires `action_destination=whatsapp`; otherwise expose only generic messaging conversations.
- Sum only enumerated additive values. Recalculate ratios from their named denominators. Reach comes only from a valid aggregate at the requested level.
- ROAS is `None` unless the caller supplies one exact `action_values.action_type` as its source.
- A successful literal `0` remains zero. A successful contractual empty group may produce zero additive metrics with `DatasetStatus.EMPTY`. Missing, unsupported, partial, or failed values remain `None` with issues.
- Account currency and timezone are authoritative. Without account timezone, presets are unavailable; an explicit custom date range may continue as partial with timezone `None`/“N/D”.
- Persist requested and actually returned attribution windows separately, along with every distinct `attribution_spec` candidate and any conflict issue.
- Do not send `action_report_time` or `use_unified_attribution_setting`. Request only `1d_click`, `7d_click`, `28d_click`, and `1d_view`.
- TLS verification is mandatory. Tokens, Authorization headers, raw response bodies, and unsanitized Meta messages never enter logs, exceptions, or fixtures.
- Do not refactor or reroute legacy pagination loops in this plan. New behavior is implemented only through `get_paid_ads_report()` and `get_paid_demographics_report()`; legacy removal happens after UI migration.
- No new runtime dependency is permitted.

---

### Task 1: Preserve raw Ads action rows and composite indices

**Dependencies:** Shared metric foundation and its `tests/conftest.py` fixtures `load_json` and `client_config`.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Create: `src/dashboard/api/meta_ads_parser.py`
- Create: `tests/unit/api/test_meta_ads_raw_actions.py`
- Create: `tests/fixtures/meta_ads/raw_actions.json`

**Interfaces:**

```python
class AdsActionDimension(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    value: str


class AdsAttributionValue(BaseModel):
    model_config = ConfigDict(frozen=True)
    window: str
    value: float


class RawAdsActionRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    action_type: str
    value: float | None = None
    attribution_values: tuple[AdsAttributionValue, ...] = ()
    dimensions: tuple[AdsActionDimension, ...] = ()
```

```python
AdsActionIndexKey = tuple[
    str,
    str | None,
    tuple[tuple[str, str], ...],
]
AdsActionIndex = dict[AdsActionIndexKey, tuple[float, ...]]


def parse_raw_ads_action_rows(
    rows: list[dict[str, Any]] | None,
) -> tuple[RawAdsActionRow, ...]: ...


def index_raw_ads_actions(
    rows: Sequence[RawAdsActionRow],
) -> AdsActionIndex: ...
```

- [ ] **RED — Add one-line-per-row fixture and failing tests**

Create `tests/fixtures/meta_ads/raw_actions.json`:

```json
[
  {
    "action_type": "onsite_conversion.messaging_conversation_started_7d",
    "value": "3",
    "1d_click": "2",
    "7d_click": "3",
    "action_destination": "whatsapp",
    "action_device": "mobile"
  },
  {
    "action_type": "onsite_conversion.messaging_conversation_started_7d",
    "value": "7",
    "1d_click": "5",
    "7d_click": "7",
    "action_destination": "messenger",
    "action_device": "mobile"
  },
  {
    "action_type": "lead",
    "value": "10",
    "1d_click": "8",
    "7d_click": "10"
  }
]
```

Write these tests:

```python
def test_preserves_one_schema_object_per_api_row(load_json):
    payload = load_json("meta_ads/raw_actions.json")

    rows = parse_raw_ads_action_rows(payload)

    assert len(rows) == len(payload) == 3
    assert rows[0].action_type == payload[0]["action_type"]
    assert rows[0].value == 3
    assert rows[0].attribution_values == (
        AdsAttributionValue(window="1d_click", value=2),
        AdsAttributionValue(window="7d_click", value=3),
    )
    assert rows[0].dimensions == (
        AdsActionDimension(name="action_destination", value="whatsapp"),
        AdsActionDimension(name="action_device", value="mobile"),
    )


def test_composite_index_keeps_destination_device_and_window(load_json):
    rows = parse_raw_ads_action_rows(load_json("meta_ads/raw_actions.json"))

    index = index_raw_ads_actions(rows)

    assert index[
        (
            "onsite_conversion.messaging_conversation_started_7d",
            "1d_click",
            (("action_destination", "whatsapp"), ("action_device", "mobile")),
        )
    ] == (2.0,)
    assert index[
        (
            "onsite_conversion.messaging_conversation_started_7d",
            "1d_click",
            (("action_destination", "messenger"), ("action_device", "mobile")),
        )
    ] == (5.0,)
    assert len(rows) == 3


def test_composite_index_preserves_duplicate_values():
    duplicate = RawAdsActionRow(action_type="lead", value=1)

    index = index_raw_ads_actions((duplicate, duplicate))

    assert index[("lead", None, ())] == (1.0, 1.0)
```

- [ ] **Verify RED — Confirm schemas and parser are missing**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_raw_actions.py
```

Expected: test collection fails on missing `RawAdsActionRow` or `parse_raw_ads_action_rows`.

- [ ] **GREEN — Implement lossless row parsing**

Use this normalization:

```python
ATTRIBUTION_WINDOW_RE = re.compile(r"^\d+d_(?:click|view|engaged_view)$")
CONTROL_FIELDS = frozenset({"action_type", "value"})


def parse_raw_ads_action_rows(
    rows: list[dict[str, Any]] | None,
) -> tuple[RawAdsActionRow, ...]:
    parsed: list[RawAdsActionRow] = []
    for source in rows or []:
        action_type = str(source.get("action_type") or "")
        if not action_type:
            continue
        attribution_values = tuple(
            AdsAttributionValue(window=name, value=float(value))
            for name, value in sorted(source.items())
            if ATTRIBUTION_WINDOW_RE.match(name) and value is not None
        )
        dimensions = tuple(
            AdsActionDimension(name=name, value=str(value))
            for name, value in sorted(source.items())
            if name not in CONTROL_FIELDS
            and not ATTRIBUTION_WINDOW_RE.match(name)
        )
        parsed.append(
            RawAdsActionRow(
                action_type=action_type,
                value=(
                    float(source["value"])
                    if source.get("value") is not None
                    else None
                ),
                attribution_values=attribution_values,
                dimensions=dimensions,
            )
        )
    return tuple(parsed)
```

`index_raw_ads_actions()` creates an aggregate key for a non-`None` row value and one key per `AdsAttributionValue`. Its dictionary values are tuples, so duplicate fully-composite keys remain observable.

- [ ] **REFACTOR — Make key construction a single pure helper**

```python
def raw_action_key(
    row: RawAdsActionRow,
    *,
    attribution_window: str | None,
) -> AdsActionIndexKey:
    return (
        row.action_type,
        attribution_window,
        tuple((dimension.name, dimension.value) for dimension in row.dimensions),
    )
```

Both index creation and later selectors must use `raw_action_key()`.

- [ ] **Verify GREEN — Run tests and lint canonical files**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_raw_actions.py
ruff check src/dashboard/schemas/meta.py src/dashboard/api/meta_ads_parser.py tests/unit/api/test_meta_ads_raw_actions.py
```

- [ ] **Commit — Commit the raw contract**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_ads_parser.py tests/unit/api/test_meta_ads_raw_actions.py tests/fixtures/meta_ads/raw_actions.json
git commit -m "feat: preserve raw Meta Ads action rows"
```

---

### Task 2: Parse named Ads metrics and aggregate only complete additive values

**Dependencies:** Task 1.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/api/meta_ads_parser.py`
- Create: `tests/unit/api/test_meta_ads_metrics.py`
- Create: `tests/fixtures/meta_ads/paid_metrics.json`

**Interfaces:**

```python
class PaidAdsMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    spend: float | None = None
    impressions: int | None = None
    reach: int | None = None
    clicks: int | None = None
    inline_link_clicks: int | None = None
    outbound_clicks: float | None = None
    action_lead: float | None = None
    action_leadgen: float | None = None
    action_pixel_lead: float | None = None
    action_messaging_conversation_started: float | None = None
    action_whatsapp_conversation_started: float | None = None
    action_instagram_follows: float | None = None
    action_profile_views: float | None = None
    cpc: float | None = None
    cpm: float | None = None
    ctr: float | None = None
    frequency: float | None = None
    cost_per_action_lead: float | None = None
    cost_per_action_leadgen: float | None = None
    cost_per_action_pixel_lead: float | None = None
    cost_per_messaging_conversation_started: float | None = None
    cost_per_whatsapp_conversation_started: float | None = None
    action_value_source: str | None = None
    action_value: float | None = None
    roas: float | None = None
    raw_actions_returned: bool = False
    raw_action_values_returned: bool = False
    raw_outbound_clicks_returned: bool = False
    raw_actions: tuple[RawAdsActionRow, ...] = ()
    raw_action_values: tuple[RawAdsActionRow, ...] = ()
    raw_outbound_clicks: tuple[RawAdsActionRow, ...] = ()
```

```python
def parse_paid_ads_metrics(
    payload: Mapping[str, Any],
    *,
    endpoint: str,
    request_group: str,
    action_destination_requested: bool,
) -> tuple[PaidAdsMetrics, tuple[MetricIssue, ...]]: ...


def aggregate_paid_ads_metrics(
    rows: Sequence[PaidAdsMetrics],
    *,
    endpoint: str,
    request_group: str,
    deduplicated_reach: int | None,
    action_value_source: str | None = None,
) -> tuple[PaidAdsMetrics, tuple[MetricIssue, ...]]: ...
```

- [ ] **RED — Add semantic payload and failing tests**

Create `tests/fixtures/meta_ads/paid_metrics.json`:

```json
{
  "spend": "200.00",
  "impressions": "1000",
  "reach": "800",
  "clicks": "100",
  "inline_link_clicks": "35",
  "actions": [
    {"action_type": "lead", "value": "10"},
    {"action_type": "leadgen", "value": "4"},
    {"action_type": "offsite_conversion.fb_pixel_lead", "value": "6"},
    {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "7", "action_destination": "messenger"},
    {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "3", "action_destination": "whatsapp"},
    {"action_type": "instagram_follows", "value": "2"},
    {"action_type": "instagram_profile_views", "value": "9"}
  ],
  "outbound_clicks": [
    {"action_type": "outbound_click", "value": "20", "action_destination": "website"}
  ],
  "action_values": [
    {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "500.00", "action_destination": "website"}
  ]
}
```

Write these tests:

```python
def test_named_actions_remain_separate_and_auditable(load_json):
    metrics, issues = parse_paid_ads_metrics(
        load_json("meta_ads/paid_metrics.json"),
        endpoint="act_1/insights",
        request_group="campaigns",
        action_destination_requested=True,
    )

    assert metrics.clicks == 100
    assert metrics.inline_link_clicks == 35
    assert metrics.outbound_clicks == 20
    assert metrics.action_lead == 10
    assert metrics.action_leadgen == 4
    assert metrics.action_pixel_lead == 6
    assert metrics.action_messaging_conversation_started == 10
    assert metrics.action_whatsapp_conversation_started == 3
    assert metrics.cost_per_action_lead == 20
    assert metrics.cost_per_action_leadgen == 50
    assert metrics.cost_per_action_pixel_lead == 200 / 6
    assert metrics.action_value is None
    assert metrics.roas is None
    assert issues == ()


def test_successful_literal_zero_is_not_missing(load_json):
    payload = {
        **load_json("meta_ads/paid_metrics.json"),
        "clicks": "0",
        "inline_link_clicks": "0",
        "outbound_clicks": [],
        "actions": [],
    }

    metrics, issues = parse_paid_ads_metrics(
        payload,
        endpoint="act_1/insights",
        request_group="account",
        action_destination_requested=True,
    )

    assert metrics.clicks == 0
    assert metrics.inline_link_clicks == 0
    assert metrics.outbound_clicks == 0
    assert metrics.action_lead == 0
    assert metrics.action_whatsapp_conversation_started == 0
    assert not [issue for issue in issues if issue.reason is IssueReason.NOT_RETURNED]


def test_missing_field_is_none_with_issue(load_json):
    payload = load_json("meta_ads/paid_metrics.json")
    payload.pop("clicks")

    metrics, issues = parse_paid_ads_metrics(
        payload,
        endpoint="act_1/insights",
        request_group="account",
        action_destination_requested=True,
    )

    assert metrics.clicks is None
    assert any(
        issue.metric_name == "clicks"
        and issue.reason is IssueReason.NOT_RETURNED
        for issue in issues
    )


def test_aggregation_recalculates_ratios_and_requires_explicit_roas_source():
    first = PaidAdsMetrics(
        spend=40,
        impressions=400,
        reach=250,
        clicks=20,
        inline_link_clicks=8,
        outbound_clicks=5,
        action_lead=2,
        raw_actions_returned=True,
        raw_action_values_returned=True,
        raw_outbound_clicks_returned=True,
        raw_action_values=(
            RawAdsActionRow(
                action_type="offsite_conversion.fb_pixel_purchase",
                value=100,
            ),
        ),
    )
    second = PaidAdsMetrics(
        spend=60,
        impressions=600,
        reach=350,
        clicks=30,
        inline_link_clicks=12,
        outbound_clicks=7,
        action_lead=3,
        raw_actions_returned=True,
        raw_action_values_returned=True,
        raw_outbound_clicks_returned=True,
        raw_action_values=(
            RawAdsActionRow(
                action_type="offsite_conversion.fb_pixel_purchase",
                value=200,
            ),
        ),
    )

    without_source, _ = aggregate_paid_ads_metrics(
        [first, second],
        endpoint="act_1/insights",
        request_group="media_1",
        deduplicated_reach=480,
    )
    with_source, _ = aggregate_paid_ads_metrics(
        [first, second],
        endpoint="act_1/insights",
        request_group="media_1",
        deduplicated_reach=480,
        action_value_source="offsite_conversion.fb_pixel_purchase",
    )

    assert without_source.spend == 100
    assert without_source.impressions == 1000
    assert without_source.clicks == 50
    assert without_source.reach == 480
    assert without_source.cpc == 2
    assert without_source.cpm == 100
    assert without_source.ctr == 5
    assert without_source.frequency == 1000 / 480
    assert without_source.roas is None
    assert with_source.action_value == 300
    assert with_source.roas == 3
    assert len(with_source.raw_action_values) == 2
```

- [ ] **Verify RED — Run named metric tests**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_metrics.py
```

Expected: failures identify missing `PaidAdsMetrics`, semantic parsing, and aggregation.

- [ ] **GREEN — Implement exact named selectors and explicit aggregation**

Use only these additive fields:

```python
ADDITIVE_FIELDS = (
    "spend",
    "impressions",
    "clicks",
    "inline_link_clicks",
    "outbound_clicks",
    "action_lead",
    "action_leadgen",
    "action_pixel_lead",
    "action_messaging_conversation_started",
    "action_whatsapp_conversation_started",
    "action_instagram_follows",
    "action_profile_views",
)
```

If any row has `None` for an additive field, the aggregate field is `None` and receives an incompleteness issue; never sum the available subset. Concatenate all three raw-row tuples. Assign `reach=deduplicated_reach` without reading row reach. Recalculate `cpc`, `cpm`, `ctr`, `frequency`, and every named cost from aggregate numerators and denominators.

When `actions=[]`, named action counts are contractual zero. When `actions` is absent, they are `None`. If messaging rows exist without the requested `action_destination` dimension, the generic messaging count remains available, WhatsApp remains `None`, and a parse issue identifies the missing destination breakdown.

- [ ] **REFACTOR — Centralize exact raw action selection**

```python
def sum_raw_action(
    rows: Sequence[RawAdsActionRow],
    *,
    action_type: str,
    destination: str | None = None,
) -> float: ...
```

This helper accepts only each row’s aggregate `value`, matches `action_type` exactly, and filters `action_destination` only when supplied. Attribution-window values never leak into aggregate counts.

- [ ] **Verify GREEN — Run raw and semantic suites**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_raw_actions.py tests/unit/api/test_meta_ads_metrics.py
ruff check src/dashboard/schemas/meta.py src/dashboard/api/meta_ads_parser.py tests/unit/api/test_meta_ads_metrics.py
```

- [ ] **Commit — Commit semantic parsing and aggregation**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_ads_parser.py tests/unit/api/test_meta_ads_metrics.py tests/fixtures/meta_ads/paid_metrics.json
git commit -m "feat: derive auditable paid metric semantics"
```

---

### Task 3: Add secure transport and explicit query-group status

**Dependencies:** Tasks 1–2 and foundation `MetaAPIError` structured fields.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/api/meta_client.py`
- Create: `tests/unit/api/meta_ads_fakes.py`
- Create: `tests/unit/api/test_meta_ads_transport.py`
- Create: `tests/fixtures/meta_ads/error_permission.json`
- Create: `tests/fixtures/meta_ads/error_rate_limit.json`

**Interfaces:**

```python
class AdsGroupResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    status: DatasetStatus
    rows: tuple[dict[str, Any], ...] = ()
    issues: tuple[MetricIssue, ...] = ()
    truncated: bool = False


def __init__(
    self,
    client_config: ClientConfig,
    *,
    api_version: str = "v26.0",
    session: requests.Session | None = None,
    clock: Callable[[], datetime] = utc_now,
    sleeper: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> None: ...


def _make_request(
    self,
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]: ...


def _run_query_group(
    self,
    *,
    name: str,
    endpoint: str,
    params: dict[str, Any],
) -> AdsGroupResult: ...
```

- [ ] **RED — Define complete response helper and transport tests**

In `tests/unit/api/meta_ads_fakes.py`, define:

```python
def build_response(
    *,
    status_code: int,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = payload
    response.text = json.dumps(payload)
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    else:
        response.raise_for_status.return_value = None
    return response
```

Create `tests/fixtures/meta_ads/error_permission.json`:

```json
{
  "error": {
    "message": "Invalid OAuth access token",
    "type": "OAuthException",
    "code": 190,
    "error_subcode": 463,
    "fbtrace_id": "TRACE_190"
  }
}
```

Create `tests/fixtures/meta_ads/error_rate_limit.json`:

```json
{
  "error": {
    "message": "Application request limit reached",
    "type": "OAuthException",
    "code": 4,
    "error_subcode": 1504022,
    "fbtrace_id": "TRACE_RATE"
  }
}
```

Write these transport tests:

```python
def test_tls_is_enabled(client_config):
    session = Mock()
    session.get.return_value = build_response(status_code=200, payload={"data": []})
    client = MetaAdsClient(client_config, session=session)

    client._make_request("act_1/insights", {"fields": "spend"})

    session.get.assert_called_once_with(
        "https://graph.facebook.com/v26.0/act_1/insights",
        params={"fields": "spend"},
        timeout=10,
        verify=True,
    )


def test_http_200_graph_error_is_still_an_error(client_config):
    session = Mock()
    session.get.return_value = build_response(
        status_code=200,
        payload={
            "error": {
                "message": "Invalid OAuth access token",
                "code": 190,
                "error_subcode": 463,
                "fbtrace_id": "TRACE_190",
            }
        },
    )
    client = MetaAdsClient(client_config, session=session)

    with pytest.raises(MetaAdsAPIError) as caught:
        client._make_request("act_1/insights")

    assert caught.value.issue.code == 190
    assert caught.value.issue.error_subcode == 463
    assert caught.value.issue.fbtrace_id == "TRACE_190"


@pytest.mark.parametrize(
    ("message", "expected_type"),
    [
        ("(#100) Tried accessing nonexisting field foo", IssueType.UNSUPPORTED_METRIC),
        ("(#100) Invalid parameter supplied", IssueType.PARSE),
    ],
)
def test_code_100_requires_message_evidence(message, expected_type, client_config):
    session = Mock()
    session.get.return_value = build_response(
        status_code=400,
        payload={"error": {"message": message, "code": 100}},
    )
    client = MetaAdsClient(client_config, session=session)

    with pytest.raises(MetaAdsAPIError) as caught:
        client._make_request("act_1/insights")

    assert caught.value.issue.issue_type is expected_type


def test_query_group_preserves_first_page_on_second_page_failure(client_config):
    session = Mock()
    session.get.side_effect = [
        build_response(
            status_code=200,
            payload={"data": [{"campaign_id": "cmp_1"}], "paging": {"cursors": {"after": "NEXT"}}},
        ),
        build_response(
            status_code=400,
            payload={"error": {"message": "Invalid parameter", "code": 100}},
        ),
    ]
    client = MetaAdsClient(client_config, session=session)

    result = client._run_query_group(
        name="campaigns",
        endpoint="act_1/insights",
        params={"fields": "campaign_id"},
    )

    assert result.status is DatasetStatus.PARTIAL
    assert result.rows == ({"campaign_id": "cmp_1"},)
    assert result.truncated is True
    assert result.issues
```

```python
def test_rate_limit_retries_three_attempts(load_json, client_config):
    limited = build_response(
        status_code=429,
        payload=load_json("meta_ads/error_rate_limit.json"),
    )
    success = build_response(status_code=200, payload={"data": []})
    session = Mock()
    session.get.side_effect = [limited, limited, success]
    delays: list[float] = []
    client = MetaAdsClient(
        client_config,
        session=session,
        sleeper=delays.append,
        jitter=lambda: 0.0,
    )

    assert client._make_request("act_1/insights") == {"data": []}
    assert session.get.call_count == 3
    assert delays == [1.0, 2.0]


def test_ssl_error_is_not_retried(client_config):
    session = Mock()
    session.get.side_effect = requests.exceptions.SSLError("certificate verify failed")
    client = MetaAdsClient(client_config, session=session)

    with pytest.raises(MetaAdsAPIError) as caught:
        client._make_request("act_1/insights")

    assert session.get.call_count == 1
    assert caught.value.issue.issue_type is IssueType.NETWORK


def test_repeated_cursor_stops_as_partial(client_config):
    repeated = build_response(
        status_code=200,
        payload={
            "data": [{"campaign_id": "cmp_1"}],
            "paging": {"cursors": {"after": "SAME"}},
        },
    )
    session = Mock()
    session.get.side_effect = [repeated, repeated]
    client = MetaAdsClient(client_config, session=session)

    result = client._run_query_group(
        name="campaigns",
        endpoint="act_1/insights",
        params={"fields": "campaign_id"},
    )

    assert result.status is DatasetStatus.PARTIAL
    assert result.truncated is True
    assert session.get.call_count == 2
    assert any(
        issue.issue_type is IssueType.PARTIAL_PAGINATION
        for issue in result.issues
    )


def test_token_never_appears_in_error_or_log(client_config, caplog):
    secret_config = client_config.model_copy(
        update={"token": "TOKEN_MUST_NOT_LEAK"}
    )
    session = Mock()
    session.get.return_value = build_response(
        status_code=401,
        payload={
            "error": {
                "message": "bad TOKEN_MUST_NOT_LEAK",
                "code": 190,
                "fbtrace_id": "TRACE_SAFE",
            }
        },
    )
    client = MetaAdsClient(secret_config, session=session)

    with pytest.raises(MetaAdsAPIError) as caught:
        client._make_request("act_1/insights")

    assert "TOKEN_MUST_NOT_LEAK" not in str(caught.value)
    assert "TOKEN_MUST_NOT_LEAK" not in repr(caught.value)
    assert "TOKEN_MUST_NOT_LEAK" not in caplog.text


def test_api_versions_are_instance_scoped(client_config):
    v25 = MetaAdsClient(client_config, api_version="v25.0", session=Mock())
    v26 = MetaAdsClient(client_config, api_version="v26.0", session=Mock())

    assert v25.base_url == "https://graph.facebook.com/v25.0"
    assert v26.base_url == "https://graph.facebook.com/v26.0"
```

- [ ] **Verify RED — Run transport suite**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_transport.py
```

Expected: failures identify disabled TLS, missing structured groups, and HTTP-200 error handling.

- [ ] **GREEN — Implement transport without touching legacy loops**

Store the injected clock as `self.clock`. Use three attempts only for timeout, connection errors, HTTP `429/500/502/503/504`, and Graph codes `1/2/4/17/32/613/80004`. Use `min(2**attempt + jitter(), 8.0)` before attempts two and three. `SSLError` fails immediately.

Classify code `190`, code `10`, and HTTP `401/403` as permission. Classify code `100` as unsupported only when the lowercase message contains `nonexisting field`, `not valid for fields param`, `unsupported get request`, or `cannot be used with`; otherwise classify it as parse. Inspect top-level `error` before trusting HTTP status.

Capture only `X-App-Usage`, `X-Page-Usage`, and `X-Business-Use-Case-Usage`. Log endpoint, status, code, subcode, and `fbtrace_id`; never log raw message/body/token.

`_run_query_group()` returns `EMPTY` for successful no-row pagination, `OK` for complete rows, `PARTIAL` for rows plus an error/repeated cursor, and `UNAVAILABLE` for failure before any row. It copies params and tracks cursors without mutating caller input.

- [ ] **REFACTOR — Keep the new transport path isolated**

Call `_run_query_group()` only from new report methods added in later tasks. Do not modify `get_campaign_insights()`, `get_creative_performance()`, `get_ads_reach_mapping()`, `get_instagram_paid_totals()`, or their loops.

- [ ] **Verify GREEN — Run transport and parser regression**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_transport.py tests/unit/api/test_meta_ads_raw_actions.py tests/unit/api/test_meta_ads_metrics.py
ruff check src/dashboard/api/meta_client.py tests/unit/api/meta_ads_fakes.py tests/unit/api/test_meta_ads_transport.py
```

- [ ] **Commit — Commit secure query groups**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_client.py tests/unit/api/meta_ads_fakes.py tests/unit/api/test_meta_ads_transport.py tests/fixtures/meta_ads/error_permission.json tests/fixtures/meta_ads/error_rate_limit.json
git commit -m "fix: secure Meta Ads query groups"
```

---

### Task 4: Resolve account context, horizons, and attribution conflicts

**Dependencies:** Tasks 1–3.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/api/meta_ads_parser.py`
- Modify: `src/dashboard/api/meta_client.py`
- Create: `tests/unit/api/test_meta_ads_context.py`
- Create: `tests/fixtures/meta_ads/ad_account_context.json`
- Create: `tests/fixtures/meta_ads/attribution_conflict.json`

**Interfaces:**

```python
class AdAccountContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    ad_account_id: str
    currency: str | None = None
    timezone_name: str | None = None


class AttributionRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_type: str
    window_days: int


class AdSetAttribution(BaseModel):
    model_config = ConfigDict(frozen=True)
    adset_id: str
    source_ad_ids: tuple[str, ...]
    rules: tuple[AttributionRule, ...]


class AdsReportingContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    report_time: Literal["mixed"] = "mixed"
    requested_attribution_windows: tuple[str, ...]
    returned_attribution_windows: tuple[str, ...]
    attribution_specs: tuple[AdSetAttribution, ...]
    ignored_parameters: tuple[str, ...] = (
        "action_report_time",
        "use_unified_attribution_setting",
    )
```

```python
def parse_ad_account_context(
    ad_account_id: str,
    payload: Mapping[str, Any],
    *,
    endpoint: str,
) -> tuple[AdAccountContext, tuple[MetricIssue, ...]]: ...


def get_ad_account_context(
    self,
) -> tuple[AdAccountContext, tuple[MetricIssue, ...]]: ...


def parse_attribution_specs(
    ads: Sequence[Mapping[str, Any]],
    *,
    endpoint: str,
) -> tuple[tuple[AdSetAttribution, ...], tuple[MetricIssue, ...]]: ...


def returned_attribution_windows(
    metric_groups: Sequence[Sequence[PaidAdsMetrics]],
) -> tuple[str, ...]: ...


def resolve_ads_period(
    *,
    date_preset: str,
    time_range: dict[str, str] | None,
    platform_scope: Literal["instagram", "all_meta"],
    timezone_name: str | None,
    now: datetime,
) -> tuple[PeriodWindow | None, DatasetStatus, tuple[MetricIssue, ...]]: ...
```

- [ ] **RED — Add context and conflict tests**

Create `tests/fixtures/meta_ads/ad_account_context.json`:

```json
{
  "id": "act_1",
  "currency": "USD",
  "timezone_name": "America/New_York"
}
```

Create `tests/fixtures/meta_ads/attribution_conflict.json`:

```json
{
  "data": [
    {
      "id": "ad_1",
      "adset": {
        "id": "adset_1",
        "attribution_spec": [
          {"event_type": "CLICK_THROUGH", "window_days": 7},
          {"event_type": "VIEW_THROUGH", "window_days": 1}
        ]
      }
    },
    {
      "id": "ad_2",
      "adset": {
        "id": "adset_1",
        "attribution_spec": [
          {"event_type": "CLICK_THROUGH", "window_days": 1}
        ]
      }
    }
  ]
}
```

Both candidate specs must survive. Write these assertions:

```python
def test_missing_timezone_blocks_preset_but_not_explicit_custom_range():
    preset = resolve_ads_period(
        date_preset="last_30d",
        time_range=None,
        platform_scope="all_meta",
        timezone_name=None,
        now=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    custom = resolve_ads_period(
        date_preset="custom",
        time_range={"since": "2026-08-01", "until": "2026-08-30"},
        platform_scope="all_meta",
        timezone_name=None,
        now=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    assert preset[0] is None
    assert preset[1] is DatasetStatus.UNAVAILABLE
    assert custom[0] == PeriodWindow(
        basis=PeriodBasis.AD_DELIVERY_WINDOW,
        requested_since=date(2026, 8, 1),
        requested_until=date(2026, 8, 30),
        effective_since=date(2026, 8, 1),
        effective_until=date(2026, 8, 30),
    )
    assert custom[1] is DatasetStatus.PARTIAL
    assert custom[2]


def test_custom_horizon_clamps_old_and_future_dates():
    period, status, issues = resolve_ads_period(
        date_preset="custom",
        time_range={"since": "2020-01-01", "until": "2027-01-01"},
        platform_scope="instagram",
        timezone_name="America/New_York",
        now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc),
    )

    assert period == PeriodWindow(
        basis=PeriodBasis.AD_DELIVERY_WINDOW,
        requested_since=date(2020, 1, 1),
        requested_until=date(2027, 1, 1),
        effective_since=date(2025, 7, 30),
        effective_until=date(2026, 8, 30),
    )
    assert status is DatasetStatus.PARTIAL
    assert len(issues) == 2


def test_attribution_conflicts_are_preserved_and_issued(load_json):
    payload = load_json("meta_ads/attribution_conflict.json")

    specs, issues = parse_attribution_specs(
        payload["data"],
        endpoint="act_1/ads",
    )

    assert len(specs) == 2
    assert {spec.adset_id for spec in specs} == {"adset_1"}
    assert any(issue.request_group == "attribution_spec" for issue in issues)


def test_requested_and_returned_windows_are_distinct():
    metrics = PaidAdsMetrics(
        raw_actions_returned=True,
        raw_actions=(
            RawAdsActionRow(
                action_type="lead",
                value=1,
                attribution_values=(AdsAttributionValue(window="1d_click", value=1),),
            ),
        ),
    )
    context = AdsReportingContext(
        requested_attribution_windows=("1d_click", "7d_click", "28d_click", "1d_view"),
        returned_attribution_windows=returned_attribution_windows(((metrics,),)),
        attribution_specs=(),
    )

    assert context.requested_attribution_windows == (
        "1d_click", "7d_click", "28d_click", "1d_view"
    )
    assert context.returned_attribution_windows == ("1d_click",)


def test_reads_account_currency_and_timezone(load_json):
    context, issues = parse_ad_account_context(
        "act_1",
        load_json("meta_ads/ad_account_context.json"),
        endpoint="act_1",
    )

    assert context == AdAccountContext(
        ad_account_id="act_1",
        currency="USD",
        timezone_name="America/New_York",
    )
    assert issues == ()
```

- [ ] **Verify RED — Run account-context tests**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_context.py
```

- [ ] **GREEN — Implement account authority and period clamps**

Request account context with `fields=currency,timezone_name`. Resolve `last_30d` and `maximum` from `ZoneInfo(timezone_name)`. Maximum horizons are 37 calendar months for all-Meta and 13 calendar months for Instagram breakdown reports. Clamp custom `effective_since` to the oldest allowed date and `effective_until` to the account-local current date while retaining both requested dates.

Every constructed `PeriodWindow` sets `basis=PeriodBasis.AD_DELIVERY_WINDOW`, including EMPTY windows with `effective_since=None` and `effective_until=None`.

If timezone is absent, presets return unavailable without issuing Insights queries. Explicit custom dates proceed as partial using their literal dates and keep `DatasetMeta.timezone=None`; future clamping uses `now.date()` and adds a timezone issue. A future-only custom interval returns `EMPTY` with a `PeriodWindow` whose effective fields are `None`.

Deduplicate identical attribution specs. If one ad set has distinct specs, preserve each distinct candidate with its source ad IDs and add a conflict issue. `returned_attribution_windows()` scans `raw_actions`, `raw_action_values`, and `raw_outbound_clicks`, unions only windows physically present in those rows, and returns them in requested-order followed by any unexpected returned windows in lexical order.

- [ ] **REFACTOR — Emit fields by level and no ignored parameters**

```python
COMMON_INSIGHT_FIELDS = (
    "spend,impressions,reach,frequency,clicks,inline_link_clicks,"
    "outbound_clicks,actions,action_values,date_start,date_stop"
)


def _insight_fields(level: Literal["account", "campaign", "ad"]) -> str:
    if level == "account":
        return COMMON_INSIGHT_FIELDS
    if level == "campaign":
        return f"campaign_id,campaign_name,objective,{COMMON_INSIGHT_FIELDS}"
    return (
        "ad_id,ad_name,campaign_id,campaign_name,objective,"
        f"{COMMON_INSIGHT_FIELDS}"
    )
```

`_build_insights_params()` sends explicit effective `time_range`, `action_breakdowns=action_destination`, and `action_attribution_windows=1d_click,7d_click,28d_click,1d_view`. It adds `breakdowns=publisher_platform` only for Instagram and never sends either ignored parameter.

- [ ] **Verify GREEN — Run context, transport, and parser suites**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_context.py tests/unit/api/test_meta_ads_transport.py tests/unit/api/test_meta_ads_raw_actions.py tests/unit/api/test_meta_ads_metrics.py
ruff check src/dashboard/schemas/meta.py src/dashboard/api/meta_ads_parser.py src/dashboard/api/meta_client.py tests/unit/api/test_meta_ads_context.py
```

- [ ] **Commit — Commit authoritative context**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_ads_parser.py src/dashboard/api/meta_client.py tests/unit/api/test_meta_ads_context.py tests/fixtures/meta_ads/ad_account_context.json tests/fixtures/meta_ads/attribution_conflict.json
git commit -m "feat: record paid attribution and account horizons"
```

---

### Task 5: Assemble platform-scoped paid account, campaign, and ad groups

**Dependencies:** Tasks 1–4.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/api/meta_client.py`
- Modify: `tests/unit/api/meta_ads_fakes.py`
- Create: `tests/unit/api/test_paid_ads_report.py`
- Create: `tests/fixtures/meta_ads/scoped_paid_report.json`

**Interfaces:**

```python
class PaidCampaign(BaseModel):
    model_config = ConfigDict(frozen=True)
    campaign_id: str
    campaign_name: str
    objective: str
    metrics: PaidAdsMetrics
    status: DatasetStatus
    issues: tuple[MetricIssue, ...] = ()


class PaidCreative(BaseModel):
    model_config = ConfigDict(frozen=True)
    ad_id: str
    ad_name: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    adset_id: str | None = None
    adset_name: str | None = None
    objective: str = "UNKNOWN"
    effective_instagram_media_id: str | None = None
    source_instagram_media_id: str | None = None
    traffic_destination: str | None = None
    attribution: tuple[AdSetAttribution, ...] = ()
    metrics: PaidAdsMetrics
    status: DatasetStatus
    issues: tuple[MetricIssue, ...] = ()


class PaidAdsReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    meta: DatasetMeta
    account_group: AdsGroupResult
    campaign_group: AdsGroupResult
    ad_group: AdsGroupResult
    metadata_group: AdsGroupResult
    totals: PaidAdsMetrics | None = None
    campaigns: tuple[PaidCampaign, ...] = ()
    creatives: tuple[PaidCreative, ...] = ()
    reporting_context: AdsReportingContext
```

`AdsGroupResult` is imported from the canonical `schemas/meta.py`; `meta_client.py` must not define a duplicate.

```python
def get_paid_ads_report(
    self,
    *,
    date_preset: str = "last_30d",
    time_range: dict[str, str] | None = None,
    platform_scope: Literal["instagram", "all_meta"] = "all_meta",
) -> PaidAdsReport: ...
```

- [ ] **RED — Add complete scoped fixture and report fake**

`scoped_paid_report.json` must include these independent keys:

```json
{
  "account_all_meta": {
    "data": [{"spend": "100", "impressions": "1000", "reach": "720", "frequency": "1.3888889", "clicks": "80", "inline_link_clicks": "32", "cpc": "1.25", "cpm": "100", "ctr": "8", "outbound_clicks": [{"action_type": "outbound_click", "value": "23"}], "actions": [], "action_values": [], "date_start": "2026-08-01", "date_stop": "2026-08-30"}]
  },
  "account_instagram": {
    "data": [
      {"publisher_platform": "instagram", "spend": "40", "impressions": "400", "reach": "300", "frequency": "1.3333333", "clicks": "30", "inline_link_clicks": "12", "cpc": "1.3333333", "cpm": "100", "ctr": "7.5", "outbound_clicks": [{"action_type": "outbound_click", "value": "8"}], "actions": [], "action_values": [], "date_start": "2026-08-01", "date_stop": "2026-08-30"},
      {"publisher_platform": "facebook", "spend": "60", "impressions": "600", "reach": "500", "frequency": "1.2", "clicks": "50", "inline_link_clicks": "20", "cpc": "1.2", "cpm": "100", "ctr": "8.3333333", "outbound_clicks": [{"action_type": "outbound_click", "value": "15"}], "actions": [], "action_values": [], "date_start": "2026-08-01", "date_stop": "2026-08-30"}
    ]
  },
  "campaigns_all_meta": {
    "data": [
      {"campaign_id": "cmp_1", "campaign_name": "One", "objective": "OUTCOME_TRAFFIC", "spend": "40", "impressions": "400", "reach": "350", "frequency": "1.1428571", "clicks": "30", "inline_link_clicks": "12", "cpc": "1.3333333", "cpm": "100", "ctr": "7.5", "outbound_clicks": [], "actions": [], "action_values": []},
      {"campaign_id": "cmp_2", "campaign_name": "Two", "objective": "OUTCOME_LEADS", "spend": "60", "impressions": "600", "reach": "500", "frequency": "1.2", "clicks": "50", "inline_link_clicks": "20", "cpc": "1.2", "cpm": "100", "ctr": "8.3333333", "outbound_clicks": [], "actions": [], "action_values": []}
    ]
  },
  "campaigns_instagram": {
    "data": [{"campaign_id": "cmp_1", "campaign_name": "One", "objective": "OUTCOME_TRAFFIC", "publisher_platform": "instagram", "spend": "40", "impressions": "400", "reach": "300", "frequency": "1.3333333", "clicks": "30", "inline_link_clicks": "12", "cpc": "1.3333333", "cpm": "100", "ctr": "7.5", "outbound_clicks": [], "actions": [], "action_values": []}]
  },
  "ads_all_meta": {"data": []},
  "ads_instagram": {"data": []},
  "metadata": {"data": []}
}
```

Extend `meta_ads_fakes.py` with a complete fake:

```python
class ReportFakeClient(MetaAdsClient):
    def __init__(
        self,
        client_config,
        *,
        groups: dict[str, AdsGroupResult],
        account_context: AdAccountContext,
        account_issues: tuple[MetricIssue, ...] = (),
    ) -> None:
        super().__init__(
            client_config,
            session=Mock(),
            clock=lambda: datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        )
        self.groups = groups
        self.account_context = account_context
        self.account_issues = account_issues

    def get_ad_account_context(self):
        return self.account_context, self.account_issues

    def _run_insights_group(self, *, name, level, time_range, platform_scope):
        return self.groups[name]

    def _load_ad_metadata(self):
        return self.groups["metadata"]
```

In `test_paid_ads_report.py`, define the complete group factory and report fixtures:

```python
def group_from_fixture(name, payload):
    rows = tuple(payload["data"])
    return AdsGroupResult(
        name=name,
        status=DatasetStatus.OK if rows else DatasetStatus.EMPTY,
        rows=rows,
    )


def make_report_client(client_config, fixture, *, platform_scope):
    suffix = "instagram" if platform_scope == "instagram" else "all_meta"
    return ReportFakeClient(
        client_config,
        groups={
            "account": group_from_fixture("account", fixture[f"account_{suffix}"]),
            "campaigns": group_from_fixture(
                "campaigns", fixture[f"campaigns_{suffix}"]
            ),
            "ads": group_from_fixture("ads", fixture[f"ads_{suffix}"]),
            "metadata": group_from_fixture("metadata", fixture["metadata"]),
        },
        account_context=AdAccountContext(
            ad_account_id="act_1",
            currency="USD",
            timezone_name="America/New_York",
        ),
    )


@pytest.fixture
def all_meta_report_client(load_json, client_config):
    return make_report_client(
        client_config,
        load_json("meta_ads/scoped_paid_report.json"),
        platform_scope="all_meta",
    )


@pytest.fixture
def instagram_report_client(load_json, client_config):
    return make_report_client(
        client_config,
        load_json("meta_ads/scoped_paid_report.json"),
        platform_scope="instagram",
    )


@pytest.fixture
def empty_report_client(client_config):
    empty = AdsGroupResult(name="empty", status=DatasetStatus.EMPTY)
    return ReportFakeClient(
        client_config,
        groups={
            "account": empty.model_copy(update={"name": "account"}),
            "campaigns": empty.model_copy(update={"name": "campaigns"}),
            "ads": empty.model_copy(update={"name": "ads"}),
            "metadata": empty.model_copy(update={"name": "metadata"}),
        },
        account_context=AdAccountContext(
            ad_account_id="act_1",
            currency="USD",
            timezone_name="America/New_York",
        ),
    )


@pytest.fixture
def partial_report_client(all_meta_report_client):
    issue = MetricIssue(
        endpoint="act_1/insights",
        request_group="campaigns",
        issue_type=IssueType.PARTIAL_PAGINATION,
        reason=IssueReason.ERROR,
        safe_message="A paginação de campanhas ficou incompleta.",
        can_display=True,
    )
    current = all_meta_report_client.groups["campaigns"]
    all_meta_report_client.groups["campaigns"] = current.model_copy(
        update={
            "status": DatasetStatus.PARTIAL,
            "issues": (issue,),
            "truncated": True,
        }
    )
    return all_meta_report_client
```

Tests assert:

```python
def test_all_meta_uses_unbroken_account_reach_720(all_meta_report_client):
    report = all_meta_report_client.get_paid_ads_report(platform_scope="all_meta")

    assert report.totals is not None
    assert report.totals.reach == 720
    assert sum(campaign.metrics.reach or 0 for campaign in report.campaigns) == 850
    assert report.totals.reach != 850
    assert report.meta.platform_scope == "all_meta"
    assert report.meta.retrieved_at == datetime(
        2026, 8, 30, 12, 0, tzinfo=timezone.utc
    )


def test_instagram_discards_facebook_rows(instagram_report_client):
    report = instagram_report_client.get_paid_ads_report(platform_scope="instagram")

    assert report.totals is not None
    assert report.totals.spend == 40
    assert report.totals.reach == 300
    assert report.totals.clicks == 30
    assert report.totals.outbound_clicks == 8
    assert len(report.campaigns) == 1
    assert report.meta.platform_scope == "instagram"


def test_empty_success_has_zero_additives_and_empty_status(empty_report_client):
    report = empty_report_client.get_paid_ads_report(platform_scope="all_meta")

    assert report.meta.status is DatasetStatus.EMPTY
    assert report.totals == PaidAdsMetrics(
        spend=0,
        impressions=0,
        reach=0,
        clicks=0,
        inline_link_clicks=0,
        outbound_clicks=0,
        action_lead=0,
        action_leadgen=0,
        action_pixel_lead=0,
        action_messaging_conversation_started=0,
        action_whatsapp_conversation_started=0,
        action_instagram_follows=0,
        action_profile_views=0,
        raw_actions_returned=True,
        raw_action_values_returned=True,
        raw_outbound_clicks_returned=True,
    )


def test_partial_group_is_explicit_and_preserves_rows(partial_report_client):
    report = partial_report_client.get_paid_ads_report(platform_scope="all_meta")

    assert report.meta.status is DatasetStatus.PARTIAL
    assert report.campaign_group.status is DatasetStatus.PARTIAL
    assert report.campaigns
    assert report.meta.truncated is True
```

- [ ] **Verify RED — Run scoped report tests**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_paid_ads_report.py
```

- [ ] **GREEN — Implement group-preserving report assembly**

Run independent account, campaign, ad, and metadata groups. For Instagram, filter every Insights group to `publisher_platform="instagram"`; for all-Meta, query without publisher breakdown. Parse account totals only from the account group. Never reconstruct them from campaigns or ads.

If account timezone is missing for a preset, return an unavailable report without Insights calls. If a custom range supplies dates, continue partial and preserve timezone `None`. Build `DatasetMeta.status` from explicit group statuses: unavailable when the account group cannot produce totals, partial when any displayable group is partial/unavailable or any parser/context issue exists, empty when every successful data group is empty, otherwise OK.

`AdsGroupResult` retains raw rows for audit. `PaidCampaign` and `PaidCreative` retain row-level status/issues. Build reporting context from requested windows, actually returned windows, and metadata attribution candidates.

- [ ] **REFACTOR — Use exact new helpers without touching legacy methods**

```python
def _run_insights_group(
    self,
    *,
    name: str,
    level: Literal["account", "campaign", "ad"],
    time_range: dict[str, str],
    platform_scope: Literal["instagram", "all_meta"],
) -> AdsGroupResult: ...


def _empty_paid_ads_metrics() -> PaidAdsMetrics: ...
```

Sort campaign and creative outputs deterministically. Do not edit any legacy public method in this task.

- [ ] **Verify GREEN — Run scoped report and dependency suites**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_paid_ads_report.py tests/unit/api/test_meta_ads_context.py tests/unit/api/test_meta_ads_transport.py tests/unit/api/test_meta_ads_metrics.py
ruff check src/dashboard/schemas/meta.py src/dashboard/api/meta_client.py tests/unit/api/meta_ads_fakes.py tests/unit/api/test_paid_ads_report.py
```

- [ ] **Commit — Commit platform-scoped groups**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_client.py tests/unit/api/meta_ads_fakes.py tests/unit/api/test_paid_ads_report.py tests/fixtures/meta_ads/scoped_paid_report.json
git commit -m "feat: assemble scoped paid Ads groups"
```

---

### Task 6: Add typed paid-demographic groups

**Dependencies:** Tasks 1–5.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/api/meta_client.py`
- Modify: `tests/unit/api/meta_ads_fakes.py`
- Create: `tests/unit/api/test_paid_demographics.py`
- Create: `tests/fixtures/meta_ads/paid_demographics.json`

**Interfaces:**

```python
PaidEntityLevel = Literal["account", "campaign", "ad"]
PaidDemographicBreakdown = Literal["age_gender", "country", "region"]


class PaidDemographicRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    breakdown: PaidDemographicBreakdown
    entity_level: PaidEntityLevel
    entity_id: str
    publisher_platform: str | None = None
    dimensions: tuple[AdsActionDimension, ...]
    reach: int | None = None
    impressions: int | None = None
    spend: float | None = None
    status: DatasetStatus
    issues: tuple[MetricIssue, ...] = ()


class PaidDemographicGroup(BaseModel):
    model_config = ConfigDict(frozen=True)
    breakdown: PaidDemographicBreakdown
    entity_level: PaidEntityLevel
    platform_scope: Literal["instagram", "all_meta"]
    status: DatasetStatus
    rows: tuple[PaidDemographicRow, ...] = ()
    issues: tuple[MetricIssue, ...] = ()


class PaidDemographicsReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    meta: DatasetMeta
    groups: tuple[PaidDemographicGroup, ...]
```

```python
def get_paid_demographics_report(
    self,
    *,
    date_preset: str = "last_30d",
    time_range: dict[str, str] | None = None,
    platform_scope: Literal["instagram", "all_meta"] = "all_meta",
    entity_level: PaidEntityLevel = "account",
) -> PaidDemographicsReport: ...
```

- [ ] **RED — Add typed demographic fixture and tests**

Create `tests/fixtures/meta_ads/paid_demographics.json`:

```json
{
  "age_gender": {
    "data": [
      {"ad_id": "ad_1", "publisher_platform": "instagram", "age": "25-34", "gender": "female", "reach": "80", "impressions": "120", "spend": "12"},
      {"ad_id": "ad_1", "publisher_platform": "facebook", "age": "25-34", "gender": "female", "reach": "40", "impressions": "60", "spend": "6"}
    ]
  },
  "country": {
    "data": [
      {"ad_id": "ad_1", "publisher_platform": "instagram", "country": "BR", "reach": "100", "impressions": "150", "spend": "15"}
    ]
  },
  "region": {
    "data": [
      {"ad_id": "ad_1", "publisher_platform": "instagram", "region": "Rio Grande do Norte", "reach": "70", "impressions": "100", "spend": "10"}
    ]
  }
}
```

Extend `tests/unit/api/meta_ads_fakes.py` with:

```python
class DemographicsFakeClient(ReportFakeClient):
    def _run_paid_demographic_group(
        self,
        *,
        breakdown,
        entity_level,
        time_range,
        platform_scope,
    ):
        return self.groups[breakdown]
```

In `test_paid_demographics.py`, define the complete fixtures:

```python
@pytest.fixture
def demographics_client(load_json, client_config):
    payload = load_json("meta_ads/paid_demographics.json")
    groups = {
        name: AdsGroupResult(
            name=name,
            status=DatasetStatus.OK,
            rows=tuple(payload[name]["data"]),
        )
        for name in ("age_gender", "country", "region")
    }
    return DemographicsFakeClient(
        client_config,
        groups=groups,
        account_context=AdAccountContext(
            ad_account_id="act_1",
            currency="USD",
            timezone_name="America/New_York",
        ),
    )


@pytest.fixture
def partial_demographics_client(demographics_client):
    permission_issue = MetricIssue(
        endpoint="act_1/insights",
        request_group="country",
        issue_type=IssueType.PERMISSION,
        reason=IssueReason.PERMISSION_DENIED,
        safe_message="A Meta recusou este breakdown.",
        can_display=False,
    )
    demographics_client.groups["country"] = AdsGroupResult(
        name="country",
        status=DatasetStatus.UNAVAILABLE,
        issues=(permission_issue,),
    )
    return demographics_client
```

Filtering by publisher platform remains production behavior. Write:

```python
def test_demographic_row_carries_breakdown_entity_platform_and_status(demographics_client):
    report = demographics_client.get_paid_demographics_report(
        platform_scope="instagram",
        entity_level="ad",
    )

    age_group = next(group for group in report.groups if group.breakdown == "age_gender")
    row = age_group.rows[0]
    assert age_group.platform_scope == "instagram"
    assert age_group.entity_level == "ad"
    assert age_group.status is DatasetStatus.OK
    assert row.entity_id == "ad_1"
    assert row.publisher_platform == "instagram"
    assert row.dimensions == (
        AdsActionDimension(name="age", value="25-34"),
        AdsActionDimension(name="gender", value="female"),
    )
    assert row.reach == 80
    assert row.impressions == 120
    assert row.spend == 12
    assert row.status is DatasetStatus.OK
    assert row.issues == ()


def test_one_failed_breakdown_makes_only_that_group_unavailable(partial_demographics_client):
    report = partial_demographics_client.get_paid_demographics_report(
        platform_scope="all_meta",
        entity_level="account",
    )

    statuses = {group.breakdown: group.status for group in report.groups}
    assert statuses == {
        "age_gender": DatasetStatus.OK,
        "country": DatasetStatus.UNAVAILABLE,
        "region": DatasetStatus.OK,
    }
    assert report.meta.status is DatasetStatus.PARTIAL
```

- [ ] **Verify RED — Run demographic tests**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_paid_demographics.py
```

- [ ] **GREEN — Implement one query group per documented breakdown**

Map `age_gender` to `breakdowns=age,gender`, `country` to `country`, and `region` to `region`. Do not call region a city. Add publisher breakdown only for Instagram. Fields are `reach,impressions,spend` plus `campaign_id,campaign_name` at campaign level or `ad_id,ad_name` at ad level. Account rows use `self.ad_account_id` as entity ID. Never sum demographic reach rows into a unique total.

Each breakdown preserves its own status/issues. Missing row fields are `None` with row issues. Report status is OK only when every group is OK, EMPTY when every group is empty, UNAVAILABLE when every group is unavailable, and PARTIAL for mixed outcomes.

- [ ] **REFACTOR — Share group execution but not demographic semantics**

Reuse `_run_query_group()` for pagination and error capture. Keep demographic parsing in a dedicated pure helper:

```python
def parse_paid_demographic_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    breakdown: PaidDemographicBreakdown,
    entity_level: PaidEntityLevel,
    platform_scope: Literal["instagram", "all_meta"],
    account_id: str,
    endpoint: str,
) -> tuple[tuple[PaidDemographicRow, ...], tuple[MetricIssue, ...]]: ...
```

- [ ] **Verify GREEN — Run demographics and report suites**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_paid_demographics.py tests/unit/api/test_paid_ads_report.py
ruff check src/dashboard/schemas/meta.py src/dashboard/api/meta_client.py tests/unit/api/test_paid_demographics.py
```

- [ ] **Commit — Commit typed paid demographics**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_client.py tests/unit/api/meta_ads_fakes.py tests/unit/api/test_paid_demographics.py tests/fixtures/meta_ads/paid_demographics.json
git commit -m "feat: type paid demographic groups"
```

---

### Task 7: Map recoverable Instagram media IDs and reconcile spend coverage

**Dependencies:** Tasks 1–6. Applies only to `platform_scope="instagram"`.

**Files:**

- Modify: `src/dashboard/schemas/meta.py`
- Modify: `src/dashboard/api/meta_client.py`
- Modify: `tests/unit/api/meta_ads_fakes.py`
- Create: `tests/unit/api/test_paid_media_identity.py`
- Create: `tests/fixtures/meta_ads/paid_media_identity.json`

**Interfaces:**

```python
class PaidMediaSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    instagram_media_id: str
    media_id_basis: Literal["effective", "source", "mixed"]
    ad_ids: tuple[str, ...]
    metrics: PaidAdsMetrics
    reach_deduplicated: bool | None
    status: DatasetStatus
    issues: tuple[MetricIssue, ...] = ()


class PaidDeliveryWithoutMediaId(BaseModel):
    model_config = ConfigDict(frozen=True)
    ad_id: str
    effective_instagram_media_id: str | None
    source_instagram_media_id: str | None
    spend: float | None
    reason: Literal["metadata_missing", "instagram_media_id_missing"]


class PaidMediaIdentityCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)
    basis: Literal[
        "ad_delivery_spend_with_recoverable_instagram_media_id"
    ] = "ad_delivery_spend_with_recoverable_instagram_media_id"
    account_total_spend: float | None
    ad_delivery_spend: float | None
    spend_reconciliation_delta: float | None
    spend_reconciled: bool | None
    spend_with_recoverable_instagram_media_id: float | None
    spend_without_recoverable_instagram_media_id: float | None
    coverage_pct: float | None
    status: DatasetStatus
    issues: tuple[MetricIssue, ...] = ()
```

Extend `PaidAdsReport` with:

```python
by_instagram_media_id: dict[str, PaidMediaSummary] = Field(default_factory=dict)
delivery_without_media_id: tuple[PaidDeliveryWithoutMediaId, ...] = ()
media_identity_coverage: PaidMediaIdentityCoverage | None = None
```

```python
def _get_instagram_aggregate_reach(
    self,
    *,
    ad_ids: tuple[str, ...],
    time_range: dict[str, str],
) -> tuple[int | None, MetricIssue | None]: ...


def _build_paid_media_identity(
    self,
    *,
    totals: PaidAdsMetrics | None,
    creatives: Sequence[PaidCreative],
    time_range: dict[str, str],
    ad_group_status: DatasetStatus,
) -> tuple[
    dict[str, PaidMediaSummary],
    tuple[PaidDeliveryWithoutMediaId, ...],
    PaidMediaIdentityCoverage,
    tuple[MetricIssue, ...],
]: ...
```

- [ ] **RED — Add identity fixture, mapping fake, and reconciliation tests**

Create `tests/fixtures/meta_ads/paid_media_identity.json`:

```json
{
  "account_instagram": {
    "data": [{"publisher_platform": "instagram", "spend": "110", "impressions": "1100", "reach": "760", "frequency": "1.4473684", "clicks": "55", "inline_link_clicks": "22", "cpc": "2", "cpm": "100", "ctr": "5", "outbound_clicks": [], "actions": [], "action_values": [], "date_start": "2026-08-01", "date_stop": "2026-08-30"}]
  },
  "campaigns_instagram": {"data": []},
  "ads_instagram": {
    "data": [
      {"ad_id": "ad_1", "ad_name": "Ad One", "publisher_platform": "instagram", "spend": "40", "impressions": "400", "reach": "250", "frequency": "1.6", "clicks": "20", "inline_link_clicks": "8", "cpc": "2", "cpm": "100", "ctr": "5", "outbound_clicks": [], "actions": [], "action_values": []},
      {"ad_id": "ad_2", "ad_name": "Ad Two", "publisher_platform": "instagram", "spend": "35", "impressions": "350", "reach": "220", "frequency": "1.5909091", "clicks": "18", "inline_link_clicks": "7", "cpc": "1.9444444", "cpm": "100", "ctr": "5.1428571", "outbound_clicks": [], "actions": [], "action_values": []},
      {"ad_id": "ad_3", "ad_name": "Ad Three", "publisher_platform": "instagram", "spend": "25", "impressions": "250", "reach": "180", "frequency": "1.3888889", "clicks": "12", "inline_link_clicks": "5", "cpc": "2.0833333", "cpm": "100", "ctr": "4.8", "outbound_clicks": [], "actions": [], "action_values": []},
      {"ad_id": "ad_4", "ad_name": "Ad Four", "publisher_platform": "instagram", "spend": "10", "impressions": "100", "reach": "90", "frequency": "1.1111111", "clicks": "5", "inline_link_clicks": "2", "cpc": "2", "cpm": "100", "ctr": "5", "outbound_clicks": [], "actions": [], "action_values": []}
    ]
  },
  "metadata": {
    "data": [
      {"id": "ad_1", "creative": {"effective_instagram_media_id": "media_1", "source_instagram_media_id": "source_old_1"}, "adset": {"id": "adset_1", "attribution_spec": []}},
      {"id": "ad_2", "creative": {"effective_instagram_media_id": "media_1", "source_instagram_media_id": "source_old_2"}, "adset": {"id": "adset_1", "attribution_spec": []}},
      {"id": "ad_3", "creative": {"source_instagram_media_id": "media_2"}, "adset": {"id": "adset_2", "attribution_spec": []}},
      {"id": "ad_4", "creative": {}, "adset": {"id": "adset_3", "attribution_spec": []}}
    ]
  },
  "aggregate_reach": {
    "ad_1,ad_2": {
      "data": [
        {"publisher_platform": "instagram", "reach": "390"},
        {"publisher_platform": "facebook", "reach": "70"}
      ]
    }
  }
}
```

Extend `meta_ads_fakes.py`:

```python
class MappingFakeClient(ReportFakeClient):
    def __init__(self, *args, aggregate_reach, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.aggregate_reach = aggregate_reach

    def _get_instagram_aggregate_reach(self, *, ad_ids, time_range):
        return self.aggregate_reach[tuple(sorted(ad_ids))]
```

Define complete mapping fixtures in `test_paid_media_identity.py`:

```python
def make_identity_client(load_json, client_config, *, account_spend=110):
    payload = load_json("meta_ads/paid_media_identity.json")
    account_rows = tuple(payload["account_instagram"]["data"])
    aggregate_rows = payload["aggregate_reach"]["ad_1,ad_2"]["data"]
    instagram_reach = next(
        int(row["reach"])
        for row in aggregate_rows
        if row["publisher_platform"] == "instagram"
    )
    if account_spend != 110:
        changed = {**account_rows[0], "spend": str(account_spend)}
        account_rows = (changed,)
    return MappingFakeClient(
        client_config,
        groups={
            "account": AdsGroupResult(
                name="account", status=DatasetStatus.OK, rows=account_rows
            ),
            "campaigns": AdsGroupResult(
                name="campaigns", status=DatasetStatus.EMPTY
            ),
            "ads": AdsGroupResult(
                name="ads",
                status=DatasetStatus.OK,
                rows=tuple(payload["ads_instagram"]["data"]),
            ),
            "metadata": AdsGroupResult(
                name="metadata",
                status=DatasetStatus.OK,
                rows=tuple(payload["metadata"]["data"]),
            ),
        },
        account_context=AdAccountContext(
            ad_account_id="act_1",
            currency="USD",
            timezone_name="America/New_York",
        ),
        aggregate_reach={("ad_1", "ad_2"): (instagram_reach, None)},
    )


@pytest.fixture
def identity_client(load_json, client_config):
    return make_identity_client(load_json, client_config)


@pytest.fixture
def unreconciled_client(load_json, client_config):
    return make_identity_client(load_json, client_config, account_spend=111)


@pytest.fixture
def failed_reach_client(identity_client):
    issue = MetricIssue(
        endpoint="act_1/insights",
        request_group="media_1_reach",
        issue_type=IssueType.NETWORK,
        reason=IssueReason.ERROR,
        safe_message="O alcance agregado não ficou disponível.",
        can_display=True,
    )
    identity_client.aggregate_reach[("ad_1", "ad_2")] = (None, issue)
    return identity_client


@pytest.fixture
def partial_ad_delivery_client(identity_client):
    issue = MetricIssue(
        endpoint="act_1/insights",
        request_group="ads",
        issue_type=IssueType.PARTIAL_PAGINATION,
        reason=IssueReason.ERROR,
        safe_message="A entrega por anúncio ficou incompleta.",
        can_display=True,
    )
    current = identity_client.groups["ads"]
    identity_client.groups["ads"] = current.model_copy(
        update={
            "status": DatasetStatus.PARTIAL,
            "issues": (issue,),
            "truncated": True,
        }
    )
    return identity_client
```

Write these tests:

```python
def test_preserves_effective_and_source_ids_and_prefers_effective(identity_client):
    report = identity_client.get_paid_ads_report(platform_scope="instagram")

    ad_1 = next(item for item in report.creatives if item.ad_id == "ad_1")
    assert ad_1.effective_instagram_media_id == "media_1"
    assert ad_1.source_instagram_media_id == "source_old_1"
    assert report.by_instagram_media_id["media_1"].media_id_basis == "effective"
    assert report.by_instagram_media_id["media_2"].media_id_basis == "source"


def test_multi_ad_reach_uses_instagram_aggregate_or_none(identity_client):
    report = identity_client.get_paid_ads_report(platform_scope="instagram")

    media = report.by_instagram_media_id["media_1"]
    assert media.metrics.reach == 390
    assert media.metrics.reach != 470
    assert media.reach_deduplicated is True


def test_failed_aggregate_reach_never_falls_back_to_ad_sum(failed_reach_client):
    report = failed_reach_client.get_paid_ads_report(platform_scope="instagram")

    media = report.by_instagram_media_id["media_1"]
    assert media.metrics.reach is None
    assert media.metrics.reach != 470
    assert media.reach_deduplicated is None
    assert media.status is DatasetStatus.PARTIAL
    assert media.issues


def test_identity_coverage_reconciles_spend_and_states_basis(identity_client):
    report = identity_client.get_paid_ads_report(platform_scope="instagram")
    coverage = report.media_identity_coverage

    assert coverage is not None
    assert coverage.basis == "ad_delivery_spend_with_recoverable_instagram_media_id"
    assert coverage.account_total_spend == 110
    assert coverage.ad_delivery_spend == 110
    assert coverage.spend_reconciliation_delta == 0
    assert coverage.spend_reconciled is True
    assert coverage.spend_with_recoverable_instagram_media_id == 100
    assert coverage.spend_without_recoverable_instagram_media_id == 10
    assert coverage.coverage_pct == 100 / 110 * 100
    assert report.delivery_without_media_id == (
        PaidDeliveryWithoutMediaId(
            ad_id="ad_4",
            effective_instagram_media_id=None,
            source_instagram_media_id=None,
            spend=10,
            reason="instagram_media_id_missing",
        ),
    )


def test_unreconciled_spend_cannot_claim_percentage(unreconciled_client):
    report = unreconciled_client.get_paid_ads_report(platform_scope="instagram")
    coverage = report.media_identity_coverage

    assert coverage is not None
    assert coverage.spend_reconciled is False
    assert coverage.coverage_pct is None
    assert coverage.status is DatasetStatus.PARTIAL
    assert coverage.issues


def test_partial_ad_delivery_cannot_claim_percentage(partial_ad_delivery_client):
    report = partial_ad_delivery_client.get_paid_ads_report(
        platform_scope="instagram"
    )
    coverage = report.media_identity_coverage

    assert coverage is not None
    assert coverage.coverage_pct is None
    assert coverage.status is DatasetStatus.PARTIAL
    assert coverage.issues


def test_recoverable_media_absent_from_publication_selection_remains_in_report(identity_client):
    report = identity_client.get_paid_ads_report(platform_scope="instagram")

    assert "media_2" in report.by_instagram_media_id
    assert not hasattr(report.by_instagram_media_id["media_2"], "dark_post")
```

- [ ] **Verify RED — Run identity and coverage tests**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_paid_media_identity.py
```

- [ ] **GREEN — Implement identity grouping, unique reach, and spend reconciliation**

Choose `effective_instagram_media_id` when present; otherwise choose `source_instagram_media_id`. Preserve both originals on every creative. A summary is `effective` when every grouped ad used its effective ID, `source` when every grouped ad used its source ID, and `mixed` when both bases contributed to the same recovered ID. A recoverable ID remains in `by_instagram_media_id` even when the organic publication-window selection does not contain it; the later comparison/UI layer decides how to label or display it. Never call it a dark post here.

For one ad, use that ad row’s reach. For multiple ads attached to one ID, query account-level `reach` with `publisher_platform` breakdown and an `ad.id IN` filter; accept only the Instagram row. Failure yields `reach=None`, partial status, and no summed fallback.

Reconcile account totals against the sum of complete ad-delivery rows. Define `spend_reconciliation_delta = ad_delivery_spend - account_total_spend`; tolerance is `max(0.01, abs(account_total_spend) * 1e-6)`. Set `coverage_pct` only when account total exists, ad group is OK or EMPTY, every ad spend is complete, and the absolute delta is inside tolerance. The denominator is `ad_delivery_spend`, never selected publications.

For a contractual EMPTY report, all spend components and `coverage_pct` are `0.0`, `spend_reconciled=True`, and coverage status is EMPTY. For all-Meta, identity fields remain empty because an Instagram identity coverage claim is not meaningful across platforms.

- [ ] **REFACTOR — Enumerate mapping aggregation and issues**

Use `aggregate_paid_ads_metrics()` with explicit `deduplicated_reach`. Do not add reach, reuse API ratios, collapse raw rows, or calculate ROAS without an explicit action-value source. Attach incomplete additive, failed reach, and spend reconciliation issues to the media/coverage object and `PaidAdsReport.meta`.

- [ ] **Verify GREEN — Run the complete paid-Ads suite**

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api/test_meta_ads_raw_actions.py tests/unit/api/test_meta_ads_metrics.py tests/unit/api/test_meta_ads_transport.py tests/unit/api/test_meta_ads_context.py tests/unit/api/test_paid_ads_report.py tests/unit/api/test_paid_demographics.py tests/unit/api/test_paid_media_identity.py
ruff check src/dashboard/api/meta_client.py src/dashboard/api/meta_ads_parser.py src/dashboard/schemas/meta.py tests/unit/api
python -m compileall -q src/dashboard
git diff --check
```

- [ ] **Commit — Commit media identity coverage**

```bash
git add src/dashboard/schemas/meta.py src/dashboard/api/meta_client.py tests/unit/api/meta_ads_fakes.py tests/unit/api/test_paid_media_identity.py tests/fixtures/meta_ads/paid_media_identity.json
git commit -m "feat: reconcile paid Instagram media identity coverage"
```

---

## Integration Boundary

The UI/data-loader plan consumes only:

```python
MetaAdsClient.get_paid_ads_report(
    date_preset=date_preset,
    time_range=time_range,
    platform_scope="all_meta",
)
```

for the general Ads view and the same method with `platform_scope="instagram"` for content comparison. It consumes `get_paid_demographics_report()` for paid demographics. It must display coverage as “percentual do investimento em linhas de entrega com ID de mídia do Instagram recuperável”, not “publicações cobertas” or “dark posts”.

`PaidAdsReport` intentionally does not embed `PaidDemographicsReport`: the canonical data loader fetches both reports explicitly with the same `date_preset`, `time_range`, and `platform_scope`, keeps each report’s independent `DatasetMeta/status/issues`, and passes the pair to the Ads UI. No third demographics DTO or dictionary adapter may be introduced.

Only after every UI consumer migrates may the integration plan delete legacy `CampaignInsight.from_api_response()`, `get_campaign_insights()`, `get_creative_performance()`, `get_ads_reach_mapping()`, and `get_instagram_paid_totals()`.

## Final Verification

```bash
META_MASTER_TOKEN=test CLIENTS_JSON='[]' PYTHONPATH=src/dashboard python -m pytest -q tests/unit/api
ruff check src/dashboard/api/meta_client.py src/dashboard/api/meta_ads_parser.py src/dashboard/schemas/meta.py tests/unit/api
python -m compileall -q src/dashboard
git diff --check
```

Expected: all paid Ads unit tests pass; Ruff reports no violation in touched files; compileall succeeds; `git diff --check` prints nothing; no legacy method changed in this plan.
