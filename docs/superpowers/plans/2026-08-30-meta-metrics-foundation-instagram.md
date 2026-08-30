# Meta Metrics Foundation and Instagram v26 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build shared auditable metric contracts and typed Instagram Media, Account, Story, demographic, and comment reports without mixing organic, account-total, visible-object, or paid scopes.

**Architecture:** Shared Pydantic contracts carry scope, status, period, provenance, and structured issues at dataset/group level. Pure parsers consume sanitized Meta-shaped payloads; `InstagramClient` owns TLS-safe transport, bounded retry, pagination, batch isolation, and report assembly. Legacy mixed schemas remain only until the separate loader/UI migration consumes all typed reports; removal and live reconciliation are merge blockers.

**Tech Stack:** Python 3.11+, Pydantic v2, requests, pytest, Ruff.

**Spec:** [`docs/superpowers/specs/2026-08-30-meta-metric-contract-design.md`](../specs/2026-08-30-meta-metric-contract-design.md)

## Global Constraints

- Production uses Graph API `v26.0`; instance-level `api_version` remains injectable for v25/v26 probes.
- Only `comments`, `likes`, `views`, and `total_interactions` are `organic_media`.
- `reach`, `saved`, `shares`, and watch metrics remain `media_insights`.
- Object-edge counts and comments are `mixed_visible_count`; they never backfill organic metrics.
- Account `reach`, `accounts_engaged`, and `total_interactions` are `account_total_including_ads`.
- User Metrics are limited to the most recent 90 inclusive days; requested and effective windows remain distinct.
- Unique metrics are never summed across windows, media, or segments.
- `None` means unavailable. Zero is valid only for `ok` or valid `empty` responses.
- Valid empty never hides an error; `not_applicable` is non-blocking.
- TLS is enabled for every request. Tokens/raw bodies never enter fixtures, issues, logs, exceptions, or commits.
- Retry is bounded and applies only to network/transient/rate-limit failures.
- Every production change follows failing test → minimal implementation → passing test → focused commit.
- Normal CI excludes `live`; live reconciliation is a secret-backed merge gate.

## File Map

- Create `src/dashboard/schemas/metrics.py`.
- Create `src/dashboard/api/instagram_parsers.py`.
- Modify `src/dashboard/schemas/instagram.py`, `src/dashboard/api/exceptions.py`, and `src/dashboard/api/instagram_client.py`.
- Create `pytest.ini`, `tests/__init__.py`, `tests/fakes/__init__.py`, `tests/conftest.py`, `tests/fakes/meta_http.py`, sanitized `tests/fixtures/instagram/*.json`, and four unit-test modules.

## Public Interfaces

```text
InstagramClient(
    client_config,
    *,
    api_version: str = "v26.0",
    session: requests.Session | None = None,
    clock: Callable[[], datetime] = utc_now,
    sleeper: Callable[[float], None] = time.sleep,
    jitter: Callable[[float, float], float] = random.uniform,
)
InstagramClient.get_media_report(
    *, publication_since: date | None = None,
    publication_until: date | None = None,
    limit: int = 100,
) -> InstagramMediaReport
InstagramClient.get_active_story_report() -> InstagramStoryReport
InstagramClient.get_account_report(
    *, requested_since: date, requested_until: date
) -> InstagramAccountReport
InstagramClient.get_demographics_report() -> InstagramDemographicsReport
InstagramClient.get_media_comments(
    media_ids: tuple[str, ...]
) -> InstagramCommentReport
```

---

### Task 1: Test Bootstrap and Shared Metric Contracts

**Files:**
- Modify: `.gitignore`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/fakes/__init__.py`
- Create: `tests/fakes/meta_http.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/schemas/test_metrics.py`
- Create: `src/dashboard/schemas/metrics.py`
- Delete from Git index: the five tracked `*.pyc` paths below

**Interfaces:**
- Produces `MetricScope`, `DatasetStatus`, `PeriodBasis`, `IssueReason`, `IssueType`, `MetricIssue`, `PeriodWindow`, `DatasetMeta`, `ScopedMetricGroup[T]`, `status_from_values`, and `merge_statuses`.
- `DatasetMeta.metric_scope` is one scope or a `frozenset` of at least two scopes; never `None`.
- `PeriodWindow` and `DatasetMeta` both expose `requested_since`, `requested_until`, `effective_since`, and `effective_until`.

- [ ] **Step 1: Make tests and fixtures trackable**

Replace `.gitignore` with UTF-8 content:

```gitignore
fetch_*.py
push_*.py
gpt*.py
scratch/
temp_*.py
temp_*.txt
*.json
!tests/fixtures/**/*.json
take_screenshot.py
screenshot.png
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
```

Remove only generated artifacts:

```bash
git rm src/dashboard/api/__pycache__/meta_client.cpython-314.pyc
git rm src/dashboard/auth/__pycache__/oauth.cpython-314.pyc
git rm src/dashboard/core/__pycache__/config.cpython-314.pyc
git rm src/dashboard/ui/__pycache__/dashboard_view.cpython-314.pyc
git rm src/dashboard/ui/__pycache__/styles.cpython-314.pyc
```

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = src/dashboard
addopts = --strict-markers -m "not live"
markers =
    live: calls real Meta APIs; normal CI excludes it
```

- [ ] **Step 2: Create deterministic HTTP fakes**

Create empty `tests/__init__.py` and `tests/fakes/__init__.py` so the project-local `tests.fakes` package cannot be shadowed by an installed package.

Create `tests/fakes/meta_http.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass(frozen=True)
class RecordedCall:
    method: str
    url: str
    params: dict[str, Any]
    data: dict[str, Any]
    kwargs: dict[str, Any]


@dataclass
class FakeResponse:
    payload: Any
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}", response=self  # type: ignore[arg-type]
            )


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.verify = True
        self.headers: dict[str, str] = {}
        self.responses = list(responses or [])
        self.calls: list[RecordedCall] = []
        self.batch_requests: list[dict[str, Any]] = []

    def queue(self, *responses: FakeResponse) -> None:
        self.responses.extend(responses)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> FakeResponse:
        params_copy, data_copy = dict(params or {}), dict(data or {})
        self.calls.append(
            RecordedCall(method, url, params_copy, data_copy, dict(kwargs))
        )
        if method == "POST" and "batch" in data_copy:
            self.batch_requests.extend(json.loads(data_copy["batch"]))
        if not self.responses:
            raise AssertionError(f"No fake response queued for {method} {url}")
        return self.responses.pop(0)

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._request("POST", url, **kwargs)
```

Create `tests/conftest.py`:

```python
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from tests.fakes.meta_http import FakeResponse, FakeSession

os.environ.setdefault("META_MASTER_TOKEN", "test-token")
os.environ.setdefault("CLIENTS_JSON", "[]")

from core.config import ClientConfig  # noqa: E402


@pytest.fixture
def client_config() -> ClientConfig:
    return ClientConfig(
        name="Fixture Client",
        ad_account_id="act_1",
        page_id="page-1",
        token="test-token",
    )


@pytest.fixture
def load_json() -> Callable[[str], Any]:
    def load(relative_path: str) -> Any:
        path = Path("tests/fixtures") / relative_path
        return json.loads(path.read_text(encoding="utf-8"))

    return load


@pytest.fixture
def today() -> date:
    return date(2026, 8, 30)


@pytest.fixture
def aware_now() -> datetime:
    return datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session_with_account() -> FakeSession:
    return FakeSession(
        [FakeResponse({"instagram_business_account": {"id": "ig-user-1"}})]
    )


@pytest.fixture
def client_factory(client_config, aware_now):
    def build(*responses: FakeResponse, api_version: str = "v26.0"):
        from api.instagram_client import InstagramClient

        session = FakeSession([
            FakeResponse({"instagram_business_account": {"id": "ig-user-1"}}),
            *responses,
        ])
        client = InstagramClient(
            client_config,
            api_version=api_version,
            session=session,
            clock=lambda: aware_now,
            sleeper=lambda _: None,
            jitter=lambda _low, _high: 0.0,
        )
        return client, session

    return build
```

- [ ] **Step 3: Write failing contract tests**

Create `tests/unit/schemas/test_metrics.py`:

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.metrics import (
    DatasetMeta, DatasetStatus, IssueReason, IssueType, MetricIssue,
    MetricScope, PeriodBasis, PeriodWindow, merge_statuses,
    status_from_values,
)


def issue(reason: IssueReason) -> MetricIssue:
    return MetricIssue(
        endpoint="ig-user-1/insights",
        request_group="organic",
        issue_type=IssueType.UNSUPPORTED_METRIC,
        reason=reason,
        safe_message="Sanitized fixture issue",
        metric_name="views",
    )


def test_zero_is_ok_not_missing() -> None:
    assert status_from_values({"reach": 0}, ()) is DatasetStatus.OK


def test_not_applicable_does_not_degrade_complete_payload() -> None:
    assert status_from_values(
        {"likes": 0}, (issue(IssueReason.NOT_APPLICABLE),)
    ) is DatasetStatus.OK


def test_empty_with_error_is_unavailable() -> None:
    assert status_from_values(
        {}, (issue(IssueReason.ERROR),), source_empty=True
    ) is DatasetStatus.UNAVAILABLE


def test_missing_and_partial_remain_distinct() -> None:
    assert status_from_values(
        {"likes": None}, (issue(IssueReason.NOT_RETURNED),)
    ) is DatasetStatus.UNAVAILABLE
    assert status_from_values(
        {"likes": 1, "comments": None}, (issue(IssueReason.NOT_RETURNED),)
    ) is DatasetStatus.PARTIAL


def test_valid_empty_and_ok_plus_empty_are_not_failures() -> None:
    assert status_from_values({}, (), source_empty=True) is DatasetStatus.EMPTY
    assert merge_statuses(
        (DatasetStatus.OK, DatasetStatus.EMPTY)
    ) is DatasetStatus.OK


def test_multi_scope_requires_two_scopes_and_aware_time() -> None:
    common = dict(
        source_endpoint="ig-user-1/media; media-id/insights",
        api_version="v26.0",
        status=DatasetStatus.OK,
        period_basis=PeriodBasis.MEDIA_LIFETIME_SNAPSHOT,
        retrieved_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    meta = DatasetMeta(
        **common,
        metric_scope=frozenset({
            MetricScope.ORGANIC_MEDIA, MetricScope.MEDIA_INSIGHTS
        }),
    )
    assert isinstance(meta.metric_scope, frozenset)
    with pytest.raises(ValidationError):
        DatasetMeta(
            **common,
            metric_scope=frozenset({MetricScope.ORGANIC_MEDIA}),
        )
    with pytest.raises(ValidationError):
        DatasetMeta(
            **{**common, "retrieved_at": datetime(2026, 8, 30, 12)},
            metric_scope=MetricScope.ORGANIC_MEDIA,
        )


def test_period_window_preserves_requested_and_effective_dates() -> None:
    window = PeriodWindow(
        requested_since=None,
        requested_until=None,
        effective_since=None,
        effective_until=None,
        basis=PeriodBasis.PUBLICATION_WINDOW,
    )
    assert window.requested_since is None
    assert window.effective_since is None
```

- [ ] **Step 4: Confirm expected failure**

```bash
python -m pytest -q tests/unit/schemas/test_metrics.py
```

Expected: `ModuleNotFoundError: No module named 'schemas.metrics'`.

- [ ] **Step 5: Implement shared contracts**

Create `src/dashboard/schemas/metrics.py`:

```python
from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class MetricScope(StrEnum):
    ORGANIC_MEDIA = "organic_media"
    MEDIA_INSIGHTS = "media_insights"
    ACCOUNT_TOTAL_INCLUDING_ADS = "account_total_including_ads"
    PAID_ADS = "paid_ads"
    MIXED_VISIBLE_COUNT = "mixed_visible_count"


class DatasetStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    EMPTY = "empty"


class PeriodBasis(StrEnum):
    PUBLICATION_WINDOW = "publication_window"
    MEDIA_LIFETIME_SNAPSHOT = "media_lifetime_snapshot"
    ACCOUNT_MEASUREMENT_WINDOW = "account_measurement_window"
    AD_DELIVERY_WINDOW = "ad_delivery_window"
    ACTIVE_STORY_WINDOW = "active_story_window"


class IssueReason(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_RETURNED = "not_returned"
    PERMISSION_DENIED = "permission_denied"
    DEPRECATED = "deprecated"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class IssueType(StrEnum):
    PERMISSION = "permission"
    UNSUPPORTED_METRIC = "unsupported_metric"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    PARSE = "parse"
    PARTIAL_PAGINATION = "partial_pagination"
    NOT_AGGREGABLE = "not_aggregable"


class MetricIssue(BaseModel):
    model_config = ConfigDict(frozen=True)
    endpoint: str
    issue_type: IssueType
    reason: IssueReason
    safe_message: str
    request_group: str | None = None
    metric_name: str | None = None
    code: int | None = None
    error_subcode: int | None = None
    fbtrace_id: str | None = None
    usage_headers: dict[str, str] = Field(default_factory=dict)
    can_display: bool = False


class PeriodWindow(BaseModel):
    model_config = ConfigDict(frozen=True)
    requested_since: date | None = None
    requested_until: date | None = None
    effective_since: date | None = None
    effective_until: date | None = None
    basis: PeriodBasis


ScopeValue = MetricScope | frozenset[MetricScope]


class DatasetMeta(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_endpoint: str
    api_version: str
    metric_scope: ScopeValue
    platform_scope: str | frozenset[str] | None = None
    status: DatasetStatus
    requested_since: date | None = None
    requested_until: date | None = None
    effective_since: date | None = None
    effective_until: date | None = None
    period_basis: PeriodBasis
    retrieved_at: AwareDatetime
    timezone: str | None = None
    currency: str | None = None
    truncated: bool = False
    issues: tuple[MetricIssue, ...] = ()

    @field_validator("metric_scope")
    @classmethod
    def validate_scope(cls, value: ScopeValue) -> ScopeValue:
        if isinstance(value, frozenset) and len(value) < 2:
            raise ValueError("multi-scope metadata requires at least two scopes")
        return value


class ScopedMetricGroup(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)
    metrics: T
    scope: MetricScope
    status: DatasetStatus
    issues: tuple[MetricIssue, ...] = ()


def status_from_values(
    values: Mapping[str, object | None],
    issues: Sequence[MetricIssue],
    *,
    source_empty: bool = False,
) -> DatasetStatus:
    blocking = tuple(
        row for row in issues if row.reason is not IssueReason.NOT_APPLICABLE
    )
    if source_empty:
        return DatasetStatus.EMPTY if not blocking else DatasetStatus.UNAVAILABLE
    if not values:
        return DatasetStatus.UNAVAILABLE if blocking else DatasetStatus.EMPTY
    present = tuple(value is not None for value in values.values())
    if all(present) and not blocking:
        return DatasetStatus.OK
    if any(present):
        return DatasetStatus.PARTIAL
    return DatasetStatus.UNAVAILABLE


def merge_statuses(statuses: Sequence[DatasetStatus]) -> DatasetStatus:
    non_empty = tuple(row for row in statuses if row is not DatasetStatus.EMPTY)
    if not non_empty:
        return DatasetStatus.EMPTY
    if all(row is DatasetStatus.OK for row in non_empty):
        return DatasetStatus.OK
    if all(row is DatasetStatus.UNAVAILABLE for row in non_empty):
        return DatasetStatus.UNAVAILABLE
    return DatasetStatus.PARTIAL
```

- [ ] **Step 6: Verify and commit Task 1**

```bash
python -m pytest -q tests/unit/schemas/test_metrics.py
ruff check src/dashboard/schemas/metrics.py tests/fakes/meta_http.py tests/conftest.py tests/unit/schemas/test_metrics.py
git add .gitignore pytest.ini tests/__init__.py tests/fakes/__init__.py tests/fakes/meta_http.py tests/conftest.py tests/unit/schemas/test_metrics.py src/dashboard/schemas/metrics.py
git commit -m "feat: add auditable metric contracts"
```

The `git rm` deletions are already staged. Do not run `git add src/dashboard`.

---

### Task 2: Safe Structured Meta Errors

**Files:**
- Modify: `src/dashboard/api/exceptions.py:6-16`
- Create: `tests/unit/api/test_exceptions.py`

**Interfaces:**
- Produces `MetaAPIError(safe_message, *, issue=None, status_code=None, retryable=False)`; subclasses remain compatible.

- [ ] **Step 1: Write the failing test**

```python
from api.exceptions import MetaAPIError
from schemas.metrics import IssueReason, IssueType, MetricIssue


def test_meta_error_exposes_only_safe_structured_data() -> None:
    issue = MetricIssue(
        endpoint="act-1/insights",
        issue_type=IssueType.PERMISSION,
        reason=IssueReason.PERMISSION_DENIED,
        safe_message="Permission denied",
        code=200,
        error_subcode=33,
        fbtrace_id="trace-1",
    )
    error = MetaAPIError(
        "Meta permission is missing",
        issue=issue,
        status_code=403,
        retryable=False,
    )
    assert str(error) == "Meta permission is missing"
    assert error.issue == issue
    assert "test-token" not in repr(error)
```

- [ ] **Step 2: Confirm failure**

```bash
python -m pytest -q tests/unit/api/test_exceptions.py
```

Expected: constructor rejects structured fields.

- [ ] **Step 3: Replace exception definitions**

```python
from schemas.metrics import MetricIssue


class MetaAPIError(Exception):
    def __init__(
        self,
        safe_message: str,
        *,
        issue: MetricIssue | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.issue = issue
        self.status_code = status_code
        self.retryable = retryable

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(safe_message={self.safe_message!r}, "
            f"status_code={self.status_code!r}, retryable={self.retryable!r})"
        )


class InstagramAPIError(MetaAPIError):
    pass


class MetaAdsAPIError(MetaAPIError):
    pass
```

- [ ] **Step 4: Verify and commit Task 2**

```bash
python -m pytest -q tests/unit/api/test_exceptions.py
ruff check src/dashboard/api/exceptions.py tests/unit/api/test_exceptions.py
git add src/dashboard/api/exceptions.py tests/unit/api/test_exceptions.py
git commit -m "feat: preserve safe Meta error diagnostics"
```

### Task 3: Typed Instagram Media Schemas and Meta-Shaped Parser

**Files:**
- Modify: `src/dashboard/schemas/instagram.py:1-82`
- Create: `src/dashboard/api/instagram_parsers.py`
- Create: `tests/unit/api/test_instagram_parsers.py`
- Create: `tests/fixtures/instagram/media_insights_image.json`
- Create: `tests/fixtures/instagram/media_insights_total_only.json`
- Create: `tests/fixtures/instagram/media_insights_video_views_only.json`
- Create: `tests/fixtures/instagram/media_insights_reel.json`

**Interfaces:**
- Produces `MediaIdentity`, `OrganicMediaMetrics`, `MediaInsightMetrics`, `VisibleMediaCounters`, `InstagramMediaItem`, `InstagramMediaReport`.
- Produces `media_request_groups(media_payload)` and `parse_media_item(media_payload, insight_groups, group_issues=())`.
- Leaves legacy `InstagramMedia` temporarily; the loader/UI plan removes it before merge.

- [ ] **Step 1: Create raw Meta-shaped fixtures**

`media_insights_image.json`:

```json
{
  "media": {
    "id": "ig-image-1", "caption": "Sanitized image",
    "timestamp": "2026-08-01T12:00:00+0000", "media_type": "IMAGE",
    "media_product_type": "FEED", "like_count": 99, "comments_count": 7,
    "permalink": "https://www.instagram.com/p/sanitized/"
  },
  "groups": {
    "organic": {"data": [
      {"name": "likes", "period": "lifetime", "values": [{"value": 12}]},
      {"name": "comments", "period": "lifetime", "values": [{"value": 2}]},
      {"name": "total_interactions", "period": "lifetime", "values": [{"value": 18}]}
    ]},
    "media_insights": {"data": [
      {"name": "reach", "period": "lifetime", "values": [{"value": 100}]},
      {"name": "saved", "period": "lifetime", "values": [{"value": 3}]},
      {"name": "shares", "period": "lifetime", "values": [{"value": 1}]}
    ]}
  }
}
```

`media_insights_total_only.json`:

```json
{"data": [
  {"name": "total_likes", "period": "lifetime", "values": [{"value": 44}]},
  {"name": "total_comments", "period": "lifetime", "values": [{"value": 8}]},
  {"name": "total_views", "period": "lifetime", "values": [{"value": 90}]}
]}
```

`media_insights_video_views_only.json`:

```json
{
  "media": {"id": "ig-video-1", "media_type": "VIDEO", "media_product_type": "FEED"},
  "groups": {"organic": {"data": [
    {"name": "video_views", "period": "lifetime", "values": [{"value": 55}]}
  ]}}
}
```

`media_insights_reel.json`:

```json
{
  "media": {"id": "ig-reel-1", "media_type": "VIDEO", "media_product_type": "REELS"},
  "groups": {
    "organic": {"data": [
      {"name": "likes", "values": [{"value": 10}]},
      {"name": "comments", "values": [{"value": 1}]},
      {"name": "views", "values": [{"value": 80}]},
      {"name": "total_interactions", "values": [{"value": 13}]}
    ]},
    "media_insights": {"data": [
      {"name": "reach", "values": [{"value": 60}]},
      {"name": "saved", "values": [{"value": 1}]},
      {"name": "shares", "values": [{"value": 1}]}
    ]},
    "watch": {"data": [
      {"name": "ig_reels_video_view_total_time", "values": [{"value": 120000}]},
      {"name": "ig_reels_avg_watch_time", "values": [{"value": 1500}]}
    ]}
  }
}
```

- [ ] **Step 2: Write failing parser tests**

Create `tests/unit/api/test_instagram_parsers.py`:

```python
import json
from pathlib import Path

from api.instagram_parsers import media_request_groups, parse_media_item
from schemas.metrics import DatasetStatus, IssueReason, MetricScope

FIXTURES = Path("tests/fixtures/instagram")


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_documented_media_interactions_are_organic() -> None:
    payload = load("media_insights_image.json")
    item = parse_media_item(payload["media"], payload["groups"])
    assert item.organic.metrics.model_dump() == {
        "comments": 2, "likes": 12, "views": None,
        "total_interactions": 18,
    }
    assert item.organic.scope is MetricScope.ORGANIC_MEDIA
    assert item.organic.status is DatasetStatus.OK
    assert item.media_insights.metrics.reach == 100


def test_total_metrics_never_backfill_organic_fields() -> None:
    image = load("media_insights_image.json")["media"]
    item = parse_media_item(
        image, {"organic": load("media_insights_total_only.json")}
    )
    assert item.organic.metrics.likes is None
    assert item.organic.metrics.comments is None
    assert item.organic.metrics.views is None
    assert any(
        row.metric_name == "total_likes"
        and row.reason is IssueReason.NOT_APPLICABLE
        for row in item.organic.issues
    )


def test_visible_counts_never_fill_missing_organic_metrics() -> None:
    item = parse_media_item(
        {"id": "ig-media-1", "like_count": 99, "comments_count": 7}, {}
    )
    assert item.organic.metrics.likes is None
    assert item.organic.status is DatasetStatus.UNAVAILABLE
    assert item.visible_counters.metrics.like_count == 99
    assert item.visible_counters.scope is MetricScope.MIXED_VISIBLE_COUNT


def test_video_views_is_not_a_views_fallback() -> None:
    payload = load("media_insights_video_views_only.json")
    item = parse_media_item(payload["media"], payload["groups"])
    assert item.organic.metrics.views is None
    assert any(
        row.metric_name == "views" and row.reason is IssueReason.NOT_RETURNED
        for row in item.organic.issues
    )


def test_request_groups_use_real_media_type_values() -> None:
    carousel = media_request_groups(
        {"media_type": "CAROUSEL_ALBUM", "media_product_type": "FEED"}
    )
    reel = media_request_groups(
        {"media_type": "VIDEO", "media_product_type": "REELS"}
    )
    assert "views" not in carousel["organic"]
    assert reel["organic"] == (
        "comments", "likes", "views", "total_interactions"
    )
    assert reel["watch"] == (
        "ig_reels_video_view_total_time", "ig_reels_avg_watch_time"
    )
```

- [ ] **Step 3: Confirm failure**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py
```

Expected: collection fails because new parser/schemas do not exist.

- [ ] **Step 4: Add exact media schemas**

Add to `schemas/instagram.py`:

```python
from datetime import datetime

from schemas.metrics import DatasetMeta, PeriodWindow, ScopedMetricGroup


class MediaIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    caption: str = ""
    media_url: str | None = None
    thumbnail_url: str | None = None
    permalink: str = ""
    timestamp: datetime | None = None
    media_type: str = ""
    media_product_type: str = ""


class OrganicMediaMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    comments: int | None = None
    likes: int | None = None
    views: int | None = None
    total_interactions: int | None = None


class MediaInsightMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    reach: int | None = None
    saved: int | None = None
    shares: int | None = None
    ig_reels_video_view_total_time: float | None = None
    ig_reels_avg_watch_time: float | None = None


class VisibleMediaCounters(BaseModel):
    model_config = ConfigDict(frozen=True)
    like_count: int | None = None
    comments_count: int | None = None


class InstagramMediaItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    identity: MediaIdentity
    organic: ScopedMetricGroup[OrganicMediaMetrics]
    media_insights: ScopedMetricGroup[MediaInsightMetrics]
    visible_counters: ScopedMetricGroup[VisibleMediaCounters]


class InstagramMediaReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[InstagramMediaItem, ...]
    meta: DatasetMeta
    publication_selection: PeriodWindow
    measurement_note: str
```

- [ ] **Step 5: Implement parser primitives and fixed signature**

Create `instagram_parsers.py` with:

```python
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from schemas.instagram import (
    InstagramMediaItem, MediaIdentity, MediaInsightMetrics,
    OrganicMediaMetrics, VisibleMediaCounters,
)
from schemas.metrics import (
    IssueReason, IssueType, MetricIssue, MetricScope,
    ScopedMetricGroup, status_from_values,
)

TOTAL_METRICS = frozenset({"total_likes", "total_comments", "total_views"})


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _graph_values(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in (payload or {}).get("data", []):
        name, values = row.get("name"), row.get("values") or []
        if isinstance(name, str) and values:
            result[name] = values[0].get("value")
        elif isinstance(name, str) and "value" in row.get("total_value", {}):
            result[name] = row["total_value"]["value"]
    return result


def _missing_issue(metric: str, group: str) -> MetricIssue:
    return MetricIssue(
        endpoint="media-id/insights", request_group=group,
        issue_type=IssueType.UNSUPPORTED_METRIC,
        reason=IssueReason.NOT_RETURNED,
        safe_message=f"{metric} was not returned for this media",
        metric_name=metric, can_display=True,
    )


def media_request_groups(media_payload: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    is_video = (
        media_payload.get("media_type") == "VIDEO"
        or media_payload.get("media_product_type") == "REELS"
    )
    groups = {
        "organic": (
            ("comments", "likes", "views", "total_interactions")
            if is_video else ("comments", "likes", "total_interactions")
        ),
        "media_insights": ("reach", "saved", "shares"),
    }
    if media_payload.get("media_product_type") == "REELS":
        groups["watch"] = (
            "ig_reels_video_view_total_time", "ig_reels_avg_watch_time"
        )
    return groups
```

Implement `parse_media_item(media_payload, insight_groups, group_issues=())` with these exact rules:

1. Call `_graph_values` separately for `organic`, `media_insights`, and `watch`; never inspect `video_views`.
2. Generate `NOT_RETURNED` for every requested metric missing from its group.
3. Generate non-blocking `NOT_APPLICABLE` for IMAGE `views`, non-Reel watch fields, and every returned `total_*` field.
4. Build `OrganicMediaMetrics` only from `comments/likes/views/total_interactions`; `MediaInsightMetrics` only from its seven named fields; object counts only from the media edge.
5. Call `status_from_values` using only metrics requested for that media type. Pass client issues to the matching `request_group`.
6. Parse identity timestamp with `_parse_datetime`. Return one `InstagramMediaItem`; never copy one group into another.

- [ ] **Step 6: Verify and commit Task 3**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py
ruff check src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py tests/unit/api/test_instagram_parsers.py
git add src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py tests/unit/api/test_instagram_parsers.py tests/fixtures/instagram/media_insights_image.json tests/fixtures/instagram/media_insights_total_only.json tests/fixtures/instagram/media_insights_video_views_only.json tests/fixtures/instagram/media_insights_reel.json
git commit -m "feat: classify Instagram media metrics by source"
```

### Task 4: TLS-Safe Transport, Pagination, Batch Isolation, and Media Report

**Files:**
- Modify: `src/dashboard/api/instagram_client.py:1-288`
- Create: `tests/unit/api/test_instagram_client.py`
- Create: `tests/fixtures/instagram/batch_partial.json`

**Interfaces:**
- Produces the injectable constructor and `get_media_report` from Public Interfaces.
- Internal types/helpers: `BatchCall`, `BatchOutcome`, `_make_request`, `_paginate`, `_run_batch`, `_issue_from_graph_error`.

- [ ] **Step 1: Create the exact batch fixture**

`batch_partial.json`:

```json
[
  {"code": 200, "body": "{\"data\":[{\"name\":\"likes\",\"values\":[{\"value\":2}]}]}"},
  {"code": 200, "body": "{\"data\":[]}"},
  {"code": 400, "body": "{\"error\":{\"message\":\"Unsupported metric\",\"code\":100,\"error_subcode\":2108006,\"fbtrace_id\":\"trace-batch-2\"}}"},
  {"code": 200, "body": "{\"data\":[]}"}
]
```

- [ ] **Step 2: Write executable failing transport tests**

Create `tests/unit/api/test_instagram_client.py`:

```python
import json
from datetime import timedelta
from pathlib import Path

import pytest
import requests

from api.exceptions import InstagramAPIError
from schemas.metrics import DatasetStatus, IssueType, MetricScope, PeriodBasis
from tests.fakes.meta_http import FakeResponse

FIXTURES = Path("tests/fixtures/instagram")


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_tls_is_enabled(client_config, session_with_account, aware_now) -> None:
    from api.instagram_client import InstagramClient

    session_with_account.queue(FakeResponse({"data": []}))
    client = InstagramClient(
        client_config, session=session_with_account, clock=lambda: aware_now
    )
    client._make_request("ig-user-1/media", {"limit": "1"})
    assert session_with_account.verify is True
    assert all(
        call.kwargs.get("verify") is not False
        for call in session_with_account.calls
    )


def test_permission_error_preserves_diagnostics_without_raw_message(
    client_factory,
) -> None:
    response = FakeResponse(
        {"error": {
            "message": "Permissions error test-token", "code": 200,
            "error_subcode": 33, "fbtrace_id": "trace-permission",
        }},
        status_code=403,
        headers={"X-App-Usage": "{\"call_count\":10}"},
    )
    client, _session = client_factory(response)
    with pytest.raises(InstagramAPIError) as caught:
        client._make_request("ig-user-1/insights")
    error = caught.value
    assert error.issue.code == 200
    assert error.issue.error_subcode == 33
    assert error.issue.fbtrace_id == "trace-permission"
    assert "X-App-Usage" in error.issue.usage_headers
    assert "test-token" not in str(error)
    assert "test-token" not in repr(error)
    assert error.retryable is False


def test_rate_limit_retries_then_succeeds(client_factory) -> None:
    limited = FakeResponse(
        {"error": {"message": "Rate limit", "code": 4}}, status_code=429
    )
    client, session = client_factory(limited, FakeResponse({"data": []}))
    assert client._make_request("ig-user-1/media") == {"data": []}
    calls = [row for row in session.calls if row.url.endswith("/ig-user-1/media")]
    assert len(calls) == 2


def test_non_transient_400_is_not_retried(client_factory) -> None:
    invalid = FakeResponse(
        {"error": {"message": "Invalid metric", "code": 100}},
        status_code=400,
    )
    client, session = client_factory(invalid)
    with pytest.raises(InstagramAPIError):
        client._make_request("ig-user-1/insights")
    calls = [row for row in session.calls if row.url.endswith("/ig-user-1/insights")]
    assert len(calls) == 1


def test_tls_error_is_not_retried(client_factory) -> None:
    client, session = client_factory()
    session.responses.clear()

    def fail_tls(*_args, **_kwargs):
        raise requests.exceptions.SSLError("certificate failed")

    session.get = fail_tls
    with pytest.raises(InstagramAPIError) as caught:
        client._make_request("ig-user-1/media")
    assert caught.value.retryable is False


def test_repeated_cursor_marks_media_report_partial(client_factory) -> None:
    page_one = FakeResponse({
        "data": [{"id": "ig-media-1", "media_type": "IMAGE"}],
        "paging": {"cursors": {"after": "cursor-a"}},
    })
    page_two = FakeResponse({
        "data": [{"id": "ig-media-2", "media_type": "IMAGE"}],
        "paging": {"cursors": {"after": "cursor-a"}},
    })
    batch = FakeResponse([
        {"code": 200, "body": "{\"data\":[]}"},
        {"code": 200, "body": "{\"data\":[]}"},
        {"code": 200, "body": "{\"data\":[]}"},
        {"code": 200, "body": "{\"data\":[]}"}
    ])
    client, _session = client_factory(page_one, page_two, batch)
    report = client.get_media_report()
    assert report.meta.status is DatasetStatus.PARTIAL
    assert report.meta.truncated is True
    assert any(
        row.issue_type is IssueType.PARTIAL_PAGINATION
        for row in report.meta.issues
    )


def test_failed_batch_subrequest_marks_only_its_item(client_factory) -> None:
    media = FakeResponse({"data": [
        {"id": "ig-media-1", "media_type": "IMAGE"},
        {"id": "ig-media-2", "media_type": "IMAGE"}
    ]})
    client, _session = client_factory(
        media, FakeResponse(load("batch_partial.json"))
    )
    report = client.get_media_report()
    assert report.items[0].organic.metrics.likes == 2
    assert report.items[1].organic.metrics.likes is None
    assert report.items[1].organic.status is DatasetStatus.UNAVAILABLE
    assert report.meta.status is DatasetStatus.PARTIAL


def test_publication_window_is_not_measurement_window(client_factory, today) -> None:
    client, _session = client_factory(FakeResponse({"data": []}))
    since = today - timedelta(days=29)
    report = client.get_media_report(
        publication_since=since, publication_until=today
    )
    assert report.publication_selection.requested_since == since
    assert report.publication_selection.requested_until == today
    assert report.publication_selection.effective_since == since
    assert report.publication_selection.effective_until == today
    assert report.meta.requested_since is None
    assert report.meta.effective_since is None
    assert report.meta.period_basis is PeriodBasis.MEDIA_LIFETIME_SNAPSHOT
    assert report.meta.metric_scope == frozenset({
        MetricScope.ORGANIC_MEDIA,
        MetricScope.MEDIA_INSIGHTS,
        MetricScope.MIXED_VISIBLE_COUNT,
    })
```

- [ ] **Step 3: Confirm failures**

```bash
python -m pytest -q tests/unit/api/test_instagram_client.py
```

- [ ] **Step 4: Implement exact transport primitives**

Add above `InstagramClient`:

```python
from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BatchCall:
    key: str
    endpoint: str
    params: dict[str, str]
    request_group: str


@dataclass(frozen=True)
class BatchOutcome:
    payload: dict[str, Any] | None
    issue: MetricIssue | None
```

Set `self.api_version`, `self.base_url`, injected `session/clock/sleeper/jitter`, and `self.session.verify = True`. Remove every `verify=False` in `instagram_client.py`.

Use these exact classifications:

```python
RETRY_HTTP = frozenset({429, 500, 502, 503, 504})
RETRY_GRAPH = frozenset({1, 2, 4, 17, 32, 613})
NON_RETRY_GRAPH = frozenset({10, 100, 200, 299})
USAGE_HEADERS = (
    "X-App-Usage", "X-Page-Usage", "X-Business-Use-Case-Usage"
)
MAX_ATTEMPTS = 3
```

`_make_request` retries timeout/connection, `RETRY_HTTP`, and `RETRY_GRAPH` at most three attempts with `min(2**attempt + jitter(0, 1), 8)`. It never retries `SSLError`, permission, or invalid query. `_issue_from_graph_error` stores only code/subcode/fbtrace and the three usage headers; its safe messages are fixed category strings and never copy `error.message`/body.

`_paginate(endpoint, params)` returns `(items, issues, truncated)`, follows only `paging.cursors.after`, tracks `seen_cursors`, and emits `PARTIAL_PAGINATION` on repeats/failure after data.

`_run_batch(calls)` serializes `/{self.api_version}/{endpoint}?{urlencode(params)}`, processes every subresponse independently even when the envelope is 200, and returns one `BatchOutcome` per `BatchCall.key`.

- [ ] **Step 5: Implement exact media report assembly**

Build calls from `media_request_groups`; IMAGE/CAROUSEL_ALBUM gets organic+media, REELS also watch. Never retry a failed group with narrower metrics.

```text
groups = tuple(
    group
    for item in items
    for group in (item.organic, item.media_insights, item.visible_counters)
)
all_issues = tuple(pagination_issues) + tuple(
    issue for group in groups for issue in group.issues
)
status = (
    DatasetStatus.UNAVAILABLE
    if truncated and not items
    else DatasetStatus.PARTIAL
    if truncated
    else merge_statuses(tuple(group.status for group in groups))
)
return InstagramMediaReport(
    items=tuple(items),
    meta=DatasetMeta(
        source_endpoint=f"{self.instagram_account_id}/media; media-id/insights",
        api_version=self.api_version,
        metric_scope=frozenset({
            MetricScope.ORGANIC_MEDIA,
            MetricScope.MEDIA_INSIGHTS,
            MetricScope.MIXED_VISIBLE_COUNT,
        }),
        status=status,
        period_basis=PeriodBasis.MEDIA_LIFETIME_SNAPSHOT,
        retrieved_at=self.clock(),
        timezone="UTC",
        truncated=truncated,
        issues=all_issues,
    ),
    publication_selection=PeriodWindow(
        requested_since=publication_since,
        requested_until=publication_until,
        effective_since=publication_since,
        effective_until=publication_until,
        basis=PeriodBasis.PUBLICATION_WINDOW,
    ),
    measurement_note=(
        "Media Insights is a lifetime snapshot at retrieval; the date filter "
        "selects publications and does not bound metric measurement."
    ),
)
```

If `items` is empty and pagination succeeded, status is `EMPTY`; if pagination failed before items, status is `UNAVAILABLE` and `truncated=True`.

- [ ] **Step 6: Verify and commit Task 4**

```bash
python -m pytest -q tests/unit/api/test_instagram_client.py tests/unit/api/test_instagram_parsers.py
ruff check src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_client.py
git add src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_client.py tests/fixtures/instagram/batch_partial.json
git commit -m "feat: return typed Instagram media reports"
```

### Task 5: Story Navigation v26 with Independent Group Status

**Files:**
- Modify: `src/dashboard/schemas/instagram.py`
- Modify: `src/dashboard/api/instagram_parsers.py`
- Modify: `src/dashboard/api/instagram_client.py`
- Modify: `tests/unit/api/test_instagram_parsers.py`
- Modify: `tests/unit/api/test_instagram_client.py`
- Create: `tests/fixtures/instagram/story_navigation.json`

**Interfaces:**
- Produces `StoryCoreMetrics`, `StoryNavigationMetrics`, `InstagramStoryItem`, `InstagramStoryReport`, `parse_story_navigation`, `parse_story_item`, and `get_active_story_report`.

- [ ] **Step 1: Create the v26 breakdown fixture**

`story_navigation.json`:

```json
{"data": [{
  "name": "navigation", "period": "lifetime",
  "total_value": {"breakdowns": [{
    "dimension_keys": ["story_navigation_action_type"],
    "results": [
      {"dimension_values": ["TAP_BACK"], "value": 1},
      {"dimension_values": ["tap_exit"], "value": 2},
      {"dimension_values": ["Tap_Forward"], "value": 4},
      {"dimension_values": ["SWIPE_FORWARD"], "value": 3}
    ]
  }]}
}]}
```

- [ ] **Step 2: Write failing Story tests**

Append to parser tests:

```python
from api.instagram_parsers import parse_story_navigation


def test_story_navigation_parses_breakdown_case_insensitively() -> None:
    parsed = parse_story_navigation(load("story_navigation.json"))
    assert parsed.model_dump() == {
        "tap_back": 1, "tap_exit": 2,
        "tap_forward": 4, "swipe_forward": 3,
    }
```

Append to client tests:

```python
def test_story_uses_separate_core_and_navigation_requests(client_factory) -> None:
    stories = FakeResponse({"data": [{"id": "story-1"}]})
    batch = FakeResponse([
        {"code": 200, "body": "{\"data\":[{\"name\":\"reach\",\"values\":[{\"value\":10}]}]}"},
        {"code": 200, "body": (FIXTURES / "story_navigation.json").read_text(encoding="utf-8")},
    ])
    client, session = client_factory(stories, batch)
    report = client.get_active_story_report()
    urls = [row["relative_url"] for row in session.batch_requests]
    assert any("metric=reach%2Creplies" in url for url in urls)
    assert any(
        "metric=navigation" in url
        and "breakdown=story_navigation_action_type" in url
        for url in urls
    )
    assert report.items[0].core.metrics.reach == 10
    assert report.items[0].navigation.metrics.tap_forward == 4
    assert report.meta.period_basis is PeriodBasis.ACTIVE_STORY_WINDOW


def test_story_core_survives_navigation_failure(client_factory) -> None:
    stories = FakeResponse({"data": [{"id": "story-1"}]})
    batch = FakeResponse([
        {"code": 200, "body": "{\"data\":[{\"name\":\"reach\",\"values\":[{\"value\":10}]}]}"},
        {"code": 400, "body": "{\"error\":{\"message\":\"Unsupported\",\"code\":100,\"fbtrace_id\":\"story-trace\"}}"},
    ])
    client, _session = client_factory(stories, batch)
    report = client.get_active_story_report()
    assert report.items[0].core.metrics.reach == 10
    assert report.items[0].navigation.metrics.tap_forward is None
    assert report.meta.status is DatasetStatus.PARTIAL


def test_generic_code_10_is_not_insufficient_audience(client_factory) -> None:
    error = FakeResponse(
        {"error": {"message": "Permission denied", "code": 10}},
        status_code=400,
    )
    client, _session = client_factory(error)
    with pytest.raises(InstagramAPIError) as caught:
        client._make_request("story-1/insights")
    assert "audience" not in caught.value.issue.safe_message.lower()
```

- [ ] **Step 3: Confirm failures**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py -k story
```

- [ ] **Step 4: Add Story schemas and parser behavior**

```python
class StoryCoreMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    reach: int | None = None
    replies: int | None = None


class StoryNavigationMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    tap_back: int | None = None
    tap_exit: int | None = None
    tap_forward: int | None = None
    swipe_forward: int | None = None


class InstagramStoryItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    identity: MediaIdentity
    core: ScopedMetricGroup[StoryCoreMetrics]
    navigation: ScopedMetricGroup[StoryNavigationMetrics]


class InstagramStoryReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[InstagramStoryItem, ...]
    meta: DatasetMeta
```

`parse_story_navigation(payload)` traverses `data[].total_value.breakdowns[]`, accepts only breakdowns whose `dimension_keys` contain `story_navigation_action_type`, uppercases each one-value `dimension_values`, and maps only `TAP_BACK`, `TAP_EXIT`, `TAP_FORWARD`, `SWIPE_FORWARD`.

`parse_story_item(identity, core_payload, navigation_payload, issues=())` creates separate scoped groups. Successful navigation with empty `results` gives four zeros and `EMPTY`; failed/missing navigation gives four `None` and `UNAVAILABLE`. A failure in one group never clears the other.

- [ ] **Step 5: Implement separate requests and Story report**

For each Story build exactly:

```python
BatchCall(
    key=f"{story_id}:core", endpoint=f"{story_id}/insights",
    params={"metric": "reach,replies"}, request_group="story_core",
)
BatchCall(
    key=f"{story_id}:navigation", endpoint=f"{story_id}/insights",
    params={
        "metric": "navigation",
        "breakdown": "story_navigation_action_type",
    },
    request_group="story_navigation",
)
```

`InstagramStoryReport.meta` uses `MEDIA_INSIGHTS`, `ACTIVE_STORY_WINDOW`, four `None` period fields, aware retrieval time, UTC, and `truncated=True` only for incomplete Story-list pagination. Only an error whose sanitized classification explicitly matches insufficient-audience text/subcode may use that reason; code 10 alone remains permission/query.

- [ ] **Step 6: Verify and commit Task 5**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py -k story
ruff check src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py
git add src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py tests/fixtures/instagram/story_navigation.json
git commit -m "fix: migrate Story navigation insights to v26"
```

---

### Task 6: Account Totals, 90-Day Retention, and Non-Aggregable Segments

**Files:**
- Modify: `src/dashboard/schemas/instagram.py`
- Modify: `src/dashboard/api/instagram_parsers.py`
- Modify: `src/dashboard/api/instagram_client.py`
- Modify: both Instagram test modules
- Create: `tests/fixtures/instagram/account_totals.json`
- Create: `tests/fixtures/instagram/account_follow_type.json`

**Interfaces:**
- Produces `InstagramAccountMetrics`, `AccountBreakdownRow`, `AccountMetricSegment`, `InstagramAccountReport`, `parse_account_metrics`, `parse_account_breakdowns`, and `get_account_report`.

- [ ] **Step 1: Create exact account fixtures**

`account_totals.json`:

```json
{"data": [
  {"name": "reach", "period": "day", "total_value": {"value": 120}},
  {"name": "accounts_engaged", "period": "day", "total_value": {"value": 45}},
  {"name": "total_interactions", "period": "day", "total_value": {"value": 60}},
  {"name": "likes", "period": "day", "total_value": {"value": 0}},
  {"name": "comments", "period": "day", "total_value": {"value": 4}},
  {"name": "shares", "period": "day", "total_value": {"value": 3}},
  {"name": "saves", "period": "day", "total_value": {"value": 2}},
  {"name": "profile_links_taps", "period": "day", "total_value": {"value": 8}},
  {"name": "profile_views", "period": "day", "total_value": {"value": 30}}
]}
```

`account_follow_type.json`:

```json
{"data": [{
  "name": "follows_and_unfollows", "period": "day",
  "total_value": {"breakdowns": [{
    "dimension_keys": ["follow_type"],
    "results": [
      {"dimension_values": ["FOLLOWER"], "value": 12},
      {"dimension_values": ["NON_FOLLOWER"], "value": 5}
    ]
  }]}
}]}
```

- [ ] **Step 2: Write strong failing tests**

Append to client tests:

```python
def test_account_unique_reach_uses_one_aggregate(client_factory, today) -> None:
    totals = load("account_totals.json")
    empty = FakeResponse({"data": []})
    client, session = client_factory(
        FakeResponse(totals), empty, empty, empty
    )
    report = client.get_account_report(
        requested_since=today - timedelta(days=59), requested_until=today
    )
    assert report.meta.metric_scope is MetricScope.ACCOUNT_TOTAL_INCLUDING_ADS
    assert report.metrics.metrics.reach == 120
    calls = [row for row in session.calls if row.url.endswith("/ig-user-1/insights")]
    assert len(calls) == 4
    assert all(row.params["since"] == "2026-07-02" for row in calls)
    assert all(row.params["until"] == "2026-08-30" for row in calls)


def test_account_range_clamps_to_90_inclusive_days(client_factory, today) -> None:
    client, _session = client_factory(
        FakeResponse(load("account_totals.json")),
        FakeResponse({"data": []}),
        FakeResponse({"data": []}),
        FakeResponse({"data": []}),
    )
    report = client.get_account_report(
        requested_since=today - timedelta(days=150), requested_until=today
    )
    assert report.meta.requested_since == today - timedelta(days=150)
    assert report.meta.effective_since == today - timedelta(days=89)
    assert report.meta.effective_until == today
    assert report.meta.status is DatasetStatus.PARTIAL
    assert any(row.issue_type is IssueType.NOT_AGGREGABLE for row in report.meta.issues)


def test_expired_account_range_is_unavailable_without_call(
    client_factory, today
) -> None:
    client, session = client_factory()
    report = client.get_account_report(
        requested_since=today - timedelta(days=200),
        requested_until=today - timedelta(days=120),
    )
    assert report.metrics.metrics.reach is None
    assert report.meta.status is DatasetStatus.UNAVAILABLE
    assert not any(row.url.endswith("/ig-user-1/insights") for row in session.calls)


def test_non_aggregable_reach_preserves_segments_without_sum(
    client_factory, today
) -> None:
    failure = FakeResponse(
        {"error": {"message": "Cannot aggregate", "code": 100,
                   "error_subcode": 2108006}}, status_code=400,
    )
    segment_one = FakeResponse({"data": [
        {"name": "reach", "total_value": {"value": 70}}
    ]})
    segment_two = FakeResponse({"data": [
        {"name": "reach", "total_value": {"value": 80}}
    ]})
    client, _session = client_factory(
        failure, segment_one, segment_two,
        FakeResponse({"data": []}), FakeResponse({"data": []}),
        FakeResponse({"data": []}),
    )
    report = client.get_account_report(
        requested_since=today - timedelta(days=59), requested_until=today
    )
    assert report.metrics.metrics.reach is None
    assert [row.metrics.metrics.reach for row in report.segment_results] == [70, 80]
    assert report.meta.status is DatasetStatus.PARTIAL
```

Append to parser tests:

```python
from api.instagram_parsers import parse_account_breakdowns


def test_follow_breakdown_stays_raw_without_gain_loss_labels() -> None:
    rows = parse_account_breakdowns(
        load("account_follow_type.json"), timeframe=None
    )
    assert [row.dimension_values for row in rows] == [
        ("FOLLOWER",), ("NON_FOLLOWER",)
    ]
    assert all("gain" not in row.metric_name.lower() for row in rows)
    assert all("loss" not in row.metric_name.lower() for row in rows)
```

- [ ] **Step 3: Confirm failures**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py -k 'account or follow'
```

- [ ] **Step 4: Add exact account contracts**

```python
class InstagramAccountMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    reach: int | None = None
    accounts_engaged: int | None = None
    total_interactions: int | None = None
    profile_links_taps: int | None = None
    profile_views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None


class AccountBreakdownRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_name: str
    dimension_keys: tuple[str, ...]
    dimension_values: tuple[str, ...]
    value: int | float
    end_time: datetime | None = None
    timeframe: str | None = None


class AccountMetricSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    since: date
    until: date
    metrics: ScopedMetricGroup[InstagramAccountMetrics]


class InstagramAccountReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    metrics: ScopedMetricGroup[InstagramAccountMetrics]
    segment_results: tuple[AccountMetricSegment, ...] = ()
    breakdowns: tuple[AccountBreakdownRow, ...] = ()
    meta: DatasetMeta
```

`parse_account_metrics(payload, requested_metrics, issues=())` reads only `total_value.value`, emits one `NOT_RETURNED` issue per requested absent metric, and preserves zero. `parse_account_breakdowns(payload, timeframe)` copies raw dimensions/value; it never names gains, losses, or balance.

- [ ] **Step 5: Implement compatible groups, retention, and segment fallback**

```python
ACCOUNT_GROUPS = {
    "unique": ("reach", "accounts_engaged"),
    "interactions": (
        "total_interactions", "likes", "comments", "shares", "saves"
    ),
    "profile": ("profile_links_taps", "profile_views"),
    "follower_flow": ("follows_and_unfollows",),
}
```

The first three calls send `metric_type=total_value`, `period=day`, ISO dates. Follower flow adds `breakdown=follow_type`. Do not request `website_clicks`.

Use `retention_start = self.clock().date() - timedelta(days=89)`. Completely expired ranges return no API call, all None, `UNAVAILABLE`, and `NOT_AGGREGABLE/UNSUPPORTED`. Overlap clamps only effective start and marks `PARTIAL` with issue.

When Graph subcode `2108006` says a group cannot aggregate, split only that group into consecutive 30-day inclusive segments; preserve `AccountMetricSegment`s and leave its top-level fields None. Never sum. Other group failures do not clear successful groups.

- [ ] **Step 6: Verify and commit Task 6**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py -k 'account or follow'
ruff check src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py
git add src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py tests/fixtures/instagram/account_totals.json tests/fixtures/instagram/account_follow_type.json
git commit -m "fix: model Instagram account totals including ads"
```

### Task 7: Demographic Timeframes and Comment Pagination Contracts

**Files:**
- Modify: `src/dashboard/schemas/instagram.py`
- Modify: `src/dashboard/api/instagram_parsers.py`
- Modify: `src/dashboard/api/instagram_client.py`
- Modify: both Instagram test modules
- Create: `tests/fixtures/instagram/demographics.json`
- Create: `tests/fixtures/instagram/comments_page_one.json`
- Create: `tests/fixtures/instagram/comments_page_two.json`

**Interfaces:**
- Produces `DemographicBreakdownRow`, `DemographicMetrics`, `DemographicGroup`, `InstagramDemographicsReport`, `InstagramComment`, `InstagramCommentReport`, `parse_demographic_rows`, `parse_comments`, `get_demographics_report`, and `get_media_comments`.
- Demographics are account-level, never organic. Comment-edge data is `mixed_visible_count`.

- [ ] **Step 1: Create exact fixtures**

`demographics.json`:

```json
{"data": [{
  "name": "engaged_audience_demographics", "period": "lifetime",
  "total_value": {"breakdowns": [{
    "dimension_keys": ["age", "gender"],
    "results": [
      {"dimension_values": ["25-34", "F"], "value": 21},
      {"dimension_values": ["25-34", "M"], "value": 17}
    ]
  }]}
}]}
```

`comments_page_one.json`:

```json
{
  "data": [{
    "id": "comment-1", "text": "Primeiro", "like_count": 1,
    "username": "user-1", "timestamp": "2026-08-01T12:00:00+0000"
  }],
  "paging": {"cursors": {"after": "comment-cursor-1"}}
}
```

`comments_page_two.json`:

```json
{"data": [{
  "id": "comment-2", "text": "Segundo", "like_count": 0,
  "username": "user-2", "timestamp": "2026-08-02T12:00:00+0000"
}]}
```

- [ ] **Step 2: Write failing tests**

Append to client tests:

```python
def test_demographic_timeframes_are_sent_and_reached_is_absent(
    client_factory,
) -> None:
    client, session = client_factory(
        *(FakeResponse({"data": []}) for _ in range(6))
    )
    client.get_demographics_report()
    calls = [row for row in session.calls if row.url.endswith("/ig-user-1/insights")]
    follower = [row for row in calls if row.params["metric"] == "follower_demographics"]
    engaged = [row for row in calls if row.params["metric"] == "engaged_audience_demographics"]
    assert len(follower) == 3
    assert all("timeframe" not in row.params for row in follower)
    assert len(engaged) == 3
    assert all(row.params["timeframe"] == "this_month" for row in engaged)
    assert not any(
        row.params["metric"] == "reached_audience_demographics"
        for row in calls
    )


def test_comments_follow_each_media_cursor(client_factory) -> None:
    client, _session = client_factory(
        FakeResponse(load("comments_page_one.json")),
        FakeResponse(load("comments_page_two.json")),
    )
    report = client.get_media_comments(("ig-media-1",))
    assert [row.id for row in report.items] == ["comment-1", "comment-2"]
    assert report.meta.metric_scope is MetricScope.MIXED_VISIBLE_COUNT
    assert report.meta.status is DatasetStatus.OK


def test_repeated_comment_cursor_marks_partial(client_factory) -> None:
    page = load("comments_page_one.json")
    client, _session = client_factory(FakeResponse(page), FakeResponse(page))
    report = client.get_media_comments(("ig-media-loop",))
    assert report.meta.status is DatasetStatus.PARTIAL
    assert report.meta.truncated is True
    assert any(
        row.issue_type is IssueType.PARTIAL_PAGINATION
        for row in report.meta.issues
    )
```

Append to parser tests:

```python
from api.instagram_parsers import parse_demographic_rows


def test_demographic_parser_preserves_dimensions_and_timeframe() -> None:
    rows = parse_demographic_rows(
        load("demographics.json"), timeframe="this_month"
    )
    assert rows[0].dimension_keys == ("age", "gender")
    assert rows[0].dimension_values == ("25-34", "F")
    assert rows[0].value == 21
    assert rows[0].timeframe == "this_month"
```

- [ ] **Step 3: Confirm failures**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py -k 'demographic or comment'
```

- [ ] **Step 4: Add complete schemas and parsers**

```python
class DemographicBreakdownRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_name: str
    dimension_keys: tuple[str, ...]
    dimension_values: tuple[str, ...]
    value: int | float
    timeframe: str | None = None


class DemographicMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    rows: tuple[DemographicBreakdownRow, ...] = ()


class DemographicGroup(BaseModel):
    model_config = ConfigDict(frozen=True)
    metric_name: str
    timeframe: str | None
    data: ScopedMetricGroup[DemographicMetrics]


class InstagramDemographicsReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    followers: DemographicGroup
    engaged: DemographicGroup
    meta: DatasetMeta


class InstagramComment(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    media_id: str
    text: str = ""
    like_count: int | None = None
    username: str | None = None
    timestamp: datetime | None = None


class InstagramCommentReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[InstagramComment, ...]
    meta: DatasetMeta
```

`parse_demographic_rows(payload, timeframe)` traverses every `total_value.breakdowns`, copies `metric_name`, dimensions, value, and timeframe verbatim. `parse_comments(payload, media_id)` parses only the supplied page, assigns `media_id`, uses `_parse_datetime`, and keeps absent `like_count=None`.

- [ ] **Step 5: Implement exact demographic and comment requests**

`get_demographics_report` makes six independent calls:

- `follower_demographics`, `period=lifetime`, `metric_type=total_value`, each breakdown `age,gender`, `city`, `country`, no timeframe;
- `engaged_audience_demographics`, same three breakdowns, `timeframe=this_month`;
- never `reached_audience_demographics`.

Both groups use `ACCOUNT_TOTAL_INCLUDING_ADS`; each stores its timeframe in `DemographicGroup`. Meta uses `ACCOUNT_MEASUREMENT_WINDOW`, four None date fields, and `PARTIAL` if any call fails.

`get_media_comments` requests `/{media_id}/comments`, fields `id,text,like_count,username,timestamp`, `limit=50`, and calls `_paginate` independently per media. It follows only cursors, guards repeats, and returns `MIXED_VISIBLE_COUNT` + `MEDIA_LIFETIME_SNAPSHOT`. `truncated=True` means incomplete pagination only. All valid empty collections produce `EMPTY`; any failed collection with no data produces `UNAVAILABLE`; successful plus failed collections produce `PARTIAL`.

- [ ] **Step 6: Verify and commit Task 7**

```bash
python -m pytest -q tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py -k 'demographic or comment'
ruff check src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py
git add src/dashboard/schemas/instagram.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py tests/fixtures/instagram/demographics.json tests/fixtures/instagram/comments_page_one.json tests/fixtures/instagram/comments_page_two.json
git commit -m "fix: expose Instagram demographic and comment partiality"
```

---

### Task 8: Foundation and Instagram Verification Gate

**Files:**
- Verify only. If a check reveals a defect, first add a regression test that fails, then make the smallest production correction.

**Blocking dependencies before merge:**
- Ads consumes the shared contracts and exception signature.
- Loader/UI consumes typed reports, creates `MediaComparison` outside domain schemas, and removes paid `model_copy` injection.
- Loader/UI removes legacy `InstagramMedia`, `InstagramStory`, `get_recent_media`, `get_active_stories`, `get_account_insights`, `get_followers_history`, and `get_account_demographics` after all callers migrate.
- CI/live runs the v25/v26 probe and reconciles raw payload, parsed report, rendered UI, currency/timezone/attribution, and promoted/unpromoted content.
- PR #2 cannot leave draft or merge until all dependencies and spec acceptance criteria pass.

- [ ] **Step 1: Run complete non-live tests**

```bash
python -m pytest -q -m "not live" tests/unit/schemas tests/unit/api/test_exceptions.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py
```

Expected: all selected tests pass; no unexpected skip.

- [ ] **Step 2: Run Ruff on owned files only**

```bash
ruff check src/dashboard/schemas/metrics.py src/dashboard/schemas/instagram.py src/dashboard/api/exceptions.py src/dashboard/api/instagram_parsers.py src/dashboard/api/instagram_client.py tests/fakes/meta_http.py tests/conftest.py tests/unit/schemas/test_metrics.py tests/unit/api/test_exceptions.py tests/unit/api/test_instagram_parsers.py tests/unit/api/test_instagram_client.py
```

- [ ] **Step 3: Compile without repository artifacts**

```bash
PYTHONPYCACHEPREFIX=/tmp/zenit-pycache python -m compileall -q src/dashboard
git status --short
```

Expected: no generated pycache artifact appears.

- [ ] **Step 4: Confirm public interfaces with correct import path**

```bash
PYTHONPATH=src/dashboard python - <<'PY'
from api.instagram_client import InstagramClient

for name in (
    "get_media_report", "get_active_story_report", "get_account_report",
    "get_demographics_report", "get_media_comments",
):
    assert hasattr(InstagramClient, name), name
print("instagram-report-interface-ok")
PY
```

- [ ] **Step 5: Confirm security and forbidden fallback patterns**

```bash
if rg -n 'verify=False|video_views|total_(likes|comments|views).*organic' src/dashboard/api/instagram_client.py src/dashboard/api/instagram_parsers.py; then
  exit 1
fi
```

Expected: no matches.

- [ ] **Step 6: Confirm default pytest excludes live**

```bash
python -m pytest --collect-only -q
python -m pytest -q
```

Expected: default run excludes `live` and passes non-live tests.

The cross-plan legacy-removal scan runs in Dashboard Integration Task 8, after every UI caller has migrated. It is intentionally not a Foundation completion prerequisite.
