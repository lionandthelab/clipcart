"""쿠팡 파트너스 리포트 API 래퍼 테스트.

엔드포인트·응답 구조는 2026-06-12 라이브 호출로 실측:
reports/{clicks,orders,commission}?startDate=YYYYMMDD&endDate=YYYYMMDD
→ 행마다 date/trackingCode/subId(+클릭·주문·커미션 필드).
"""

from __future__ import annotations

import clipcart.coupang as cp


def _capture(monkeypatch, data):
    calls: list[tuple] = []

    def fake_request(method, path, params=None, body=None):
        calls.append((method, path, params))
        return data

    monkeypatch.setattr(cp, "_request", fake_request)
    return calls


def test_report_clicks_calls_endpoint_with_dates(monkeypatch):
    rows = [{"date": "20260610", "subId": "salrimshorts123", "click": 3}]
    calls = _capture(monkeypatch, rows)
    assert cp.report_clicks("20260605", "20260611") == rows
    method, path, params = calls[0]
    assert method == "GET"
    assert path.endswith("/reports/clicks")
    assert params == {"startDate": "20260605", "endDate": "20260611"}


def test_report_orders_and_commission_endpoints(monkeypatch):
    calls = _capture(monkeypatch, [])
    cp.report_orders("20260605", "20260611")
    cp.report_commission("20260605", "20260611")
    assert calls[0][1].endswith("/reports/orders")
    assert calls[1][1].endswith("/reports/commission")


def test_report_accepts_iso_dates(monkeypatch):
    calls = _capture(monkeypatch, [])
    cp.report_clicks("2026-06-05", "2026-06-11")
    assert calls[0][2] == {"startDate": "20260605", "endDate": "20260611"}


def test_report_returns_empty_list_when_no_data(monkeypatch):
    _capture(monkeypatch, None)
    assert cp.report_clicks("20260605", "20260611") == []
