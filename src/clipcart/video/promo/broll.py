"""니치별 영어 b-roll 검색어 (Pexels) — 불편함/사용/결과 장면용.

Pexels는 영어 쿼리가 결과가 좋다. pain=문제장면, use=사용/행동, clean=결과.
키워드 미스 시 카테고리 폴백.
"""

from __future__ import annotations

BROLL: dict[str, dict[str, str]] = {
    "배수구 거름망 스테인리스": {
        "pain": "hair clogged shower drain", "use": "cleaning bathroom sink drain", "clean": "clean shiny sink drain"},
    "싱크대 물막이 실리콘": {
        "pain": "water splashing kitchen sink", "use": "washing dishes kitchen sink", "clean": "clean tidy kitchen sink"},
    "냉장고 정리 트레이 서랍형": {
        "pain": "messy full refrigerator", "use": "organizing refrigerator food", "clean": "organized clean fridge"},
    "케이블 정리 클립 책상": {
        "pain": "tangled cables under desk", "use": "organizing desk cables", "clean": "clean minimal desk setup"},
    "욕실 물때 스크래퍼": {
        "pain": "dirty shower glass water stains", "use": "squeegee cleaning shower glass", "clean": "sparkling clean bathroom"},
    "전자레인지 음식 덮개": {
        "pain": "dirty microwave inside", "use": "heating food microwave", "clean": "clean microwave kitchen"},
    "반려동물 털제거 롤러 침구": {
        "pain": "cat hair on bed sheets", "use": "lint roller pet hair", "clean": "clean tidy bed pet"},
    "키보드 청소 젤": {
        "pain": "dusty dirty keyboard", "use": "cleaning computer keyboard", "clean": "clean desk keyboard"},
    "창문 레일 청소솔": {
        "pain": "dusty dirty window track", "use": "cleaning window sill brush", "clean": "clean bright window"},
    "음식물 쓰레기통 밀폐 뚜껑": {
        "pain": "kitchen trash bin smell flies", "use": "kitchen food waste bin", "clean": "clean modern kitchen bin"},
    "세탁기 먼지 거름망 부직포": {
        "pain": "lint dust on dark clothes", "use": "laundry washing machine", "clean": "clean folded laundry"},
    "빨래 양말 건조 클립 행거": {
        "pain": "pile of socks laundry", "use": "hanging socks to dry", "clean": "tidy hanging laundry"},
    "가스레인지 틈새 커버 실리콘": {
        "pain": "dirty gap stove counter", "use": "cleaning kitchen stove", "clean": "clean kitchen countertop"},
    "멀티탭 정리함": {
        "pain": "messy power strip cables dust", "use": "organizing power cables", "clean": "clean organized cables"},
    "현관 먼지 제거 매트": {
        "pain": "dirty muddy shoes entrance", "use": "wiping shoes doormat", "clean": "clean home entrance hallway"},
    "옷장 칸막이 수납함 접이식": {
        "pain": "messy clothes drawer pile", "use": "folding organizing clothes", "clean": "organized neat wardrobe"},
    "텀블러 세척솔 스펀지": {
        "pain": "dirty coffee tumbler bottle", "use": "cleaning water bottle brush", "clean": "clean shiny tumbler"},
    "냄비 뚜껑 거치대 주방": {
        "pain": "messy stovetop cooking pots", "use": "cooking pot lid kitchen", "clean": "clean tidy kitchen counter"},
    "변기 틈새 청소솔 좁은": {
        "pain": "dirty toilet bathroom", "use": "cleaning toilet brush", "clean": "clean white bathroom toilet"},
    "후드 필터 기름때 시트": {
        "pain": "greasy kitchen range hood", "use": "cleaning kitchen hood filter", "clean": "clean modern kitchen hood"},
    "침대 틈새 막이 패드": {
        "pain": "phone behind bed gap", "use": "tidying bed bedroom", "clean": "clean cozy bedroom bed"},
    "신발 정리대 2단": {
        "pain": "messy pile of shoes entrance", "use": "organizing shoes rack", "clean": "neat organized shoe rack"},
    "분리수거함 가정용 분리형": {
        "pain": "messy recycling bags home", "use": "sorting recycling bins", "clean": "organized recycling bins"},
    "압축봉 커튼 설치 못없이": {
        "pain": "bare window no curtain", "use": "installing curtain rod", "clean": "cozy room curtains light"},
}

_CATEGORY_FALLBACK: dict[str, dict[str, str]] = {
    "청소": {"pain": "messy dirty home", "use": "cleaning house chores", "clean": "clean bright tidy home"},
    "주방": {"pain": "messy kitchen counter", "use": "cleaning kitchen", "clean": "clean modern kitchen"},
    "욕실": {"pain": "dirty bathroom", "use": "cleaning bathroom", "clean": "clean bright bathroom"},
    "정리/수납": {"pain": "messy cluttered room", "use": "organizing home storage", "clean": "organized tidy room"},
    "세탁": {"pain": "pile of laundry", "use": "doing laundry home", "clean": "clean folded laundry"},
    "반려동물": {"pain": "pet hair home mess", "use": "pet care cleaning", "clean": "clean home with pet"},
}


def get_broll(niche: dict) -> dict[str, str]:
    q = BROLL.get(niche.get("keyword", ""))
    if q:
        return q
    return _CATEGORY_FALLBACK.get(niche.get("category", ""),
                                  {"pain": "messy home", "use": "cleaning home", "clean": "clean tidy home"})
