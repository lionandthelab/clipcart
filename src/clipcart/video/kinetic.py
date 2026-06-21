"""단어 동기화 카라오케 자막 — 페이지 분할, 레이아웃, 프레임별 렌더."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from clipcart.video.frames import ACCENT, BLACK, W, _font

WHITE = "#FFFFFF"
DIM = (255, 255, 255, 90)

_SENT_END = ("。", ".", "?", "!", "…")


def split_pages(words: list[dict], max_words: int = 5) -> list[list[int]]:
    """단어 인덱스를 읽기 좋은 페이지(자막 한 화면)로 분할.

    문장부호에서 끊고, 최대 max_words로 제한.
    """
    pages: list[list[int]] = []
    cur: list[int] = []
    for i, w in enumerate(words):
        cur.append(i)
        text = w["text"].strip()
        ends_sentence = text.endswith(_SENT_END)
        if ends_sentence or len(cur) >= max_words:
            pages.append(cur)
            cur = []
    if cur:
        pages.append(cur)
    return pages


def _strip_join(words: list[dict], idxs: list[int]) -> list[str]:
    return [words[i]["text"].strip() for i in idxs]


class Caption:
    """한 장면의 단어 자막 — 페이지/레이아웃 사전 계산 후 프레임별 draw."""

    def __init__(
        self,
        words: list[dict],
        duration: float,
        *,
        font_size: int = 70,
        max_words: int = 5,
        bottom: int = 1640,
        line_gap: int = 16,
        highlight: str = ACCENT,
        max_width: int | None = None,
    ) -> None:
        self.words = words
        self.duration = duration
        self.font = _font(font_size, bold=True)
        self.bottom = bottom
        self.line_gap = line_gap
        self.highlight = highlight
        self.max_width = max_width or (W - 130)
        self.pages = split_pages(words, max_words=max_words)
        # 단어 인덱스 → (페이지번호, 페이지 내 위치)
        self._page_of: dict[int, int] = {}
        for pno, page in enumerate(self.pages):
            for slot in page:
                self._page_of[slot] = pno
        self._layouts = [self._layout_page(page) for page in self.pages]
        # 각 단어의 표시 시작 = start, 끝 = 다음 단어 start (마지막은 duration)
        self._starts = [w["start"] for w in words]

    def _measure(self, text: str) -> int:
        tmp = Image.new("RGB", (1, 1))
        return int(ImageDraw.Draw(tmp).textlength(text, font=self.font))

    def _layout_page(self, idxs: list[int]) -> list[dict]:
        """페이지 단어들을 줄바꿈 배치. 반환: 단어별 {idx,text,x,y,w}."""
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        space = draw.textlength(" ", font=self.font)
        ascent, descent = self.font.getmetrics()
        line_h = ascent + descent
        # 줄 구성
        lines: list[list[tuple[int, str, int]]] = [[]]
        widths = [0.0]
        for idx in idxs:
            token = self.words[idx]["text"].strip()
            tw = draw.textlength(token, font=self.font)
            add = tw if not lines[-1] else widths[-1] + space + tw
            if add > self.max_width and lines[-1]:
                lines.append([])
                widths.append(0.0)
                add = tw
            lines[-1].append((idx, token, int(tw)))
            widths[-1] = add
        n_lines = len(lines)
        block_h = n_lines * line_h + (n_lines - 1) * self.line_gap
        top = self.bottom - block_h
        out: list[dict] = []
        for li, line in enumerate(lines):
            total = widths[li]
            x = (W - total) / 2
            y = top + li * (line_h + self.line_gap)
            for idx, token, tw in line:
                out.append({"idx": idx, "text": token, "x": int(x), "y": int(y), "w": tw})
                x += tw + space
        return out

    def _active_index(self, t: float) -> int:
        active = -1
        for i, s in enumerate(self._starts):
            if t >= s:
                active = i
            else:
                break
        return active

    def draw(self, frame: Image.Image, t: float) -> None:
        if not self.words:
            return
        active = self._active_index(t)
        if active < 0:
            active = 0  # 첫 단어 등장 전: 첫 페이지 미점등 상태로 노출
            pre = True
        else:
            pre = False
        page_no = self._page_of.get(active, 0)
        layout = self._layouts[page_no]
        draw = ImageDraw.Draw(frame, "RGBA")
        ascent, descent = self.font.getmetrics()
        for item in layout:
            idx = item["idx"]
            spoken = (idx < active) or (idx == active and not pre)
            is_active = idx == active and not pre
            x, y = item["x"], item["y"]
            if is_active:
                # 등장 팝: 0.13s 동안 1.32→1.0 스케일, 노랑
                age = t - self._starts[idx]
                scale = 1.0 + max(0.0, 0.32 * (1 - min(age / 0.13, 1.0)))
                self._draw_word(frame, item, self.highlight, scale, ascent)
            elif spoken:
                draw.text((x, y), item["text"], font=self.font, fill=WHITE,
                          stroke_width=6, stroke_fill=BLACK)
            else:
                draw.text((x, y), item["text"], font=self.font, fill=DIM,
                          stroke_width=5, stroke_fill=(0, 0, 0, 160))

    def _draw_word(self, frame: Image.Image, item: dict, color: str, scale: float, ascent: int) -> None:
        if scale <= 1.001:
            ImageDraw.Draw(frame, "RGBA").text(
                (item["x"], item["y"]), item["text"], font=self.font, fill=color,
                stroke_width=7, stroke_fill=BLACK,
            )
            return
        # 스케일 팝: 단어를 별도 레이어에 그려 확대 후 합성(중심 고정)
        pad = 24
        ascent2, descent2 = self.font.getmetrics()
        lh = ascent2 + descent2
        layer = Image.new("RGBA", (item["w"] + pad * 2, lh + pad * 2), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((pad, pad), item["text"], font=self.font, fill=color,
                                   stroke_width=7, stroke_fill=BLACK)
        nw, nh = int(layer.width * scale), int(layer.height * scale)
        layer = layer.resize((nw, nh), Image.LANCZOS)
        cx = item["x"] + item["w"] / 2
        cy = item["y"] + lh / 2
        frame.paste(layer, (int(cx - nw / 2), int(cy - nh / 2)), layer)
