import json
import os
from pathlib import Path

DATA_DIR = Path("data")


def _get_filepath(guild_id: int, thread_id: int) -> Path:
    """Returns local JSON path using thread_id as unique key."""
    DATA_DIR.mkdir(exist_ok=True)
    return DATA_DIR / f"{guild_id}_{thread_id}.json"


def load_tournament_by_thread(guild_id: int, thread_id: int) -> dict | None:
    """Loads tournament state associated with a thread."""
    filepath = _get_filepath(guild_id, thread_id)
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tournament_by_thread(guild_id: int, thread_id: int, data: dict) -> None:
    """Saves tournament state keyed by thread ID."""
    filepath = _get_filepath(guild_id, thread_id)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def delete_tournament_by_thread(guild_id: int, thread_id: int) -> bool:
    """Deletes local JSON storage when a tournament thread is removed."""
    filepath = _get_filepath(guild_id, thread_id)
    if filepath.exists():
        os.remove(filepath)
        return True
    return False