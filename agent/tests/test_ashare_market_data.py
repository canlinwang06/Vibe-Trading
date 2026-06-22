"""PR-04 tests for A-share assets, daily bars, and API routes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api_server
from src.ashare_data.market_data import AShareMarketDataError, AShareMarketDataService
from src.ashare_data.store import AShareDataStore

pytest.importorskip("duckdb")


class _FakeLoader:
    def fetch(self, codes, start_date, end_date, *, interval="1D", fields=None):
        index = pd.to_datetime(["2026-06-17", "2026-06-18", "2026-06-19"])
        frame = pd.DataFrame(
            {
                "open": [100.0, 101.0, 112.0],
                "high": [101.0, 112.0, 112.0],
                "low": [99.5, 100.5, 112.0],
                "close": [101.0, 112.0, 112.0],
                "volume": [1000.0, 1200.0, 0.0],
                "amount": [100000.0, 134400.0, 0.0],
                "turnover": [0.8, 1.2, 0.0],
            },
            index=index,
        )
        return {code: frame for code in codes}


@pytest.fixture
def store(tmp_path: Path) -> AShareDataStore:
    return AShareDataStore(database_path=tmp_path / "ashare.duckdb")


@pytest.fixture
def service(store: AShareDataStore) -> AShareMarketDataService:
    return AShareMarketDataService(store=store)


def test_core_assets_include_required_stocks_and_indexes(service: AShareMarketDataService) -> None:
    service.ensure_core_assets()

    assert service.get_asset("600519.SH")["ticker_name"] == "贵州茅台"
    assert service.get_asset("300750.SZ")["ticker_name"] == "宁德时代"
    assert service.get_asset("000001.SZ")["ticker_name"] == "平安银行"
    assert service.get_asset("000300.SH")["asset_type"] == "index"
    assert service.get_asset("000985.SH")["ticker_name"] == "中证全指"
    assert service.get_asset("399006.SZ")["ticker_name"] == "创业板指"


def test_market_daily_update_writes_ohlc_amount_limit_and_suspension(
    service: AShareMarketDataService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AShareMarketDataService, "_loader_for_source", staticmethod(lambda source: _FakeLoader()))

    result = service.update_market_daily(["600519.SH"], "2026-06-17", "2026-06-19", source="akshare")
    rows = service.get_market_daily("600519.SH", "2026-06-17", "2026-06-19")

    assert result["rows_written"] == 3
    assert rows[0]["open"] == 100.0
    assert rows[0]["amount"] == 100000.0
    assert rows[1]["limit_status"] == "limit_up"
    assert rows[2]["suspended"] is True
    assert rows[2]["adj_factor"] == 1.0


def test_market_daily_rejects_non_a_share_with_chinese_error(service: AShareMarketDataService) -> None:
    with pytest.raises(AShareMarketDataError, match="仅支持沪深 A 股"):
        service.update_market_daily(["AAPL.US"], "2026-06-17", "2026-06-19", source="local")


def test_market_daily_empty_fetch_returns_chinese_error(
    service: AShareMarketDataService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyLoader:
        def fetch(self, *args, **kwargs):
            return {}

    monkeypatch.setattr(AShareMarketDataService, "_loader_for_source", staticmethod(lambda source: EmptyLoader()))

    with pytest.raises(AShareMarketDataError, match="未能获取日线行情"):
        service.update_market_daily(["600519.SH"], "2026-06-17", "2026-06-19", source="local")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ASHARE_DATA_ROOT", str(tmp_path / "runtime"))
    monkeypatch.delenv("API_AUTH_KEY", raising=False)
    monkeypatch.setattr(AShareMarketDataService, "_loader_for_source", staticmethod(lambda source: _FakeLoader()))
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def test_ashare_asset_api_returns_required_asset_info(client: TestClient) -> None:
    for ticker in ("600519.SH", "300750.SZ", "000001.SZ"):
        response = client.get(f"/ashare/assets/{ticker}")
        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == ticker
        assert body["market"] == "CN_A"
        assert body["exchange"] in {"SH", "SZ"}


def test_ashare_update_and_market_daily_api_round_trip(client: TestClient) -> None:
    update = client.post(
        "/ashare/market-data/update",
        json={
            "tickers": ["600519.SH"],
            "start_date": "2026-06-17",
            "end_date": "2026-06-19",
            "source": "akshare",
        },
    )

    assert update.status_code == 200
    assert update.json()["rows_written"] == 3

    response = client.get(
        "/ashare/market-daily",
        params={"ticker": "600519.SH", "start_date": "2026-06-17", "end_date": "2026-06-19"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 3
    assert {"open", "high", "low", "close", "volume", "amount"}.issubset(body["rows"][0])


def test_ashare_api_returns_chinese_error_for_invalid_ticker(client: TestClient) -> None:
    response = client.post(
        "/ashare/market-data/update",
        json={
            "tickers": ["BTC-USDT"],
            "start_date": "2026-06-17",
            "end_date": "2026-06-19",
            "source": "local",
        },
    )

    assert response.status_code == 400
    assert "仅支持沪深 A 股" in response.json()["detail"]
