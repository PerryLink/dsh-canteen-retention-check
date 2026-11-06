#!/usr/bin/env python3
"""Generate the README visuals for dsh-canteen-retention-check.

Outputs (all under docs/assets/, idempotent overwrite):

  dsh-canteen-retention-check-hero-zh-light.webp   1440x576  Pillow poster
  dsh-canteen-retention-check-hero-zh-dark.webp
  dsh-canteen-retention-check-hero-en-light.webp
  dsh-canteen-retention-check-hero-en-dark.webp
  dsh-canteen-retention-check-flow-v5-light.svg    1100x660  hand-written SVG
  dsh-canteen-retention-check-flow-v5-dark.svg

Hero — a 48-hour retention window over five real fixture rows:
  every row is taken verbatim from tests/fixtures or samples/quickstart
  (dish, weight, sampled/removed time, keeper), so the drawing cannot claim a
  behaviour the plugin does not have. Each row is measured twice: a weight bar
  against the 125 g floor, and a sampled->removed bar against the 48 h line.
  The verdict chip is the rule the fixture actually trips; the clean baseline
  row says "no difference". The bottom strip is the one check that cannot run
  on a single ledger (CF-010), which the report lists in skipped[].

Flow — two moments around the 48-hour window, not a row of five boxes:
  the material is parsed into canonical fields; eight checks run at the
  sampling moment, one at the release moment, and the 48 h window hangs
  between them; CF-010 sits on its own dashed channel because it needs a
  second ledger and lands in skipped[] on a single-table run. Findings merge
  into one report card with issues[] and skipped[]. The SVG is language
  neutral (English + code tokens) so the same light/dark pair serves all
  five README languages.

Every label is measured before it is drawn; a label that would overflow
aborts the run instead of shipping a clipped figure.

Run once:  python scripts/gen-readme-assets.py
Requires:  Pillow + the Microsoft YaHei / Consolas fonts shipped with Windows.
"""
from __future__ import annotations

import math
import os
import sys
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "assets")

# ---------------------------------------------------------------------------
# fonts
# ---------------------------------------------------------------------------
FONT_CANDIDATES = {
    "sans": [r"C:\Windows\Fonts\msyh.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/System/Library/Fonts/PingFang.ttc"],
    "sans_bold": [r"C:\Windows\Fonts\msyhbd.ttc",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                  "/System/Library/Fonts/PingFang.ttc"],
    "mono": [r"C:\Windows\Fonts\consola.ttf",
             r"C:\Windows\Fonts\cour.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/System/Library/Fonts/Menlo.ttc"],
}
FONT_PATH: dict[str, str] = {}
for _key, _paths in FONT_CANDIDATES.items():
    _found = next((p for p in _paths if os.path.exists(p)), None)
    if _found is None:
        sys.exit(f"FATAL: no font for {_key!r}; looked for {_paths}. "
                 "Refusing to render tofu boxes.")
    FONT_PATH[_key] = _found

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(size: int, kind: str = "sans") -> ImageFont.FreeTypeFont:
    key = (kind, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONT_PATH[kind], size, index=0)
    return _font_cache[key]


_measure = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def text_width(text: str, size: float, bold: bool = False,
               mono: bool = False) -> float:
    kind = "mono" if mono else ("sans_bold" if bold else "sans")
    return _measure.textlength(text, font=font(round(size), kind))


def assert_fit(text: str, size: float, limit: float, *, bold=False,
               mono=False, where: str = "") -> float:
    """Fail loudly instead of shipping a clipped / overflowing label."""
    width = text_width(text, size, bold, mono)
    if width > limit:
        raise SystemExit(
            f"FATAL: text overflows in {where or '?'} "
            f"({width:.0f}px > {limit:.0f}px at {size}px): {text!r}")
    return width


def fit_size(text: str, limit: float, start: float, floor: float, *,
             bold=False, mono=False) -> float:
    size = float(start)
    while size > floor and text_width(text, size, bold, mono) > limit:
        size -= 0.5
    if text_width(text, size, bold, mono) > limit:
        raise SystemExit(f"FATAL: cannot fit {text!r} into {limit}px "
                         f"(floor {floor}px)")
    return size


# ---------------------------------------------------------------------------
# palette — family accent + the light/dark page backgrounds in the brief
# ---------------------------------------------------------------------------
THEMES = {
    "light": dict(
        bg_top=(249, 246, 253), bg_bottom=(228, 234, 248),
        ink=(24, 29, 45), ink2=(66, 78, 104), muted=(104, 116, 142),
        faint=(146, 156, 178),
        surface=(255, 255, 255), surface_alt=(244, 247, 253),
        border=(213, 220, 240), grid=(224, 229, 243),
        family=(75, 103, 180), family_soft=(232, 238, 252),
        ok=(26, 130, 92), warn=(168, 112, 24), hot=(186, 66, 44),
        violet=(102, 76, 184), info=(52, 92, 184),
        shadow=(38, 50, 92),
    ),
    "dark": dict(
        bg_top=(19, 26, 42), bg_bottom=(12, 16, 22),
        ink=(238, 242, 255), ink2=(178, 189, 214), muted=(146, 158, 186),
        faint=(112, 124, 152),
        surface=(23, 31, 48), surface_alt=(19, 26, 41),
        border=(43, 54, 82), grid=(35, 45, 68),
        family=(132, 150, 245), family_soft=(35, 45, 74),
        ok=(84, 214, 165), warn=(226, 179, 74), hot=(240, 138, 93),
        violet=(180, 158, 246), info=(122, 162, 247),
        shadow=(0, 0, 0),
    ),
}


def mix(rgb, other, ratio):
    return tuple(round(rgb[i] + (other[i] - rgb[i]) * ratio) for i in range(3))


def over(rgb, theme, alpha):
    """Flatten `rgb` against the theme surface for alpha-style fills."""
    return mix(theme["surface"], rgb, alpha)


class Sheet:
    """2x supersampled RGBA canvas; every coordinate is in final pixels."""

    def __init__(self, width: int, height: int, theme: dict, ss: int = 2):
        self.w, self.h, self.ss, self.t = width, height, ss, theme
        base = Image.new("RGB", (1, 2))
        base.putpixel((0, 0), theme["bg_top"])
        base.putpixel((0, 1), theme["bg_bottom"])
        self.img = base.resize((width * ss, height * ss),
                               Image.BILINEAR).convert("RGBA")
        self.d = ImageDraw.Draw(self.img)

    def _box(self, box):
        s = self.ss
        return [round(v * s) for v in box]

    def rounded(self, box, radius, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(self._box(box), radius=radius * self.ss,
                                 fill=fill, outline=outline,
                                 width=max(1, round(width * self.ss)))

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(self._box(box), fill=fill, outline=outline,
                         width=max(1, round(width * self.ss)))

    def line(self, xy, fill, width=1):
        s = self.ss
        self.d.line([(round(xy[0] * s), round(xy[1] * s)),
                     (round(xy[2] * s), round(xy[3] * s))],
                    fill=fill, width=max(1, round(width * s)))

    def dashed_line(self, x1, y1, x2, y2, fill, width=1.5, dash=5, gap=5):
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 0:
            return
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        pos = 0.0
        while pos < length:
            end = min(pos + dash, length)
            self.line((x1 + ux * pos, y1 + uy * pos,
                       x1 + ux * end, y1 + uy * end), fill, width)
            pos += dash + gap

    def dot(self, cx, cy, r, fill):
        s = self.ss
        self.d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s,
                        (cy + r) * s], fill=fill)

    def text(self, xy, s, size, fill, *, bold=False, mono=False, anchor="ls"):
        kind = "mono" if mono else ("sans_bold" if bold else "sans")
        self.d.text((xy[0] * self.ss, xy[1] * self.ss), s,
                    font=font(round(size * self.ss), kind),
                    fill=fill, anchor=anchor)

    def shadow(self, box, radius, dy=14, blur=26, alpha=34):
        s = self.ss
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        b = self._box((box[0], box[1] + dy, box[2], box[3] + dy))
        ld.rounded_rectangle(b, radius=radius * s,
                             fill=self.t["shadow"] + (alpha,))
        layer = layer.filter(ImageFilter.GaussianBlur(blur * s))
        self.img.alpha_composite(layer)
        self.d = ImageDraw.Draw(self.img)

    def save(self, path):
        out = self.img.resize((self.w, self.h), Image.LANCZOS)
        out.convert("RGB").save(path, "WEBP", quality=94, method=6)


# ===========================================================================
# HERO — 1440x576
# ===========================================================================
HERO_W, HERO_H = 1440, 576

# Rows are verbatim fixture data.  `gap` is the sampled -> removed interval:
# 2026-03-04 11:40 -> 2026-03-06 11:40 is exactly 48 h (clean), while
# 2026-03-04 11:40 -> 2026-03-04 13:40 is the 2 h failing case.
HERO_ROWS = [
    dict(dish=("红烧肉", "红烧肉"), stamp="2026-03-04 11:40", weight=125,
         gap=48.0, verdict=("无差异", "no difference"), kind="ok"),
    dict(dish=("（空）", "(empty)"), stamp="2026-03-04 11:40", weight=125,
         gap=48.0, verdict=("CF-001 error", "CF-001 error"), kind="error"),
    dict(dish=("红烧肉", "红烧肉"), stamp="2026-03-04 11:40", weight=120,
         gap=48.0, verdict=("CF-002 error", "CF-002 error"), kind="error"),
    dict(dish=("待填", "待填"), stamp="2026-03-04 11:40", weight=125,
         gap=48.0, verdict=("CF-008 warn", "CF-008 warn"), kind="warn"),
    dict(dish=("红烧肉", "红烧肉"), stamp="2026-03-04 11:40", weight=125,
         gap=2.0, verdict=("CF-006 error", "CF-006 error"), kind="error"),
]

HERO_COPY = {
    "zh": dict(
        kicker="CHECKER · 食堂留样核对",
        title="留样核对",
        value=("把留样台账核成四要素、125 克与 48 小时",
               "缺项、超窗、占位符逐行列进清单"),
        sub="CF-001..CF-010 · 9 条单表 + 1 条跨表 · 规则包 2026.3",
        meta="只读材料 · 无网络 · 不调用模型 · 结论留给审核人",
        footer="dsh-canteen-retention-check · Apache-2.0 · DSH ≥0.2.1 <0.3.0",
        panel_title="48 小时留样窗口",
        panel_meta="sample rows · tests/fixtures",
        col1="品名 / 留样时间", col2="留样量 g", col3="留样 → 出柜 · 0–48 h",
        col4="判定",
        skip="CF-010 跨表：菜单 + 留样两份台账 · 单表运行 → skipped[]",
        weight_unit="g", weight_tick="125 g", window_tick="48 h",
        gap_label="2 h",
    ),
    "en": dict(
        kicker="CHECKER · CANTEEN SAMPLE RETENTION",
        title="Retention",
        value=("Four elements, 125 g, 48 h — one ledger",
               "Missing cells, short windows, placeholders"),
        sub="CF-001..CF-010 · 9 table + 1 cross · pack 2026.3",
        meta="Read-only · no network · no model · verdict stays human",
        footer="dsh-canteen-retention-check · Apache-2.0 · DSH ≥0.2.1 <0.3.0",
        panel_title="48h retention window",
        panel_meta="sample rows · tests/fixtures",
        col1="dish / sampled", col2="weight g", col3="sampled → out · 0–48 h",
        col4="verdict",
        skip="CF-010 cross-table: menu + samples · single-ledger run → skipped[]",
        weight_unit="g", weight_tick="125 g", window_tick="48 h",
        gap_label="2 h",
    ),
}

LX = 72
PANEL = (736, 60, 1408, 520)
PANEL_X0, PANEL_Y0, PANEL_X1, PANEL_Y1 = PANEL
IL, IR = PANEL_X0 + 28, PANEL_X1 - 28
ROW_TOPS = (156, 218, 280, 342, 404)

WEIGHT_X0, WEIGHT_X1 = 896, 960
WEIGHT_MAX = 150.0
WINDOW_X0, WINDOW_X1 = 1000, 1250
WINDOW_MAX = 50.0
WINDOW_48 = WINDOW_X0 + 48 * (WINDOW_X1 - WINDOW_X0) / WINDOW_MAX
VERDICT_X0, VERDICT_X1 = 1264, 1380

KIND_COLOR = {"ok": "ok", "error": "hot", "warn": "warn"}


def hero(lang: str, theme_name: str) -> Sheet:
    c = HERO_COPY[lang]
    t = THEMES[theme_name]
    zh = lang == "zh"
    s = Sheet(HERO_W, HERO_H, t)

    # ---- left column: kicker / title / two value lines / sub / meta ----
    kicker = c["kicker"]
    ksize = fit_size(kicker, 330, 16.5, 13.5, bold=True)
    kw = text_width(kicker, ksize, bold=True) + 54
    s.rounded((LX, 74, LX + kw, 116), 21, fill=over(t["family"], t, 0.10),
              outline=over(t["family"], t, 0.40), width=1.2)
    s.dot(LX + 23, 95, 3.6, t["family"])
    s.text((LX + 38, 95), kicker, ksize, t["family"], bold=True, anchor="lm")

    tsize = fit_size(c["title"], 620, 88, 64, bold=True)
    assert_fit(c["title"], tsize, 620, bold=True, where="hero title")
    s.text((LX, 232), c["title"], tsize, t["ink"], bold=True)

    v1, v2 = c["value"]
    assert_fit(v1, 27, 628, where="hero value line 1")
    assert_fit(v2, 27, 628, where="hero value line 2")
    s.text((LX, 288), v1, 27, t["ink2"])
    s.text((LX, 326), v2, 27, t["ink2"])

    ssize = fit_size(c["sub"], 628, 24.5, 19)
    s.text((LX, 378), c["sub"], ssize, t["muted"])

    s.line((LX, 412, LX + 560, 412), over(t["border"], t, 0.95), width=1.2)
    assert_fit(c["meta"], 20.5, 628, where="hero meta")
    s.text((LX, 452), c["meta"], 20.5, t["faint"])

    s.line((LX, 508, LX + 560, 508), over(t["border"], t, 0.95), width=1.2)
    assert_fit(c["footer"], 15.5, 628, where="hero footer")
    s.text((LX, 536), c["footer"], 15.5, t["faint"])

    # ---- right panel: the 48-hour window over five fixture rows ----
    s.shadow(PANEL, 22, dy=16, blur=28,
             alpha=42 if theme_name == "light" else 150)
    s.rounded(PANEL, 22, fill=t["surface"],
              outline=over(t["border"], t, 0.95), width=1.4)

    psize = fit_size(c["panel_title"], 300, 19, 15, bold=True)
    s.text((IL, 100), c["panel_title"], psize, t["ink"], bold=True)
    assert_fit(c["panel_meta"], 11.5, 210, mono=True, where="panel meta")
    s.text((IR, 100), c["panel_meta"], 11.5, t["muted"], mono=True, anchor="rs")
    s.line((IL, 118, IR, 118), over(t["border"], t, 0.9), width=1.1)

    heads = (c["col1"], c["col2"], c["col3"], c["col4"])
    s.text((IL, 142), heads[0], 12, t["muted"])
    s.text((WEIGHT_X0, 142), heads[1], 12, t["muted"])
    s.text((WINDOW_X0, 142), heads[2], 12, t["muted"])
    s.text((IR, 142), heads[3], 12, t["muted"], anchor="rs")

    # rule lines: the 125 g floor and the 48 h floor
    weight_tick = WEIGHT_X0 + 125 * (WEIGHT_X1 - WEIGHT_X0) / WEIGHT_MAX
    s.dashed_line(weight_tick, 150, weight_tick, 452,
                  over(t["warn"], t, 0.65), width=1.2, dash=4, gap=4)
    s.dashed_line(WINDOW_48, 150, WINDOW_48, 452,
                  over(t["hot"], t, 0.55), width=1.2, dash=4, gap=4)
    s.text((weight_tick, 464), c["weight_tick"], 10.5, t["warn"], anchor="ms")
    s.text((WINDOW_48, 464), c["window_tick"], 10.5, t["hot"], anchor="ms")

    for index, row in enumerate(HERO_ROWS):
        top = ROW_TOPS[index]
        color = t[KIND_COLOR[row["kind"]]]
        if index > 0:
            s.line((IL, top - 8, IR, top - 8), over(t["grid"], t, 0.9),
                   width=1.0)

        # dish + sampled time
        dish = row["dish"][0 if zh else 1]
        dcol = t["hot"] if row["kind"] == "error" and row["dish"][0] == "（空）" \
            else (t["warn"] if row["dish"][0] == "待填" else t["ink"])
        s.text((IL, top + 24), dish, 15, dcol, bold=True)
        s.text((IL, top + 42), row["stamp"], 11, t["muted"], mono=True)

        # weight and the 125 g floor
        wcolor = t["ok"] if row["weight"] >= 125 else t["hot"]
        s.text((WEIGHT_X0, top + 24), f"{row['weight']}", 14.5, t["ink"],
               bold=True, mono=True)
        s.text((WEIGHT_X0 + 30, top + 24), c["weight_unit"], 10.5, t["muted"])
        s.rounded((WEIGHT_X0, top + 31, WEIGHT_X1, top + 39), 4,
                  fill=over(t["grid"], t, 0.85))
        end = WEIGHT_X0 + min(row["weight"], WEIGHT_MAX) * \
            (WEIGHT_X1 - WEIGHT_X0) / WEIGHT_MAX
        s.rounded((WEIGHT_X0, top + 31, max(end, WEIGHT_X0 + 6), top + 39), 4,
                  fill=wcolor)

        # sampled -> removed against the 48 h line
        s.rounded((WINDOW_X0, top + 14, WINDOW_48, top + 44), 7,
                  fill=over(t["family"], t, 0.055))
        end_x = WINDOW_X0 + min(row["gap"], WINDOW_MAX) * \
            (WINDOW_X1 - WINDOW_X0) / WINDOW_MAX
        bar_color = t["family"] if row["gap"] >= 48 else t["hot"]
        s.rounded((WINDOW_X0, top + 25, max(end_x, WINDOW_X0 + 16),
                   top + 33), 3, fill=bar_color)
        if row["gap"] < 48:
            s.text((end_x + 8, top + 34), c["gap_label"], 10.5, bar_color)

        # verdict chip
        vtext = row["verdict"][0 if zh else 1]
        vsize = fit_size(vtext, VERDICT_X1 - VERDICT_X0 - 20, 11.5, 9.5,
                         bold=True)
        s.rounded((VERDICT_X0, top + 10, VERDICT_X1, top + 40), 15,
                  fill=over(color, t, 0.13), outline=over(color, t, 0.50),
                  width=1.2)
        s.text(((VERDICT_X0 + VERDICT_X1) / 2, top + 25), vtext, vsize, color,
               bold=True, anchor="mm")

    # the one rule a single ledger cannot run
    s.rounded((IL, 470, IR, 506), 12, fill=over(t["family"], t, 0.07),
              outline=over(t["family"], t, 0.35), width=1.1)
    s.dot(IL + 18, 488, 3.2, t["family"])
    sk = c["skip"]
    sksize = fit_size(sk, IR - IL - 44, 11.5, 9.5)
    s.text((IL + 32, 488), sk, sksize, t["ink2"], anchor="lm")
    return s


# ===========================================================================
# FLOW — 1100x660 SVG (two moments + 48 h window + cross-table bypass)
# ===========================================================================
FLOW_W, FLOW_H = 1100, 660

SANS = ("'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',"
        "'Source Han Sans SC',sans-serif")
MONO = ("Consolas,'Cascadia Mono','SFMono-Regular',ui-monospace,monospace")


def hexs(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def col(value):
    if isinstance(value, (tuple, list)):
        return hexs(value)
    return value


class Flow:
    """Hand-written SVG with measured labels and no automatic layout."""

    def __init__(self, theme_name: str):
        self.t = THEMES[theme_name]
        self.theme_name = theme_name
        self.o: list[str] = []
        t = self.t
        self.o.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{FLOW_W}" '
            f'height="{FLOW_H}" viewBox="0 0 {FLOW_W} {FLOW_H}" '
            f'role="img" aria-labelledby="flowTitle flowDesc">'
            f'<title id="flowTitle">dsh-canteen-retention-check structure: '
            f'two moments, 48-hour window, cross-table bypass</title>'
            f'<desc id="flowDesc">The retention ledger is parsed into '
            f'canonical fields; eight rules check the sampling moment and '
            f'CF-006 checks the 48-hour release floor; CF-010 needs a second '
            f'ledger and lands in skipped[] when only one is supplied; '
            f'findings merge into issues[] and skipped[].</desc>'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{hexs(t["bg_top"])}"/>'
            f'<stop offset="1" stop-color="{hexs(t["bg_bottom"])}"/>'
            f'</linearGradient>'
            f'<filter id="soft" x="-20%" y="-20%" width="140%" height="140%">'
            f'<feDropShadow dx="0" dy="5" stdDeviation="7" '
            f'flood-color="{hexs(t["shadow"])}" '
            f'flood-opacity="{0.16 if theme_name == "light" else 0.42}"/>'
            f'</filter></defs>'
            f'<rect width="{FLOW_W}" height="{FLOW_H}" rx="20" '
            f'fill="url(#bg)"/>'
        )

    # -- primitives ------------------------------------------------------
    def text(self, x, y, s, size, fill, *, bold=False, mono=False,
             anchor="start", spacing=None, opacity=None, limit=None):
        if limit is not None:
            kind = "mono" if mono else ("sans_bold" if bold else "sans")
            w = _measure.textlength(s, font=font(round(size), kind))
            if w > limit:
                raise SystemExit(f"FATAL: flow label {s!r} is {w:.0f}px > "
                                 f"{limit}px")
        family = MONO if mono else SANS
        weight = "700" if bold else "400"
        extra = f' letter-spacing="{spacing}"' if spacing is not None else ""
        extra += f' opacity="{opacity}"' if opacity is not None else ""
        self.o.append(
            f'<text x="{x}" y="{y}" fill="{col(fill)}" font-family="{family}" '
            f'font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{extra}>{escape(s)}</text>')

    def rect(self, x, y, w, h, r, fill, stroke=None, sw=1, dashed=False,
             shadow=False):
        dash = ' stroke-dasharray="5 5"' if dashed else ""
        filt = ' filter="url(#soft)"' if shadow else ""
        stroke_attr = (f' stroke="{col(stroke)}" stroke-width="{sw}"{dash}'
                       if stroke is not None else "")
        self.o.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            f'fill="{col(fill)}"{stroke_attr}{filt}/>')

    def line(self, x1, y1, x2, y2, stroke, sw=1.2, dashed=False):
        dash = ' stroke-dasharray="5 5"' if dashed else ""
        self.o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                      f'stroke="{col(stroke)}" stroke-width="{sw}"{dash}/>')

    def dot(self, cx, cy, r, fill):
        self.o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" '
                      f'fill="{col(fill)}"/>')

    def arrow(self, x1, y1, x2, y2, stroke, sw=2.2, dashed=False):
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        ang = math.atan2(y2 - y1, x2 - x1)
        head = 8
        bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
        p1 = (x2 - head * 1.6 * math.cos(ang) - head * 0.62 * math.sin(ang),
              y2 - head * 1.6 * math.sin(ang) + head * 0.62 * math.cos(ang))
        p2 = (x2 - head * 1.6 * math.cos(ang) + head * 0.62 * math.sin(ang),
              y2 - head * 1.6 * math.sin(ang) - head * 0.62 * math.cos(ang))
        self.o.append(f'<path d="M{x1} {y1}L{bx} {by}" stroke="{col(stroke)}" '
                      f'stroke-width="{sw}" fill="none"{dash} '
                      f'stroke-linecap="round"/>')
        self.o.append(
            f'<path d="M{x2} {y2}L{p1[0]:.1f} {p1[1]:.1f}L{p2[0]:.1f} '
            f'{p2[1]:.1f}Z" fill="{col(stroke)}"/>')

    def arrow_down(self, x, y1, y2, stroke, sw=2.2):
        self.arrow(x, y1, x, y2, stroke, sw)

    def arrow_right(self, x1, x2, y, stroke, sw=2.2, dashed=False):
        self.arrow(x1, y, x2, y, stroke, sw, dashed)

    def elbow(self, x1, y1, x2, y2, stroke, sw=2.0):
        """Right, then up/down, then into the target — a two-bend merge line."""
        mid = x1 + 8
        self.o.append(f'<path d="M{x1} {y1}H{mid}V{y2}" '
                      f'stroke="{col(stroke)}" stroke-width="{sw}" '
                      f'fill="none" stroke-linecap="round" '
                      f'stroke-linejoin="round"/>')
        self.arrow(mid, y2, x2, y2, stroke, sw)

    def finish(self):
        self.o.append("</svg>")
        return "\n".join(self.o) + "\n"


def flow(theme_name: str) -> Flow:
    """Draw the structure diagram.  Geometry lives in named constants below."""
    f = Flow(theme_name)
    t = f.t

    family, ink, ink2, muted = t["family"], t["ink"], t["ink2"], t["muted"]
    faint, border, grid = t["faint"], t["border"], t["grid"]
    surface, surface_alt = t["surface"], t["surface_alt"]
    ok, warn, hot = t["ok"], t["warn"], t["hot"]

    # ---- header ---------------------------------------------------------
    f.text(44, 44, "STRUCTURE · MATERIAL → CHECKS → REPORT", 11, family,
           bold=True, mono=True, spacing=1.4, limit=1012)
    f.text(44, 78, "One ledger row, two moments, ten rules", 24, ink,
           bold=True, limit=900)
    f.text(44, 102,
           "Sampling checks four elements, 125 g, minute precision, template "
           "leftovers and future dates; release checks the 48-hour floor.", 12,
           ink2, limit=1012)
    f.text(44, 122,
           "A missing column skips the whole rule — never a per-row report. "
           "CF-010 is the only cross-table rule.", 12, muted, limit=830)
    f.text(1056, 44, "rules/canteen-retention.yaml · 2026.3", 11, muted,
           mono=True, anchor="end", limit=320)
    f.line(44, 136, 1056, 136, border, 1)

    # ---- material card --------------------------------------------------
    f.rect(40, 148, 228, 282, 18, surface, border, 1.1, shadow=True)
    f.text(56, 172, "MATERIAL", 11, family, bold=True, mono=True, spacing=1.2,
           limit=196)
    f.text(56, 198, "Retention ledger", 14, ink, bold=True, limit=196)
    f.text(56, 220, "rows[] · JSON / YAML", 11, ink2, limit=196)
    f.text(56, 238, "read-only · never rewritten", 11, muted, limit=196)
    f.line(56, 250, 252, 250, grid, 1)
    fields = [("meal", "lunch"), ("foodName", "braised pork"),
              ("sampleWeight", "125 g"), ("sampledAt", "03-04 11:40"),
              ("removedAt", "03-06 11:40"), ("keeper", "Zhang")]
    for i, (key, value) in enumerate(fields):
        y = 272 + i * 24
        f.text(56, y, key, 11, muted, mono=True, limit=80)
        f.text(140, y, value, 13, ink, mono=True, limit=112)
    f.text(56, 416, "aliases folded · case / space", 11, faint, limit=196)

    # ---- rule-pack card -------------------------------------------------
    f.rect(40, 446, 228, 142, 18, surface_alt, border, 1.1)
    f.text(56, 470, "RULE PACK", 11, family, bold=True, mono=True, spacing=1.2,
           limit=196)
    f.text(56, 496, "rules/*.yaml", 13, ink, bold=True, mono=True, limit=196)
    f.text(56, 518, "version 2026.3", 11, ink2, mono=True, limit=196)
    f.text(56, 538, "9 table + 1 cross-table", 11, ink2, limit=196)
    f.text(56, 558, "replace the YAML, not the TS", 11, muted, limit=196)
    f.text(56, 578, "validated on load", 11, faint, limit=196)

    # ---- sampling panel (one ledger, t = 0) -----------------------------
    f.rect(296, 148, 304, 204, 18, surface, border, 1.1, shadow=True)
    f.text(312, 172, "① SAMPLING · t = 0", 13, ink, bold=True, limit=200)
    f.text(588, 172, "8 rules", 11, muted, mono=True, anchor="end", limit=60)
    f.line(312, 182, 584, 182, grid, 1)
    chips = [
        ("CF-001", "foodName · error", "error"),
        ("CF-002", "≥ 125 g · error", "error"),
        ("CF-003", "sampledAt · error", "error"),
        ("CF-004", "keeper · error", "error"),
        ("CF-005", "minute fmt · warn", "warn"),
        ("CF-007", "meal · info", "info"),
        ("CF-008", "placeholder · warn", "warn"),
        ("CF-009", "not future · warn", "warn"),
    ]
    chip_colors = {"error": hot, "warn": warn, "info": t["info"]}
    for i, (rule, label, sev) in enumerate(chips):
        cx = 308 + (i % 2) * 150
        cy = 190 + (i // 2) * 40
        f.rect(cx, cy, 138, 34, 11, surface_alt, border, 1)
        f.rect(cx + 6, cy + 9, 3, 16, 1.5, chip_colors[sev])
        f.text(cx + 15, cy + 15, rule, 13, ink, bold=True, mono=True,
               limit=110)
        f.text(cx + 15, cy + 28, label, 11, muted, mono=True, limit=113)
        f.dot(cx + 128, cy + 17, 2.6, chip_colors[sev])

    # ---- cross-table channel (two ledgers) ------------------------------
    f.rect(620, 148, 240, 152, 18, surface_alt, family, 1.3, dashed=True)
    f.text(636, 172, "CF-010 · CROSS-TABLE", 11, family, bold=True, mono=True,
           spacing=1.1, limit=208)
    # two overlapping ledger plates
    f.rect(636, 186, 30, 22, 4, surface, family, 1.1)
    f.rect(646, 194, 30, 22, 4, surface, family, 1.1)
    f.text(688, 196, "menu + samples", 14, ink, bold=True, limit=156)
    f.text(688, 216, "join on date / meal / dish", 11, ink2, limit=156)
    f.text(688, 238, "one ledger → skipped[]", 11, hot, limit=156)
    f.text(688, 258, "never silently passed", 11, muted, limit=156)
    f.text(636, 286, "the other nine rules read one table", 11, faint,
           limit=208)

    # ---- 48-hour window band -------------------------------------------
    f.rect(296, 368, 564, 80, 16, surface, border, 1.1, shadow=True)
    f.text(312, 390, "48 h RETENTION WINDOW", 11, family, bold=True,
           mono=True, spacing=1.2, limit=280)
    f.text(844, 390, "2880 min · exactly 48 h → no issue", 11, muted,
           mono=True, anchor="end", limit=238)
    axis_y = 416
    f.line(316, axis_y, 844, axis_y, border, 1.6)
    # the measured span (>= 48 h)
    f.rect(316, 404, 528, 8, 4, over(ok, t, 0.55))
    for hours in (0, 12, 24, 36, 48):
        x = 316 + hours * (844 - 316) / 48.0
        f.line(x, axis_y - 4, x, axis_y + 4, muted, 1.2)
        label = f"{hours} h" if hours in (0, 48) else f"{hours}"
        anchor = "start" if hours == 0 else ("end" if hours == 48 else "middle")
        f.text(x, 434, label, 11, muted, mono=True, anchor=anchor, limit=40)

    # ---- release panel (one rule, t >= 48 h) ----------------------------
    f.rect(620, 464, 240, 124, 18, surface, border, 1.1, shadow=True)
    f.text(636, 486, "② RELEASE · removedAt", 13, ink, bold=True, limit=170)
    f.text(844, 486, "1 rule", 11, muted, mono=True, anchor="end", limit=60)
    f.line(636, 494, 844, 494, grid, 1)
    f.rect(636, 502, 208, 36, 11, surface_alt, border, 1)
    f.rect(642, 510, 3, 20, 1.5, hot)
    f.text(651, 517, "CF-006 · 48 h floor", 13, ink, bold=True, mono=True,
           limit=185)
    f.text(651, 531, "dateGap ≥ 2 days · error", 11, muted, mono=True,
           limit=185)
    f.rect(636, 548, 13, 8, 3, hot)
    f.text(656, 560, "11:40 → 13:40 = 2 h < 48 h", 11, hot, mono=True,
           limit=188)
    f.text(636, 580, "wall-clock only · no temperature", 11, faint, limit=208)

    # ---- evidence / severity panel --------------------------------------
    f.rect(296, 464, 304, 124, 18, surface_alt, border, 1.1)
    f.text(312, 486, "SEVERITY FOLLOWS EVIDENCE", 11, family, bold=True,
           mono=True, spacing=1.1, limit=272)
    f.text(312, 512, "direct → error", 13, ink, limit=272)
    f.text(312, 534, "derived-from-principle → ≤ warn", 13, ink, limit=272)
    f.text(312, 556, "institutional-configuration → ≤ info", 13, ink,
           limit=272)
    f.text(312, 578, "empty issues[] ≠ clean — see skipped[]", 11, muted,
           limit=272)

    # ---- report card ----------------------------------------------------
    f.rect(880, 148, 180, 452, 18, surface, border, 1.1, shadow=True)
    f.text(896, 172, "REPORT", 11, family, bold=True, mono=True, spacing=1.2,
           limit=148)
    f.text(896, 198, "issues[]", 15, ink, bold=True, mono=True, limit=148)
    f.text(896, 218, "+ skipped[]", 13, ink2, bold=True, mono=True, limit=148)
    f.text(896, 242, "3 error · 1 warn", 11, ink2, mono=True, limit=148)
    f.text(896, 260, "skipped 1 · fixtures", 11, ink2, mono=True, limit=148)
    f.line(896, 272, 1044, 272, grid, 1)
    reports = [
        ("CF-001 · row 1", "food name empty", hot),
        ("CF-002 · row 1", "120 g < 125 g", hot),
        ("CF-008 · row 1", "template text left", warn),
        ("CF-006 · row 1", "2 h < 48 h", hot),
    ]
    for i, (rule, detail, color) in enumerate(reports):
        y = 296 + i * 40
        f.dot(900, y - 4, 2.4, color)
        f.text(910, y, rule, 13, ink, mono=True, limit=134)
        f.text(910, y + 13, detail, 11, muted, mono=True, limit=134)
    f.line(896, 452, 1044, 452, grid, 1)
    f.text(896, 474, "skipped[]", 12, ink, bold=True, mono=True, limit=148)
    f.rect(892, 484, 156, 58, 10, over(hot, t, 0.06), hot, 1.1, dashed=True)
    f.text(900, 502, "CF-010", 13, hot, bold=True, mono=True, limit=140)
    f.text(900, 518, "needs menu + samples", 11, ink2, limit=140)
    f.text(900, 532, "single ledger → listed", 11, muted, limit=140)
    f.line(896, 556, 1044, 556, grid, 1)
    f.text(896, 576, "lists differences only", 11, ink2, limit=148)
    f.text(896, 592, "verdict stays human", 11, faint, limit=148)

    # ---- connectors -----------------------------------------------------
    f.arrow_right(268, 296, 220, family, 2.0)
    f.arrow_down(448, 352, 368, family, 2.0)
    f.arrow_down(844, 448, 464, family, 2.0)
    f.arrow_right(860, 880, 224, family, 2.0, dashed=True)
    f.elbow(860, 522, 880, 408, family, 2.0)

    # ---- footer ---------------------------------------------------------
    f.text(44, 628,
           "An empty issues[] never means clean — every check that could not "
           "run is listed in skipped[] with its reason.", 11.5, muted,
           limit=760)
    f.text(1056, 628, "wording guard · disclaimer attached", 11.5, faint,
           anchor="end", limit=220)
    return f


# ===========================================================================
# entry point
# ===========================================================================
def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for lang in ("zh", "en"):
        for theme in ("light", "dark"):
            sheet = hero(lang, theme)
            sheet.save(os.path.join(
                OUT, f"dsh-canteen-retention-check-hero-{lang}-{theme}.webp"))

    for theme in ("light", "dark"):
        with open(os.path.join(
                OUT, f"dsh-canteen-retention-check-flow-v5-{theme}.svg"),
                "w", encoding="utf-8", newline="\n") as fh:
            fh.write(flow(theme).finish())
    print("wrote 4 hero webp + 2 flow svg to docs/assets/")


if __name__ == "__main__":
    main()
