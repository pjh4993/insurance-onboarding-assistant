"""Diagram helpers for the docs: every diagram is plain SVG drawn in currentColor, so it follows the light or
dark theme of the page it sits in. Generators in this folder call these helpers and write the SVGs under
docs/<section>/assets/; run `uv run --no-project python tools/diagrams/<generator>.py` from the repo root.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STANDALONE_STYLE = (
    "<style>svg{color:#1f2328;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}"
    "@media (prefers-color-scheme:dark){svg{color:#e6edf3}}</style>"
)

BLUE, PURPLE, ORANGE, GREEN = "#2563eb", "#7c3aed", "#d97706", "#059669"
MONO = 'font-family="ui-monospace, SFMono-Regular, Menlo, monospace"'


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self, pid, w, h, label):
        self.pid, self.w, self.h, self.label = pid, w, h, label
        self.p = []

    def defs(self):
        m = ""
        for sfx, col, op in (("a", "currentColor", "1"), ("g", "currentColor", "0.5"),
                             ("o", ORANGE, "1"), ("n", GREEN, "1")):
            m += (f'<marker id="{self.pid}-{sfx}" viewBox="0 0 10 10" refX="9" refY="5" '
                  f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                  f'<path d="M0 0L10 5L0 10z" fill="{col}" fill-opacity="{op}"/></marker>')
        return f"<defs>{m}</defs>"

    def box(self, x, y, w, h, title, subs=(), color=None, dashed=False, mono=False, radius=6):
        c = color or "currentColor"
        fo = "0.14" if color else "0.05"
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                      f'fill="{c}" fill-opacity="{fo}" stroke="{c}" stroke-width="1.6"'
                      f' stroke-opacity="{"0.9" if color else "0.45"}"{dash}/>')
        cx = x + w / 2
        n = 1 + len(subs)
        ty = y + h / 2 - (n - 1) * 8 + 5
        f = MONO if mono else ""
        self.p.append(f'<text x="{cx}" y="{ty}" font-size="14" text-anchor="middle" '
                      f'fill="currentColor" font-weight="650" {f}>{esc(title)}</text>')
        for i, s in enumerate(subs):
            self.p.append(f'<text x="{cx}" y="{ty + 17 + i * 15}" font-size="11.5" '
                          f'text-anchor="middle" fill="currentColor" fill-opacity="0.72">{esc(s)}</text>')

    def group(self, x, y, w, h, label, color=None):
        c = color or "currentColor"
        self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="none" '
                      f'stroke="{c}" stroke-opacity="0.4" stroke-width="1.4" stroke-dasharray="7 5"/>')
        self.p.append(f'<text x="{x + 12}" y="{y + 18}" font-size="12" text-anchor="start" '
                      f'fill="{c}" fill-opacity="0.95" font-weight="700">{esc(label)}</text>')

    def arrow(self, x1, y1, x2, y2, label=None, color=None, dashed=False, anchor="middle",
              lx=None, ly=None, two=False):
        sfx = {None: "a", ORANGE: "o", GREEN: "n"}.get(color, "a")
        c = color or "currentColor"
        op = "0.55" if dashed else "0.8"
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        start = f' marker-start="url(#{self.pid}-{sfx})"' if two else ""
        self.p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" '
                      f'stroke-opacity="{op}" stroke-width="1.5"{dash} '
                      f'marker-end="url(#{self.pid}-{sfx})"{start}/>')
        if label:
            tx = lx if lx is not None else (x1 + x2) / 2
            ty = ly if ly is not None else (y1 + y2) / 2 - 7
            for i, ln in enumerate(label.split("\n")):
                self.p.append(f'<text x="{tx}" y="{ty + i * 14}" font-size="11.5" '
                              f'text-anchor="{anchor}" fill="currentColor" '
                              f'fill-opacity="0.75">{esc(ln)}</text>')

    def text(self, x, y, s, size=13, anchor="middle", weight="400", op="1", color="currentColor"):
        self.p.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
                      f'fill="{color}" fill-opacity="{op}" font-weight="{weight}">{esc(s)}</text>')

    def legend(self, x, y, items):
        for i, (col, lab) in enumerate(items):
            bx = x + i * 150
            self.p.append(f'<rect x="{bx}" y="{y}" width="22" height="14" rx="4" fill="{col}" '
                          f'fill-opacity="0.14" stroke="{col}" stroke-width="1.6"/>')
            self.p.append(f'<text x="{bx + 30}" y="{y + 11.5}" font-size="12" text-anchor="start" '
                          f'fill="currentColor" fill-opacity="0.8">{esc(lab)}</text>')

    def render(self):
        # The <style> only matters when the file is shown as an <img> (GitHub): it gives currentColor a value
        # and follows the viewer's color scheme. The docs site inlines the SVG and strips it (see .mkdocs/hooks.py),
        # so the diagram takes the page's own colors and font instead.
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" role="img" '
                f'aria-label="{esc(self.label)}" '
                f'style="width:100%;height:auto;max-width:{self.w}px;display:block;margin:0 auto" '
                f'font-family="inherit">{STANDALONE_STYLE}{self.defs()}{"".join(self.p)}</svg>')

    def save(self, path):
        """Write the SVG, creating the directory. Paths are relative to the repo root."""
        out = ROOT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.render() + "\n")
        print(f"wrote {path}")

    def chip(self, cx, cy, txt, color, w=22, h=19):
        self.p.append(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="4" '
                      f'fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-opacity="0.85" stroke-width="1.3"/>')
        self.p.append(f'<text x="{cx}" y="{cy+4.5}" font-size="11.5" text-anchor="middle" '
                      f'fill="currentColor" font-weight="700">{esc(txt)}</text>')

    def rule(self, x1, y, x2, op="0.12"):
        self.p.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="currentColor" stroke-opacity="{op}"/>')


MONOF = 'font-family="ui-monospace, SFMono-Regular, Menlo, monospace"'
KIND = {"code": BLUE, "llm": PURPLE, "wait": ORANGE}


def _num(self, cx, cy, n):
    self.p.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{ORANGE}"/>')
    self.p.append(f'<text x="{cx}" y="{cy + 4}" font-size="11" text-anchor="middle" fill="#ffffff" font-weight="700">{n}</text>')


def _pill(self, x, y, w, h, txt, color=None, dashed=False):
    c = color or "currentColor"
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{c}" fill-opacity="{0.14 if color else 0.06}" '
                  f'stroke="{c}" stroke-opacity="{0.9 if color else 0.5}" stroke-width="1.4"{dash}/>')
    self.p.append(f'<text x="{x + w/2}" y="{y + h/2 + 4.5}" font-size="12" text-anchor="middle" fill="currentColor" font-weight="600">{esc(txt)}</text>')


def _node(self, x, y, w, name, kind, sub=None, num=None, h=None):
    h = h or (40 if sub else 34)
    if num:
        self.box(x, y, w, h, "", (), color=KIND.get(kind))
        self.p.append(f'<text x="{x + w / 2 + 9}" y="{y + h / 2 + 5}" font-size="13" text-anchor="middle" '
                      f'fill="currentColor" font-weight="650" {MONOF}>{esc(name)}</text>')
        self._num(x + 13, y + h / 2, num)
    else:
        self.box(x, y, w, h, name, (sub,) if sub else (), color=KIND.get(kind), mono=True)
    return h


def _seg(self, pts, color=None, dashed=False, arrow=True):
    c = color or "currentColor"
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    sfx = {None: "a", ORANGE: "o", GREEN: "n"}.get(color, "a")
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    mk = f' marker-end="url(#{self.pid}-{sfx})"' if arrow else ""
    self.p.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-opacity="{0.55 if dashed else 0.8}" stroke-width="1.5"{dash}{mk}/>')


def _ebox(self, x, y, w, title, groups, mono_title=True):
    lines = []
    for label, fields in groups:
        if label:
            lines.append(("label", label))
        lines += [("field", f) for f in fields]
    h = 28 + len(lines) * 16 + 6
    self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="currentColor" fill-opacity="0.04" '
                  f'stroke="currentColor" stroke-opacity="0.45" stroke-width="1.4"/>')
    f = MONOF if mono_title else ""
    self.p.append(f'<text x="{x + 12}" y="{y + 20}" font-size="13" text-anchor="start" fill="currentColor" font-weight="700" {f}>{esc(title)}</text>')
    yy = y + 20
    for kind, t in lines:
        yy += 16
        if kind == "label":
            self.p.append(f'<text x="{x + 12}" y="{yy}" font-size="10.5" text-anchor="start" fill="currentColor" fill-opacity="0.5" {MONOF}>{esc(t)}</text>')
        else:
            self.p.append(f'<text x="{x + 22}" y="{yy}" font-size="11" text-anchor="start" fill="currentColor" fill-opacity="0.88" {MONOF}>{esc(t)}</text>')
    return h


def _ibox(self, x, y, w, title, lines, num):
    h = 30 + len(lines) * 16 + 6
    self.p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="currentColor" fill-opacity="0.04" '
                  f'stroke="{ORANGE}" stroke-opacity="0.6" stroke-width="1.4"/>')
    self._num(x + 16, y + 16, num)
    self.p.append(f'<text x="{x + 32}" y="{y + 20}" font-size="12.5" text-anchor="start" fill="currentColor" font-weight="700">{esc(title)}</text>')
    for i, t in enumerate(lines):
        self.p.append(f'<text x="{x + 14}" y="{y + 38 + i * 16}" font-size="11" text-anchor="start" fill="currentColor" fill-opacity="0.85">{esc(t)}</text>')
    return h


Svg._num, Svg.pill, Svg.node, Svg.seg, Svg.ebox, Svg.ibox = _num, _pill, _node, _seg, _ebox, _ibox
