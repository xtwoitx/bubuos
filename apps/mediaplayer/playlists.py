"""Playlist management — JSON-based storage in ~/data/playlists/."""

import json
import os


def list_playlists(playlists_dir):
    """Return sorted list of (name, path) for all playlists."""
    os.makedirs(playlists_dir, exist_ok=True)
    result = []
    try:
        for fn in sorted(os.listdir(playlists_dir)):
            if fn.endswith(".json"):
                name = fn[:-5]
                result.append((name, os.path.join(playlists_dir, fn)))
    except OSError:
        pass
    return result


def load_playlist(path):
    """Load track list from a playlist JSON file."""
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("tracks", [])
    except (OSError, json.JSONDecodeError, KeyError):
        return []


def save_playlist(path, tracks):
    """Save track list to a playlist JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"tracks": tracks}, f)


def delete_playlist(path):
    """Delete a playlist file."""
    try:
        os.remove(path)
    except OSError:
        pass
