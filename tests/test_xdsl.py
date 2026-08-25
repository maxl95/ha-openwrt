"""Test xDSL metric collection and normalized sensor descriptions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.openwrt.api.base import DslMetrics, OpenWrtData
from custom_components.openwrt.api.ssh import SshClient
from custom_components.openwrt.sensor import _get_dsl_sensors


@pytest.mark.asyncio
async def test_get_dsl_metrics_preserves_raw_metrics_and_normalizes_core_values() -> (
    None
):
    """xDSL metrics expose stable core values while retaining every raw field."""
    client = SshClient(
        MagicMock(), MagicMock(), host="router", username="root", password=""
    )
    client.execute_command = AsyncMock(
        return_value="""{
            "state": "Showtime with TC-Layer sync",
            "up": true,
            "uptime": 42,
            "mode": "G.993.2 (VDSL2)",
            "downstream": {"data_rate": 116790000, "snr": 12.5},
            "upstream": {"data_rate": 42462000, "snr": 6.7},
            "vendor_extension": {"preserved": true}
        }"""
    )

    metrics = await client.get_dsl_metrics()

    assert metrics.available is True
    assert metrics.up is True
    assert metrics.state == "Showtime with TC-Layer sync"
    assert metrics.downstream_data_rate == 116790000
    assert metrics.upstream_snr == 6.7
    assert metrics.raw["vendor_extension"] == {"preserved": True}


@pytest.mark.asyncio
async def test_get_dsl_metrics_is_unavailable_when_router_has_no_dsl_object() -> None:
    """Routers without the optional xDSL ubus object add no DSL capability."""
    client = SshClient(
        MagicMock(), MagicMock(), host="router", username="root", password=""
    )
    client.execute_command = AsyncMock(return_value="")

    metrics = await client.get_dsl_metrics()

    assert metrics.available is False
    assert metrics.raw == {}


def test_dsl_sensors_expose_core_values_and_complete_raw_metrics() -> None:
    """xDSL sensors include useful measurements and preserve vendor extensions."""
    data = OpenWrtData(
        dsl=DslMetrics(
            available=True,
            up=True,
            state="Showtime with TC-Layer sync",
            downstream_data_rate=116790000,
            upstream_data_rate=42462000,
            raw={"vendor_extension": {"preserved": True}},
        )
    )

    descriptions = _get_dsl_sensors()
    sync = next(item for item in descriptions if item.key == "dsl_downstream_sync")
    diagnostics = next(item for item in descriptions if item.key == "dsl_diagnostics")

    assert sync.value_fn(data) == 116.79
    assert diagnostics.value_fn(data) == "Showtime with TC-Layer sync"
    assert diagnostics.attrs_fn(data) == {"vendor_extension": {"preserved": True}}


def test_dsl_sensors_expose_line_quality_and_error_counters() -> None:
    """xDSL trend sensors cover attainable rates, quality and errors."""
    data = OpenWrtData(
        dsl=DslMetrics(
            available=True,
            raw={
                "downstream": {
                    "attndr": 141_952_288,
                    "latn": 10.6,
                    "satn": 10.6,
                    "inp": 69,
                    "interleave_delay": 160,
                    "actatp": 14.5,
                    "mineftr": 100_728_000,
                },
                "upstream": {
                    "attndr": 42_585_000,
                    "latn": 7.9,
                    "satn": 7.6,
                    "inp": 45,
                    "interleave_delay": 0,
                    "actatp": -3.3,
                    "mineftr": 42_127_000,
                },
                "errors": {
                    "near": {"es": 2, "ses": 1, "fec_c": 4490, "cv_c": 15},
                    "far": {"es": 135, "ses": 50, "fec_c": 33503, "cv_c": 406},
                },
            },
        )
    )

    descriptions = {item.key: item for item in _get_dsl_sensors()}

    assert descriptions["dsl_downstream_attainable"].value_fn(data) == 141.952288
    assert descriptions["dsl_upstream_line_attenuation"].value_fn(data) == 7.9
    assert descriptions["dsl_downstream_inp"].value_fn(data) == 69
    assert descriptions["dsl_upstream_interleave_delay"].value_fn(data) == 0
    assert descriptions["dsl_downstream_minimum_throughput"].value_fn(data) == 100.728
    assert descriptions["dsl_near_end_fec"].value_fn(data) == 4490
    assert descriptions["dsl_far_end_error_seconds"].value_fn(data) == 135
    assert descriptions["dsl_far_end_code_violations"].value_fn(data) == 406


def test_dsl_sensors_are_disabled_by_default() -> None:
    """Optional xDSL sensors do not add entities until a user enables them."""
    assert all(
        description.entity_registry_enabled_default is False
        for description in _get_dsl_sensors()
    )
