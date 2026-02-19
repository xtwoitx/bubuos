"""BubuOS sound effects manager — cute pixel UI sounds via pygame.mixer."""

import json
import math
import os
import array

import pygame

# Sound event names
NAVIGATE = "navigate"
CONFIRM = "confirm"
BACK = "back"
LAUNCH = "launch"
ERROR = "error"
STARTUP = "startup"
EAT = "eat"


class SFXManager:
    """Manages UI sound effects with on/off toggle and persistence."""

    def __init__(self, data_dir):
        self._config_path = os.path.join(data_dir, ".sfx_config.json")
        self._sounds = {}
        self._enabled = True
        self._available = True
        self._load_config()
        self._sample_rate = 44100
        self._channels = 2
        self._init_mixer()
        if self._available:
            self._generate_sounds()

    def _init_mixer(self):
        try:
            init = pygame.mixer.get_init()
            if not init:
                pygame.mixer.init()
                init = pygame.mixer.get_init()
            if init:
                self._sample_rate = init[0]
                self._channels = init[2]
            else:
                self._available = False
        except Exception:
            self._available = False

    def _load_config(self):
        try:
            with open(self._config_path) as f:
                self._enabled = json.load(f).get("enabled", True)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def _save_config(self):
        try:
            with open(self._config_path, "w") as f:
                json.dump({"enabled": self._enabled}, f)
        except OSError:
            pass

    def _make_tone(self, freq, duration_ms, volume=0.3, freq2=None, decay=8.0):
        """Generate a plucky music-box tone with soft octave harmonic."""
        sr = self._sample_rate
        ch = self._channels
        n = int(sr * duration_ms / 1000)
        buf = array.array("h", [0] * (n * ch))
        attack = min(n, int(sr * 0.004))
        for i in range(n):
            t = i / sr
            f = freq + (freq2 - freq) * i / n if freq2 else freq
            # Sine + soft octave harmonic for music-box warmth
            val = math.sin(2 * math.pi * f * t)
            val += 0.25 * math.sin(2 * math.pi * f * 2 * t)
            # Plucky envelope: fast attack, exponential decay
            if attack > 0 and i < attack:
                env = i / attack
            else:
                env = math.exp(-(i - attack) / sr * decay)
            val *= env
            sample = max(-32767, min(32767, int(val * volume * 32767)))
            for c in range(ch):
                buf[i * ch + c] = sample
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _make_melody(self, notes, volume=0.3):
        """Generate melody from [(freq_hz, duration_ms), ...] list."""
        sr = self._sample_rate
        ch = self._channels
        gap = int(sr * 0.025)  # 25ms gap between notes
        total = sum(int(sr * d / 1000) + gap for _, d in notes)
        buf = array.array("h", [0] * (total * ch))
        pos = 0
        for freq, dur_ms in notes:
            n = int(sr * dur_ms / 1000)
            attack = min(n, int(sr * 0.004))
            for i in range(n):
                t = i / sr
                val = math.sin(2 * math.pi * freq * t)
                val += 0.25 * math.sin(2 * math.pi * freq * 2 * t)
                if attack > 0 and i < attack:
                    env = i / attack
                else:
                    env = math.exp(-(i - attack) / sr * 5.0)
                val *= env
                sample = max(-32767, min(32767, int(val * volume * 32767)))
                for c in range(ch):
                    buf[(pos + i) * ch + c] = sample
            pos += n + gap
        return pygame.mixer.Sound(buffer=bytes(buf))

    def _generate_sounds(self):
        # Gentle navigate blip — tiny high-pitched pip
        self._sounds[NAVIGATE] = self._make_tone(1100, 40, 0.2, decay=12.0)
        # Happy confirm chirp — ascending C5 → E5
        self._sounds[CONFIRM] = self._make_melody([
            (523, 55), (659, 75),
        ], 0.3)
        # Soft back — gentle descending tone
        self._sounds[BACK] = self._make_tone(580, 60, 0.25, freq2=400, decay=10.0)
        # App launch — quick ascending C5 → E5 → G5
        self._sounds[LAUNCH] = self._make_melody([
            (523, 55), (659, 55), (784, 85),
        ], 0.3)
        # Error — two soft low notes E4 → C4
        self._sounds[ERROR] = self._make_melody([
            (330, 80), (262, 100),
        ], 0.3)
        # Eat / chomp — two quick low notes like "am-nyam"
        self._sounds[EAT] = self._make_melody([
            (330, 45), (220, 55),
        ], 0.35)
        # Startup jingle — music-box arpeggio G4 → C5 → E5 → G5 → C6
        self._sounds[STARTUP] = self._make_melody([
            (392, 110),   # G4
            (523, 110),   # C5
            (659, 110),   # E5
            (784, 130),   # G5
            (1047, 220),  # C6
        ], 0.35)

    def play(self, sound_name):
        if self._enabled and self._available:
            snd = self._sounds.get(sound_name)
            if snd:
                try:
                    snd.play()
                except Exception:
                    pass

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = bool(value)
        self._save_config()

    def toggle(self):
        self.enabled = not self._enabled
        if self._enabled:
            self.play(CONFIRM)
