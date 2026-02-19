"""BubuOS input handler — maps physical buttons to abstract actions."""

import pygame
from enum import Enum, auto


class Action(Enum):
    """Abstract input actions."""
    NONE = auto()
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    CONFIRM = auto()      # A button / Enter
    BACK = auto()          # B button / Escape
    MENU = auto()          # X button / Tab
    DELETE = auto()        # Y button / Delete
    SYSTEM = auto()        # Start button / F1
    SWITCH_LAYOUT = auto() # Select button / F2
    PAGE_UP = auto()       # L button / PageUp
    PAGE_DOWN = auto()     # R button / PageDown
    SCREENSHOT = auto()    # Function/+ button / F5
    QUIT = auto()          # Window close


# Keyboard mapping (for development on desktop)
KEY_MAP = {
    pygame.K_UP: Action.UP,
    pygame.K_DOWN: Action.DOWN,
    pygame.K_LEFT: Action.LEFT,
    pygame.K_RIGHT: Action.RIGHT,
    pygame.K_RETURN: Action.CONFIRM,
    pygame.K_ESCAPE: Action.BACK,
    pygame.K_TAB: Action.MENU,
    pygame.K_DELETE: Action.DELETE,
    pygame.K_BACKSPACE: Action.DELETE,
    pygame.K_F1: Action.SYSTEM,
    pygame.K_F2: Action.SWITCH_LAYOUT,
    pygame.K_PAGEUP: Action.PAGE_UP,
    pygame.K_PAGEDOWN: Action.PAGE_DOWN,
    pygame.K_F5: Action.SCREENSHOT,
}

# GPi Case 2 gamepad button mapping
# The GPi Case 2 maps buttons as a USB gamepad (joystick)
# These indices may vary — adjust after testing on real hardware
GAMEPAD_BUTTON_MAP = {
    0: Action.CONFIRM,        # A
    1: Action.BACK,            # B
    2: Action.MENU,            # X
    3: Action.DELETE,          # Y
    4: Action.PAGE_UP,         # L
    5: Action.PAGE_DOWN,       # R
    6: Action.SWITCH_LAYOUT,   # Select
    7: Action.SYSTEM,          # Start
    8: Action.SCREENSHOT,      # Function / +
}

# D-pad via hat (POV)
HAT_MAP = {
    (0, 1): Action.UP,
    (0, -1): Action.DOWN,
    (-1, 0): Action.LEFT,
    (1, 0): Action.RIGHT,
}


class InputHandler:
    """Processes pygame events and returns abstract actions."""

    def __init__(self):
        self.joystick = None
        self._init_joystick()

    def _init_joystick(self):
        """Initialize the first available joystick (GPi Case 2 gamepad)."""
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

    def poll(self):
        """Process all pending events and return a list of Actions."""
        actions = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                actions.append(Action.QUIT)

            # Keyboard (desktop dev)
            elif event.type == pygame.KEYDOWN:
                action = KEY_MAP.get(event.key, Action.NONE)
                if action != Action.NONE:
                    actions.append(action)

            # Gamepad buttons
            elif event.type == pygame.JOYBUTTONDOWN:
                action = GAMEPAD_BUTTON_MAP.get(event.button, Action.NONE)
                if action != Action.NONE:
                    actions.append(action)

            # D-pad (hat)
            elif event.type == pygame.JOYHATMOTION:
                action = HAT_MAP.get(event.value, Action.NONE)
                if action != Action.NONE:
                    actions.append(action)

        return actions
