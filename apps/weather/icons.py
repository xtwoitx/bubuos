"""Programmatic pixel-art weather icons (48x48 RGBA surfaces)."""

import math
import pygame

# Warm palette matching BubuOS theme
SUN_YELLOW = (255, 210, 80)
SUN_CORE = (255, 185, 60)
CLOUD_LIGHT = (215, 215, 220)
CLOUD_DARK = (175, 175, 185)
CLOUD_STORM = (105, 105, 120)
RAIN_BLUE = (110, 165, 235)
SNOW_WHITE = (235, 235, 250)
BOLT_YELLOW = (255, 235, 100)
FOG_GRAY = (185, 180, 175)
WIND_TEAL = (135, 195, 195)

SIZE = 48

# WMO code → icon key (for use by app.py)
WMO_TO_ICON = {
    0: "sun",
    1: "partly_cloudy", 2: "partly_cloudy", 3: "cloudy",
    45: "fog", 48: "fog",
    51: "rain", 53: "rain", 55: "rain", 56: "rain", 57: "rain",
    61: "rain", 63: "heavy_rain", 65: "heavy_rain",
    66: "rain", 67: "heavy_rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rain", 81: "rain", 82: "heavy_rain",
    85: "snow", 86: "snow",
    95: "thunder", 96: "thunder", 99: "thunder",
}


def _surf():
    return pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)


def _sun(s, cx, cy, r, ray):
    """Sun: filled circle + 8 rays."""
    pygame.draw.circle(s, SUN_YELLOW, (cx, cy), r)
    pygame.draw.circle(s, SUN_CORE, (cx, cy), r - 2)
    for deg in range(0, 360, 45):
        a = math.radians(deg)
        x1 = cx + int((r + 2) * math.cos(a))
        y1 = cy + int((r + 2) * math.sin(a))
        x2 = cx + int((r + 2 + ray) * math.cos(a))
        y2 = cy + int((r + 2 + ray) * math.sin(a))
        pygame.draw.line(s, SUN_YELLOW, (x1, y1), (x2, y2), 3)


def _cloud(s, cx, cy, col=CLOUD_LIGHT, sc=1.0):
    """Puffy cloud from overlapping circles."""
    def c(dx, dy, r):
        pygame.draw.circle(s, col, (cx + int(dx * sc), cy + int(dy * sc)), int(r * sc))
    c(0, 0, 10)
    c(-10, 3, 8)
    c(10, 3, 8)
    c(5, -5, 7)
    pygame.draw.rect(s, col, (
        cx - int(18 * sc), cy + int(2 * sc),
        int(36 * sc), int(10 * sc)))


def _drops(s, x0, y0, n, col=RAIN_BLUE):
    """Diagonal rain drops."""
    sp = 36 // max(n, 1)
    for i in range(n):
        x = x0 + 6 + i * sp
        pygame.draw.line(s, col, (x, y0), (x - 3, y0 + 8), 2)


def _icon_sun():
    s = _surf()
    _sun(s, 24, 24, 10, 7)
    return s


def _icon_partly_cloudy():
    s = _surf()
    _sun(s, 32, 14, 8, 5)
    _cloud(s, 20, 28, CLOUD_LIGHT, 1.1)
    return s


def _icon_cloudy():
    s = _surf()
    _cloud(s, 28, 20, CLOUD_DARK, 0.9)
    _cloud(s, 20, 28, CLOUD_LIGHT, 1.1)
    return s


def _icon_rain():
    s = _surf()
    _cloud(s, 24, 16)
    _drops(s, 6, 30, 3)
    return s


def _icon_heavy_rain():
    s = _surf()
    _cloud(s, 24, 14, CLOUD_DARK)
    _drops(s, 4, 28, 5)
    return s


def _icon_snow():
    s = _surf()
    _cloud(s, 24, 16)
    for sx, sy in [(12, 34), (24, 38), (36, 34)]:
        pygame.draw.circle(s, SNOW_WHITE, (sx, sy), 3)
        for dx, dy in [(-4, 0), (4, 0), (0, -4), (0, 4)]:
            pygame.draw.line(s, SNOW_WHITE, (sx, sy), (sx + dx, sy + dy), 1)
    return s


def _icon_thunder():
    s = _surf()
    _cloud(s, 24, 14, CLOUD_STORM, 1.1)
    bolt = [(22, 26), (26, 26), (23, 34), (28, 34), (20, 46), (25, 36), (21, 36)]
    pygame.draw.polygon(s, BOLT_YELLOW, bolt)
    return s


def _icon_fog():
    s = _surf()
    for i, (y, a) in enumerate([(14, 180), (22, 220), (30, 200), (38, 160)]):
        off = (i % 2) * 4
        pygame.draw.line(s, (*FOG_GRAY, a), (6 + off, y), (42 - off, y), 3)
    return s


def _icon_wind():
    s = _surf()
    for i, yb in enumerate([16, 26, 36]):
        pts = []
        length = 36 - i * 4
        x0 = 6 + i * 2
        for x in range(x0, x0 + length):
            pts.append((x, yb + int(2 * math.sin(x * 0.3 + i))))
        if len(pts) >= 2:
            pygame.draw.lines(s, WIND_TEAL, False, pts, 2)
        if pts:
            lx, ly = pts[-1]
            pygame.draw.arc(s, WIND_TEAL, (lx - 3, ly - 4, 8, 8), -1.5, 1.0, 2)
    return s


_BUILDERS = {
    "sun": _icon_sun,
    "partly_cloudy": _icon_partly_cloudy,
    "cloudy": _icon_cloudy,
    "rain": _icon_rain,
    "heavy_rain": _icon_heavy_rain,
    "snow": _icon_snow,
    "thunder": _icon_thunder,
    "fog": _icon_fog,
    "wind": _icon_wind,
}

_cache = {}


def get_weather_icon(key):
    """Get 48x48 weather icon Surface (cached)."""
    if key not in _cache:
        builder = _BUILDERS.get(key, _icon_sun)
        _cache[key] = builder()
    return _cache[key]
