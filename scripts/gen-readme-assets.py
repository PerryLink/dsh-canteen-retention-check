#!/usr/bin/env python3
"""Generate README image assets for dsh-canteen-retention-check (docs/assets/).

Outputs (idempotent overwrite):
  dsh-canteen-retention-check-flow-light.svg / -flow-dark.svg
      Hero data-flow diagram. Two hand-written SVG files (vector — never
      rasterized to webp). Text inside is command-surface tokens only
      (canteen_retention_check, rules/*.yaml, CF-001..CF-010, issues[],
      skipped[], config keys), so all five README languages share the same pair.

This plugin has no UI and no benchmark data, so there are no screenshots to
process and no evidence chart to draw. The older single-skin assets
(dsh-canteen-retention-check-flow.svg, -hero.png, -demo.gif, quickstart.png)
are kept untouched for external deep links; the READMEs reference only the new
pair.

Run once:  python scripts/gen-readme-assets.py
Requires:  Pillow (only for the font probe parity with the family script)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "assets")

# --- palette: PerryLink family (accent) + GitHub page backgrounds ----------
FAMILY = "#4B67B4"   # family accent (badges labelColor family uses #2B3245)
GREEN = {"light": "#16a34a", "dark": "#3fb950"}
SKIN = {
    "light": dict(bg="#ffffff", box="#f6f8fa", border="#d0d7de",
                  text="#1f2328", sub="#57606a"),
    "dark": dict(bg="#0d1117", box="#161b22", border="#30363d",
                 text="#f0f6fc", sub="#8b949e"),
}

# --- CJK font probe: kept for parity with the family pipeline ---------------
# The SVGs below carry command tokens only (ASCII), so no CJK font is needed
# for them; the probe stays so that adding a localized bitmap later fails
# loudly instead of rendering tofu boxes.
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",      # Microsoft YaHei
    r"C:\Windows\Fonts\simhei.ttf",    # SimHei
    r"C:\Windows\Fonts\Deng.ttf",      # DengXian
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
if FONT_PATH is None:
    sys.exit("FATAL: no CJK font found (looked for msyh.ttc, simhei.ttf, "
             "Deng.ttf, Noto Sans CJK, PingFang). Refusing to render Chinese "
             "as tofu boxes; install one of the probed fonts and re-run.")


# ---------------------------------------------------------------------------
# Hero data-flow SVG (light + dark): ledger rows -> tool -> rule pack -> report
# -> reviewer. All labels are command/config tokens, shared by five languages.
# ---------------------------------------------------------------------------
FLOW_NODES = [
    ("ledger rows[]", "JSON / YAML", 190),
    ("canteen_retention_check", "tool · read-only", 240),
    ("rules/*.yaml", "CF-001 .. CF-010", 190),
    ("report", "issues[] + skipped[]", 190),
    ("reviewer", "verdict stays human", 190),
]
GAP = 40
X0 = 50
Y0 = 150


def flow_svg(skin: str) -> str:
    s = SKIN[skin]
    w, h = 1260, 400
    nh = 96
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="dsh-canteen-retention-check '
        f'data flow">',
        f'<title>dsh-canteen-retention-check data flow</title>',
        f'<rect width="{w}" height="{h}" rx="18" fill="{s["bg"]}"/>',
        f'<text x="60" y="62" fill="{s["text"]}" font-family="ui-sans-serif,'
        f'system-ui,sans-serif" font-size="30" font-weight="700">'
        f'dsh-canteen-retention-check</text>',
        f'<text x="60" y="94" fill="{s["sub"]}" font-family="ui-monospace,'
        f'monospace" font-size="16">retention-ledger check · read-only on the '
        f'material</text>',
        f'<line x1="60" y1="116" x2="1200" y2="116" stroke="{s["border"]}"/>',
    ]
    x = X0
    centers = []
    for i, (label, sub, nw) in enumerate(FLOW_NODES):
        accent = GREEN[skin] if i == len(FLOW_NODES) - 1 else (
            FAMILY if i == 1 else s["border"])
        parts.append(
            f'<rect x="{x}" y="{Y0}" width="{nw}" height="{nh}" rx="14" '
            f'fill="{s["box"]}" stroke="{accent}" stroke-width="2"/>')
        label_size = 13 if len(label) > 16 else 16
        parts.append(
            f'<text x="{x + nw // 2}" y="{Y0 + 40}" fill="{s["text"]}" '
            f'text-anchor="middle" font-family="ui-monospace,monospace" '
            f'font-size="{label_size}" font-weight="700">{label}</text>')
        parts.append(
            f'<text x="{x + nw // 2}" y="{Y0 + 68}" fill="{s["sub"]}" '
            f'text-anchor="middle" font-family="ui-monospace,monospace" '
            f'font-size="12">{sub}</text>')
        centers.append((x, nw))
        if i < len(FLOW_NODES) - 1:
            ax = x + nw + 6
            ay = Y0 + nh // 2
            parts.append(
                f'<path d="M{ax} {ay}h{GAP - 12}" stroke="{s["sub"]}" '
                f'stroke-width="3"/>')
            parts.append(
                f'<path d="M{ax + GAP - 14} {ay - 7}l10 7-10 7" fill="none" '
                f'stroke="{s["sub"]}" stroke-width="3" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
        x += nw + GAP
    # config bar under nodes 2..3 (tool + rule pack)
    bx, bw, by, bh = 280, 620, 285, 52
    for cx in (centers[1][0] + centers[1][1] // 2,
               centers[2][0] + centers[2][1] // 2):
        parts.append(
            f'<path d="M{cx} {Y0 + nh}v{by - Y0 - nh}" '
            f'stroke="{FAMILY}" stroke-width="2" stroke-dasharray="5 5"/>')
    parts.append(
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="12" '
        f'fill="{s["box"]}" stroke="{FAMILY}" stroke-width="2"/>')
    parts.append(
        f'<text x="{bx + bw // 2}" y="{by + 33}" fill="{s["text"]}" '
        f'text-anchor="middle" font-family="ui-monospace,monospace" '
        f'font-size="13">config · rulesFile · disabledRules · onlyRules · '
        f'skipNotes · timeoutMs</text>')
    parts.append(
        f'<text x="60" y="352" fill="{s["sub"]}" font-family="ui-monospace,'
        f'monospace" font-size="12.5">excerpt = verbatim quote · '
        f'derived-from-principle &lt;= warn · institutional-configuration '
        f'&lt;= info</text>')
    parts.append(
        f'<text x="60" y="380" fill="{s["sub"]}" font-family="ui-monospace,'
        f'monospace" font-size="12.5">CF-010 cross-ledger: menu + samples · '
        f'a single-table run reports skipped[]</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for skin in ("light", "dark"):
        with open(os.path.join(
                OUT, f"dsh-canteen-retention-check-flow-{skin}.svg"),
                "w", encoding="utf-8", newline="\n") as fh:
            fh.write(flow_svg(skin))
    print("wrote 2 SVG assets to docs/assets/")


if __name__ == "__main__":
    main()
