"""BubuOS base application class."""

from core.input_handler import Action


class App:
    """Base class for all BubuOS applications.

    Every app must implement handle_input() and draw().
    """

    name = "Untitled"
    help_items = []  # List of (key_label, description) for the help bar

    def __init__(self, system):
        """Initialize the app with a reference to the system (main loop).

        system provides:
            system.screen       — pygame Surface
            system.renderer     — Renderer instance
            system.input        — InputHandler instance
            system.open_app(app) — switch to another app
            system.back()       — return to previous app / shell
            system.open_keyboard(callback, initial_text) — open on-screen keyboard
            system.data_dir     — path to user data directory
        """
        self.system = system

    def on_enter(self):
        """Called when this app becomes the active app."""
        pass

    def on_exit(self):
        """Called when leaving this app."""
        pass

    def handle_input(self, action):
        """Handle an abstract input action. Return True if handled."""
        return False

    def update(self, dt):
        """Update logic. dt is delta time in seconds."""
        pass

    def draw(self):
        """Draw the app's content to the screen."""
        pass
