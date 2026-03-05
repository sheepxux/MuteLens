"""
Mutelens - Badge SVG Generator
================================
Generates premium certification badge SVGs in different styles.
Uses unified brand color (burnt orange) across all grades.
"""

import html

BRAND_COLOR = "#fc6011"
BRAND_COLOR_LIGHT = "#ff8a47"
BRAND_BG = "#2d1a0e"


def generate_badge_svg(
    score: float, grade: str, title: str = "", style: str = "flat"
) -> str:
    if style == "seal":
        return _generate_seal(score, grade, title)
    return _generate_flat(score, grade)


def _generate_flat(score: float, grade: str) -> str:
    score_int = int(round(score))
    right_text = f"{score_int} · {grade}"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="190" height="28" viewBox="0 0 190 28" role="img" aria-label="MuteLens Score: {score_int} ({grade})">
  <title>MuteLens Score: {score_int} ({grade})</title>
  <defs>
    <linearGradient id="left-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1e1e2e"/>
      <stop offset="100%" stop-color="#15151f"/>
    </linearGradient>
    <linearGradient id="right-bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{BRAND_COLOR}"/>
      <stop offset="100%" stop-color="#d4500e"/>
    </linearGradient>
  </defs>
  <rect width="190" height="28" rx="6" fill="url(#left-bg)"/>
  <rect x="100" width="90" height="28" rx="0" fill="url(#right-bg)"/>
  <rect x="184" width="6" height="28" rx="6" fill="url(#right-bg)"/>
  <g fill="#fff" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" text-rendering="geometricPrecision">
    <g opacity="0.9">
      <text x="14" y="17.5" font-size="11" font-weight="600" letter-spacing="0.3">MuteLens</text>
      <circle cx="84" cy="14" r="2.5" fill="{BRAND_COLOR}" opacity="0.8"/>
    </g>
    <text x="145" y="17.5" font-size="11.5" font-weight="700" text-anchor="middle" letter-spacing="0.5">{right_text}</text>
  </g>
</svg>'''


def _generate_seal(score: float, grade: str, title: str = "") -> str:
    score_int = int(round(score))
    safe_title = html.escape(title[:40] + "\u2026" if len(title) > 40 else title) if title else ""

    title_row = ""
    if safe_title:
        title_row = f'<text x="120" y="135" font-size="9" fill="#fff" fill-opacity="0.4" text-anchor="middle" font-weight="400">{safe_title}</text>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="240" height="155" viewBox="0 0 240 155" role="img" aria-label="MuteLens Certified: {score_int} ({grade})">
  <title>MuteLens Certified: {score_int} ({grade})</title>
  <defs>
    <linearGradient id="card-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0d0d14"/>
      <stop offset="100%" stop-color="{BRAND_BG}"/>
    </linearGradient>
    <linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{BRAND_COLOR_LIGHT}"/>
      <stop offset="100%" stop-color="{BRAND_COLOR}"/>
    </linearGradient>
  </defs>
  <rect width="240" height="155" rx="12" fill="url(#card-bg)" stroke="{BRAND_COLOR}" stroke-opacity="0.2" stroke-width="1"/>

  <g font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" text-rendering="geometricPrecision">
    <text x="120" y="28" font-size="10" fill="#fff" fill-opacity="0.3" text-anchor="middle" font-weight="600" letter-spacing="2.5" textLength="100">MUTELENS</text>
    <text x="120" y="40" font-size="7.5" fill="{BRAND_COLOR}" fill-opacity="0.7" text-anchor="middle" letter-spacing="1">CERTIFIED</text>
  </g>

  <circle cx="120" cy="78" r="28" fill="none" stroke="#fff" stroke-opacity="0.06" stroke-width="3"/>
  <circle cx="120" cy="78" r="28" fill="none" stroke="url(#ring-grad)" stroke-width="3"
          stroke-dasharray="{score_int * 1.76} 176" stroke-dashoffset="0" stroke-linecap="round"
          transform="rotate(-90 120 78)"/>

  <g font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" text-rendering="geometricPrecision">
    <text x="120" y="83" font-size="20" fill="#fff" text-anchor="middle" font-weight="700">{score_int}</text>
    <text x="120" y="95" font-size="9" fill="{BRAND_COLOR}" text-anchor="middle" font-weight="600">{grade}</text>
  </g>

  <line x1="40" y1="115" x2="200" y2="115" stroke="{BRAND_COLOR}" stroke-opacity="0.1" stroke-width="0.5"/>
  <text x="120" y="128" font-size="7" fill="#fff" fill-opacity="0.25" text-anchor="middle"
        font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
        letter-spacing="0.5">Verified by MuteLens AI · mutelens.com</text>
  {title_row}
</svg>'''
