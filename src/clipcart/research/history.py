"""업로드 히스토리 — 권위 있는 중복 방지 원장(append-only).

게시(PUBLISH)에 성공한 항목만 기록한다. 선정 단계의 niche_state(커서/시도 가드)와
별개로, "실제로 올라간 것"을 기준으로 같은 상품·같은 이름·같은 문제(키워드)를
반복하지 않도록 한다.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from clipcart.config import DATA_DIR

HISTORY_FILE = DATA_DIR / "history.json"

_NORM_RE = re.compile(r"[^0-9a-z가-힣]+")
# 이름 정규화 시 제거할 흔한 수식/규격 토큰(과도 차단 방지를 위해 보수적)
_NAME_NOISE = re.compile(r"\d+\s*(cm|mm|ml|l|g|kg|개|개입|매|p|p입|세트|색|color)\b", re.IGNORECASE)


def load_history() -> list[dict[str, Any]]:
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []
    return []


def _save(items: list[dict[str, Any]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def name_key(name: str) -> str:
    """상품명 정규화 키 — 동일/거의 동일한 리스팅을 잡되 과도 차단은 피함."""
    s = _NAME_NOISE.sub("", (name or "").lower())
    return _NORM_RE.sub("", s)


def record(entry: dict[str, Any]) -> None:
    """게시 성공 1건 기록. 같은 post_id면 중복 추가하지 않음."""
    items = load_history()
    pid = entry.get("post_id")
    if pid and any(e.get("post_id") == pid for e in items):
        return
    items.append(entry)
    _save(items)


def mark_not_live(post_ids: set[str]) -> int:
    """비공개/삭제 확인된 게시를 live=False로 마킹(감사 기록). 마킹한 개수 반환.

    주의: 중복 차단은 live 여부와 무관하게 '한 번이라도 올린 것'을 기준으로 한다.
    비공개됐다고 같은 상품/이름/주제를 다시 올리면 운영자에겐 중복으로 보이기
    때문이다(2026-06-14 운영자 피드백). live 플래그는 bio 페이지 노출 판정과
    '언제 내려갔는지' 감사용으로만 쓴다.
    """
    items = load_history()
    changed = 0
    for e in items:
        if e.get("post_id") in post_ids and e.get("live") is not False:
            e["live"] = False
            e["not_live_at"] = date.today().isoformat()
            changed += 1
    if changed:
        _save(items)
    return changed


def used_coupang_ids() -> set[str]:
    return {str(e["coupang_product_id"]) for e in load_history() if e.get("coupang_product_id")}


def used_aliexpress_ids() -> set[str]:
    return {str(e["aliexpress_product_id"]) for e in load_history() if e.get("aliexpress_product_id")}


def used_name_keys() -> set[str]:
    return {name_key(e["product_name"]) for e in load_history() if e.get("product_name")}


def keyword_last_used() -> dict[str, str]:
    """니치 키워드 → 마지막 사용 날짜(ISO). 비공개분도 포함해 이미 다룬 주제의
    재선정을 막는다(gap_days 동안 회피)."""
    out: dict[str, str] = {}
    for e in load_history():
        k = e.get("niche_keyword")
        d = e.get("date", "")
        if k and d > out.get(k, ""):
            out[k] = d
    return out


def days_since(iso_date: str) -> int:
    try:
        return (date.today() - date.fromisoformat(iso_date)).days
    except Exception:  # noqa: BLE001
        return 9999
