"""BubuWeather — current conditions + 5-day forecast."""

import datetime
import math
import os
import time
import threading
import pygame

from core.app import App
from core.input_handler import Action
from core import theme
from apps.weather.api import fetch_weather, fetch_location, geocode_city
from apps.weather.icons import get_weather_icon, WMO_TO_ICON

# Season → animation directory name
_SEASON_ANIM = {
    "winter": "winter_anim",    # Dec, Jan, Feb
    "spring": "updown_anim",    # Mar, Apr, May
    "summer": "fan_anim",       # Jun, Jul, Aug
    "autumn": "raincoat_anim",  # Sep, Oct, Nov
}

# Heavy-rain icon keys that trigger raincoat override
_RAINY_ICONS = {"rain", "heavy_rain", "thunder"}


class WeatherApp(App):
    name = "BubuWeather"

    REFRESH_INTERVAL = 30 * 60  # 30 minutes

    def __init__(self, system):
        super().__init__(system)

        self.state = "loading"  # loading | ready | error
        self.error_text = ""
        self._fetching = False

        # Location
        self.city_name = ""
        self.latitude = None
        self.longitude = None
        self._manual_city = None

        # Weather data
        self.current = {}
        self.forecast = []

        # Animation — pick based on season (updated after weather loads)
        self._assets_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets"))
        self._anim_dir = self._pick_anim_dir()
        self._anim_frames = None
        self._anim_idx = 0
        self._anim_tick = 0

        # Timing
        self._last_fetch = 0
        self._loading_start = 0
        self._pending_ready = False
        self._MIN_LOADING = 3.0  # seconds

        # Icon cache
        self._icons = {}

    def on_enter(self):
        if self.state == "loading" and not self._fetching:
            self._start_fetch()

    def update(self, dt):
        # Transition from loading → ready after min loading time
        if (self.state == "loading" and self._pending_ready
                and time.time() - self._loading_start >= self._MIN_LOADING):
            self._pending_ready = False
            self.state = "ready"

        # Auto-refresh
        if (self.state == "ready" and not self._fetching
                and time.time() - self._last_fetch > self.REFRESH_INTERVAL):
            self._start_fetch()

        # Animation tick (~6fps at 30fps)
        self._anim_tick += 1
        if self._anim_tick >= 5:
            self._anim_tick = 0
            self._anim_idx += 1

    def handle_input(self, action):
        if self._fetching and action != Action.BACK:
            return True  # block input while fetching

        if action == Action.CONFIRM:
            self._start_fetch()
            return True
        if action == Action.BACK:
            self.system.back()
            return True
        if action == Action.MENU:
            self.system.open_keyboard(
                self._on_city, initial_text=self.city_name or "",
                title="City name:")
            return True
        return False

    def _on_city(self, city):
        if city and city.strip():
            self._manual_city = city.strip()
            self.latitude = None
            self.longitude = None
            self._start_fetch()

    # --- Drawing ---

    def draw(self):
        r = self.system.renderer

        r.draw_statusbar("  BubuWeather", self.city_name or "")

        if self.state == "loading":
            self._draw_loading(r)
        elif self.state == "error":
            self._draw_error(r)
        else:
            self._draw_weather(r)

        r.draw_helpbar([("A", "Refresh"), ("B", "Back"), ("X", "City")])

    def _draw_loading(self, r):
        scr = r.screen
        frame = self._get_frame(r)

        # Center Bubu vertically in content area
        mid_y = (theme.CONTENT_TOP + theme.CONTENT_BOTTOM) // 2
        if frame:
            fx = (theme.SCREEN_WIDTH - frame.get_width()) // 2
            fy = mid_y - frame.get_height() // 2 - 20
            scr.blit(frame, (fx, fy))
            below_y = fy + frame.get_height() + 12
        else:
            below_y = mid_y

        # "Loading" text
        r.draw_text_centered("Loading",
                             below_y, color=theme.ACCENT,
                             size=theme.FONT_SMALL)

        # Progress bar — fills over _MIN_LOADING seconds
        bar_w, bar_h = 160, 6
        bar_x = (theme.SCREEN_WIDTH - bar_w) // 2
        bar_y = below_y + 24
        pygame.draw.rect(scr, theme.BORDER_COLOR,
                         (bar_x, bar_y, bar_w, bar_h), 1)
        elapsed = time.time() - self._loading_start if self._loading_start else 0
        progress = min(1.0, elapsed / self._MIN_LOADING)
        fill_w = int((bar_w - 2) * progress)
        if fill_w > 0:
            pygame.draw.rect(scr, theme.ACCENT,
                             (bar_x + 1, bar_y + 1, fill_w, bar_h - 2))

    def _draw_error(self, r):
        _, ch = theme.get_char_size()
        mid = theme.SCREEN_HEIGHT // 2
        r.draw_text_centered("Could not load weather",
                             mid - ch * 2, color=theme.ERROR_COLOR)
        r.draw_text_centered(self.error_text,
                             mid - ch, color=theme.TEXT_DIM,
                             size=theme.FONT_SMALL)
        r.draw_text_centered("Press A to retry",
                             mid + ch, color=theme.ACCENT,
                             size=theme.FONT_SMALL)

    def _draw_weather(self, r):
        scr = r.screen
        _, ch = theme.get_char_size()
        _, ch_sm = theme.get_char_size(theme.FONT_SMALL)
        y_top = theme.CONTENT_TOP + 8

        # --- Left: Bubu animation ---
        frame = self._get_frame(r)
        anim_w = 0
        if frame:
            scr.blit(frame, (theme.PADDING + 4, y_top))
            anim_w = frame.get_width()

        # --- Right: current weather ---
        info_x = theme.PADDING + anim_w + 20

        # Weather icon + big temperature
        icon = self._get_icon(self.current.get("icon_key", "sun"))
        temp = self.current.get("temp")
        temp_str = f"{temp:.0f}°C" if temp is not None else "--°C"

        icon_y = y_top + 8
        if icon:
            scr.blit(icon, (info_x, icon_y))
        r.draw_text(temp_str, info_x + 56, y_top + 14,
                     color=theme.TEXT_COLOR, size=theme.FONT_LARGE)

        # Condition text
        y_info = y_top + 14 + 40
        r.draw_text(self.current.get("condition", ""),
                     info_x, y_info, color=theme.TEXT_COLOR)

        # Wind & humidity
        y_info += ch + 8
        wind = self.current.get("wind_speed")
        r.draw_text(f"Wind: {wind:.0f} km/h" if wind is not None else "Wind: --",
                     info_x, y_info, color=theme.TEXT_DIM,
                     size=theme.FONT_SMALL)
        y_info += ch_sm + 2
        hum = self.current.get("humidity")
        r.draw_text(f"Humidity: {hum:.0f}%" if hum is not None else "Humidity: --",
                     info_x, y_info, color=theme.TEXT_DIM,
                     size=theme.FONT_SMALL)

        # --- Forecast section ---
        forecast_y = y_top + max(200, (frame.get_height() if frame else 200)) + 16

        # Separator
        pygame.draw.line(scr, theme.BORDER_COLOR,
                         (theme.PADDING, forecast_y),
                         (theme.SCREEN_WIDTH - theme.PADDING, forecast_y))
        forecast_y += 8

        r.draw_text("Forecast", theme.PADDING, forecast_y,
                     color=theme.ACCENT, size=theme.FONT_SMALL)
        forecast_y += ch_sm + 6

        if not self.forecast:
            return

        font_sm = theme.get_font(theme.FONT_SMALL)
        col_w = (theme.SCREEN_WIDTH - theme.PADDING * 2) // 5

        for i, day in enumerate(self.forecast[:5]):
            cx = theme.PADDING + i * col_w + col_w // 2

            # Day name
            name = day["day_name"]
            nw = font_sm.size(name)[0]
            r.draw_text(name, cx - nw // 2, forecast_y,
                         color=theme.TEXT_COLOR, size=theme.FONT_SMALL)

            # Icon (48x48 centered)
            day_icon = self._get_icon(day["icon_key"])
            if day_icon:
                scr.blit(day_icon, (cx - 24, forecast_y + ch_sm + 2))

            # High/Low
            hi = day["high"]
            lo = day["low"]
            temp_txt = f"{hi:.0f}/{lo:.0f}"
            tw = font_sm.size(temp_txt)[0]
            r.draw_text(temp_txt, cx - tw // 2,
                         forecast_y + ch_sm + 52,
                         color=theme.TEXT_DIM, size=theme.FONT_SMALL)

    # --- Helpers ---

    def _pick_anim_dir(self):
        """Choose Bubu animation based on season and weather forecast."""
        month = datetime.date.today().month
        if month in (12, 1, 2):
            season = "winter"
        elif month in (3, 4, 5):
            season = "spring"
        elif month in (6, 7, 8):
            season = "summer"
        else:
            season = "autumn"

        # Override: rainy weather → raincoat (but never override winter)
        if season != "winter":
            cur_icon = self.current.get("icon_key", "")
            if cur_icon in _RAINY_ICONS:
                season = "autumn"
            elif self.forecast:
                rainy = sum(1 for d in self.forecast if d["icon_key"] in _RAINY_ICONS)
                if rainy >= 3:
                    season = "autumn"

        return os.path.join(self._assets_dir, _SEASON_ANIM[season])

    def _update_anim(self):
        """Re-pick animation after weather data changes."""
        new_dir = self._pick_anim_dir()
        if new_dir != self._anim_dir:
            self._anim_dir = new_dir
            self._anim_frames = None  # force reload on next draw

    def _get_frame(self, r):
        if self._anim_frames is None:
            self._anim_frames = r.load_anim(self._anim_dir, target_h=200)
        if self._anim_frames:
            return self._anim_frames[self._anim_idx % len(self._anim_frames)]
        return None

    def _get_icon(self, key):
        if key not in self._icons:
            self._icons[key] = get_weather_icon(key)
        return self._icons[key]

    # --- Data fetching ---

    def _start_fetch(self):
        if self._fetching:
            return
        self._fetching = True
        self._pending_ready = False
        if self.state != "ready":
            self.state = "loading"
            self._loading_start = time.time()
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            # Resolve location
            if self._manual_city:
                result = geocode_city(self._manual_city)
                if result:
                    self.latitude, self.longitude, self.city_name = result
                else:
                    self.error_text = f"City not found: {self._manual_city}"
                    self.state = "error"
                    return
            elif self.latitude is None:
                loc = fetch_location()
                if loc:
                    self.latitude = loc["lat"]
                    self.longitude = loc["lon"]
                    self.city_name = loc["city"]
                else:
                    self.error_text = "Could not detect location"
                    self.state = "error"
                    return

            # Fetch weather
            data = fetch_weather(self.latitude, self.longitude)
            if data:
                self.current = data["current"]
                self.forecast = data["forecast"]
                self._update_anim()
                self._last_fetch = time.time()
                # If already showing ready (refresh), switch immediately
                if self.state == "ready":
                    pass  # stay ready
                else:
                    self._pending_ready = True  # update() will transition after min time
            else:
                self.error_text = "Weather API unavailable"
                self.state = "error"
        except Exception as e:
            self.error_text = str(e)[:50]
            self.state = "error"
        finally:
            self._fetching = False
