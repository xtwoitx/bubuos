"""BubuOS Calendar — month view with event organizer."""

import calendar
import datetime
import json
import os

import pygame

from core.app import App
from core.input_handler import Action
from core import theme
from core.widgets import ConfirmDialog

VIEW_MONTH = 0
VIEW_DAY = 1


def _evt_text(evt):
    """Get text from event (supports old str and new dict format)."""
    if isinstance(evt, dict):
        return evt.get("text", "")
    return str(evt)


def _evt_done(evt):
    """Check if event is marked done."""
    if isinstance(evt, dict):
        return evt.get("done", False)
    return False


def _make_evt(text, done=False):
    """Create event dict."""
    return {"text": text, "done": done}


def load_events_file(path):
    """Load events from JSON, migrating old string format."""
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception:
        return {}
    # Migrate old string entries to dict format
    for key, evts in data.items():
        for i, evt in enumerate(evts):
            if isinstance(evt, str):
                evts[i] = _make_evt(evt)
    return data


def has_pending_today(path):
    """Check if there are pending (not done) events for today. Used by shell."""
    events = load_events_file(path)
    today_key = datetime.date.today().isoformat()
    for evt in events.get(today_key, []):
        if not _evt_done(evt):
            return True
    return False


class CalendarApp(App):
    """Calendar with event management."""

    name = "Calendar"

    def __init__(self, system):
        super().__init__(system)
        today = datetime.date.today()
        self.year = today.year
        self.month = today.month
        self.selected_day = today.day

        self.view = VIEW_MONTH
        self.events = {}
        self._events_path = os.path.join(
            system.data_dir, "calendar", "events.json")

        # Day view state
        self.day_selected = 0

        # Confirm dialog for deletion
        self._confirm = ConfirmDialog("Delete", "Delete this event?")

        self._load_events()

    def on_enter(self):
        today = datetime.date.today()
        self.year = today.year
        self.month = today.month
        self.selected_day = today.day
        self.view = VIEW_MONTH
        self._load_events()

    # --- Events persistence ---

    def _load_events(self):
        self.events = load_events_file(self._events_path)

    def _save_events(self):
        os.makedirs(os.path.dirname(self._events_path), exist_ok=True)
        with open(self._events_path, "w") as f:
            json.dump(self.events, f)

    def _date_key(self):
        return f"{self.year:04d}-{self.month:02d}-{self.selected_day:02d}"

    def _day_events(self):
        return self.events.get(self._date_key(), [])

    def _has_pending(self, date_key):
        """Check if date has any pending (not done) events."""
        for evt in self.events.get(date_key, []):
            if not _evt_done(evt):
                return True
        return False

    # --- Calendar helpers ---

    def _days_in_month(self):
        return calendar.monthrange(self.year, self.month)[1]

    def _first_weekday(self):
        return calendar.monthrange(self.year, self.month)[0]

    def _change_month(self, delta):
        self.month += delta
        if self.month > 12:
            self.month = 1
            self.year += 1
        elif self.month < 1:
            self.month = 12
            self.year -= 1
        self.selected_day = min(self.selected_day, self._days_in_month())

    # --- Keyboard callbacks ---

    def _on_add_event(self, text):
        text = text.strip()
        if not text:
            return
        key = self._date_key()
        if key not in self.events:
            self.events[key] = []
        self.events[key].append(_make_evt(text))
        self._save_events()

    def _on_edit_event(self, text):
        text = text.strip()
        evts = self._day_events()
        if not text or self.day_selected >= len(evts):
            return
        key = self._date_key()
        self.events[key][self.day_selected]["text"] = text
        self._save_events()

    def _delete_selected_event(self):
        key = self._date_key()
        evts = self.events.get(key, [])
        if self.day_selected < len(evts):
            evts.pop(self.day_selected)
            if not evts:
                self.events.pop(key, None)
            self._save_events()
            if self.day_selected >= len(self._day_events()):
                self.day_selected = max(0, len(self._day_events()) - 1)

    def _toggle_done(self):
        key = self._date_key()
        evts = self.events.get(key, [])
        if self.day_selected < len(evts):
            evts[self.day_selected]["done"] = not _evt_done(evts[self.day_selected])
            self._save_events()

    # --- Input ---

    def handle_input(self, action):
        if self._confirm.active:
            self._confirm.handle_input(action)
            return True

        if self.view == VIEW_MONTH:
            return self._handle_month(action)
        else:
            return self._handle_day(action)

    def _handle_month(self, action):
        if action == Action.LEFT:
            self.selected_day -= 1
            if self.selected_day < 1:
                self._change_month(-1)
                self.selected_day = self._days_in_month()
            return True
        elif action == Action.RIGHT:
            self.selected_day += 1
            if self.selected_day > self._days_in_month():
                self._change_month(1)
                self.selected_day = 1
            return True
        elif action == Action.UP:
            self.selected_day -= 7
            if self.selected_day < 1:
                old = self.selected_day
                self._change_month(-1)
                self.selected_day = self._days_in_month() + old
                if self.selected_day < 1:
                    self.selected_day = 1
            return True
        elif action == Action.DOWN:
            self.selected_day += 7
            dim = self._days_in_month()
            if self.selected_day > dim:
                overflow = self.selected_day - dim
                self._change_month(1)
                self.selected_day = min(overflow, self._days_in_month())
            return True
        elif action == Action.PAGE_UP:
            self._change_month(-1)
            return True
        elif action == Action.PAGE_DOWN:
            self._change_month(1)
            return True
        elif action == Action.CONFIRM:
            self.view = VIEW_DAY
            self.day_selected = 0
            return True
        elif action == Action.SYSTEM:
            self.system.open_keyboard(
                self._on_add_event, title="New event")
            return True
        elif action == Action.BACK:
            self.system.back()
            return True
        return False

    def _handle_day(self, action):
        evts = self._day_events()
        if action == Action.UP:
            if evts:
                self.day_selected = max(0, self.day_selected - 1)
            return True
        elif action == Action.DOWN:
            if evts:
                self.day_selected = min(len(evts) - 1, self.day_selected + 1)
            return True
        elif action == Action.CONFIRM:
            if evts and self.day_selected < len(evts):
                self.system.open_keyboard(
                    self._on_edit_event,
                    initial_text=_evt_text(evts[self.day_selected]),
                    title="Edit event")
            return True
        elif action == Action.MENU:
            # X → toggle done
            if evts and self.day_selected < len(evts):
                self._toggle_done()
            return True
        elif action == Action.SYSTEM:
            self.system.open_keyboard(
                self._on_add_event, title="New event")
            return True
        elif action == Action.DELETE:
            if evts and self.day_selected < len(evts):
                self._confirm.on_confirm = self._delete_selected_event
                self._confirm.on_cancel = None
                self._confirm.message = f'Delete "{_evt_text(evts[self.day_selected])}"?'
                self._confirm.open()
            return True
        elif action == Action.BACK:
            self.view = VIEW_MONTH
            return True
        return False

    # --- Draw ---

    def draw(self):
        if self.view == VIEW_MONTH:
            self._draw_month()
        else:
            self._draw_day()
        self._confirm.draw(self.system.renderer)

    def _draw_month(self):
        r = self.system.renderer
        font = theme.get_font(theme.FONT_SIZE)
        font_sm = theme.get_font(theme.FONT_SMALL)
        cw, ch = theme.get_char_size()

        month_name = calendar.month_name[self.month]
        r.draw_statusbar(f"  {month_name} {self.year}", "")

        today = datetime.date.today()
        is_current_month = (self.year == today.year
                            and self.month == today.month)

        # Day-of-week headers
        y = theme.CONTENT_TOP + 8
        days_header = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        cell_w = (theme.SCREEN_WIDTH - theme.PADDING * 2) // 7

        for i, dh in enumerate(days_header):
            dx = (theme.PADDING + i * cell_w
                  + (cell_w - font_sm.size(dh)[0]) // 2)
            color = theme.SALMON if i >= 5 else theme.TEXT_DIM
            r.draw_text(dh, dx, y, color=color, size=theme.FONT_SMALL)

        y += ch + 4

        # Calendar grid
        first_wd = self._first_weekday()
        dim = self._days_in_month()
        cell_h = ch + 10

        col = first_wd
        row_y = y

        for day in range(1, dim + 1):
            cx = theme.PADDING + col * cell_w
            day_str = str(day)
            tw = font.size(day_str)[0]
            tx = cx + (cell_w - tw) // 2
            ty = row_y + 2

            is_today = is_current_month and day == today.day
            is_selected = day == self.selected_day
            dkey = f"{self.year:04d}-{self.month:02d}-{day:02d}"
            has_events = dkey in self.events and len(self.events[dkey]) > 0
            has_pending = self._has_pending(dkey)

            # Dot color: salmon if pending, dim if all done
            dot_color_normal = theme.SALMON if has_pending else theme.WARM_GRAY

            if is_selected:
                pygame.draw.rect(r.screen, theme.SALMON,
                                 (cx + 2, row_y + 1,
                                  cell_w - 4, cell_h - 2))
                r.draw_text(day_str, tx, ty, color=theme.WHITE)
                if has_events:
                    dot_y = ty + ch - 2
                    dot_x = cx + cell_w // 2
                    pygame.draw.circle(r.screen, theme.WHITE,
                                       (dot_x, dot_y), 3)
            elif is_today:
                pygame.draw.rect(r.screen, theme.WARM_BROWN,
                                 (cx + 2, row_y + 1,
                                  cell_w - 4, cell_h - 2), 1)
                r.draw_text(day_str, tx, ty, color=theme.TEXT_COLOR)
                if has_events:
                    dot_y = ty + ch - 2
                    dot_x = cx + cell_w // 2
                    pygame.draw.circle(r.screen, dot_color_normal,
                                       (dot_x, dot_y), 3)
            else:
                color = theme.SALMON if col >= 5 else theme.TEXT_COLOR
                r.draw_text(day_str, tx, ty, color=color)
                if has_events:
                    dot_y = ty + ch - 2
                    dot_x = cx + cell_w // 2
                    pygame.draw.circle(r.screen, dot_color_normal,
                                       (dot_x, dot_y), 3)

            col += 1
            if col > 6:
                col = 0
                row_y += cell_h

        # Event preview for selected day
        evts = self._day_events()
        preview_y = theme.CONTENT_BOTTOM - ch * 3 - 4
        sel_date = datetime.date(self.year, self.month, self.selected_day)
        date_label = sel_date.strftime("%a, %b %d")

        r.draw_text(date_label, theme.PADDING, preview_y,
                     color=theme.ACCENT, size=theme.FONT_SMALL)
        preview_y += ch

        if evts:
            shown = evts[:2]
            for ev in shown:
                txt = _evt_text(ev)
                done = _evt_done(ev)
                prefix = "[v] " if done else "    "
                display = prefix + txt
                if len(display) > 50:
                    display = display[:47] + "..."
                color = theme.WARM_GRAY if done else theme.TEXT_DIM
                r.draw_text(display, theme.PADDING, preview_y,
                             color=color, size=theme.FONT_SMALL)
                preview_y += ch
            if len(evts) > 2:
                r.draw_text(f"    +{len(evts) - 2} more", theme.PADDING,
                             preview_y, color=theme.WARM_GRAY,
                             size=theme.FONT_SMALL)
        else:
            r.draw_text("    No events", theme.PADDING, preview_y,
                         color=theme.WARM_GRAY, size=theme.FONT_SMALL)

        r.draw_helpbar([
            ("A", "View"), ("L/R", "Month"),
            ("St", "Add"), ("B", "Back"),
        ])

    def _draw_day(self):
        r = self.system.renderer
        font = theme.get_font(theme.FONT_SIZE)
        _, ch = theme.get_char_size()

        sel_date = datetime.date(self.year, self.month, self.selected_day)
        r.draw_statusbar(f"  {sel_date.strftime('%a, %b %d %Y')}", "")

        evts = self._day_events()
        y = theme.CONTENT_TOP + 8

        if not evts:
            r.draw_text("No events", theme.PADDING, y,
                         color=theme.WARM_GRAY)
            r.draw_text("Press Start to add one",
                         theme.PADDING, y + ch,
                         color=theme.WARM_GRAY)
        else:
            max_vis = (theme.CONTENT_BOTTOM - y) // ch
            for i, ev in enumerate(evts[:max_vis]):
                txt = _evt_text(ev)
                done = _evt_done(ev)
                check = "[v]" if done else "[ ]"
                display = f"{check} {txt}"
                if len(display) > 55:
                    display = display[:52] + "..."

                if i == self.day_selected:
                    r.draw_row(f" {display}", y,
                               fg=theme.HIGHLIGHT_TEXT,
                               bg=theme.HIGHLIGHT_BG)
                else:
                    color = theme.WARM_GRAY if done else theme.TEXT_COLOR
                    r.draw_text(f" {display}", theme.PADDING, y,
                                 color=color)
                y += ch

        r.draw_helpbar([
            ("A", "Edit"), ("X", "Done"),
            ("St", "Add"), ("Y", "Del"), ("B", "Back"),
        ])
