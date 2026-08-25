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
