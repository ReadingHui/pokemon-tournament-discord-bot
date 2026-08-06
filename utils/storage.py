import json
import os
from pathlib import Path

DATA_DIR = Path("data")


def _get_filepath(guild_id: int, tournament_name: str) -> Path:
    """Helper to generate local JSON path."""
    DATA_DIR.mkdir(exist_ok=True)
    # Sanitize tournament name for safer filenames
    clean_name = "".join(c for c in tournament_name if c.isalnum() or c in ("-", "_")).lower()
    return DATA_DIR / f"{guild_id}_{clean_name}.json"


def load_tournament(guild_id: int, tournament_name: str) -> dict | None:
    """Loads tournament state from disk."""
    filepath = _get_filepath(guild_id, tournament_name)
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tournament(guild_id: int, tournament_name: str, data: dict) -> None:
    """Saves tournament state to disk."""
    filepath = _get_filepath(guild_id, tournament_name)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_tournament(guild_id: int, tournament_name: str, thread_id: int, roster: dict) -> dict:
    """Initializes a new tournament file with thread ID and initial roster."""
    data = {
        "tournament_name": tournament_name,
        "thread_id": thread_id,
        "current_round": 0,
        "players": roster,  # Output from parse_player_list()
        "rounds": {}
    }
    save_tournament(guild_id, tournament_name, data)
    return data


def update_pairings(guild_id: int, tournament_name: str, round_num: str, pairings_data: dict) -> dict:
    """Stores round pairings and updates the current round tracker."""
    data = load_tournament(guild_id, tournament_name)
    if not data:
        raise FileNotFoundError(f"No active tournament found for {tournament_name}")

    data["current_round"] = int(round_num)
    # Merges new round dictionary into the existing rounds structure
    data["rounds"][str(round_num)] = pairings_data[str(round_num)]
    
    save_tournament(guild_id, tournament_name, data)
    return data


def get_player_status(guild_id: int, tournament_name: str, player_name: str) -> dict | None:
    """Queries a player's current round assignment, table number, and record."""
    data = load_tournament(guild_id, tournament_name)
    if not data:
        return None

    current_round = str(data.get("current_round", 0))
    if current_round == "0" or current_round not in data["rounds"]:
        return None

    round_pairings = data["rounds"][current_round]

    # Search through divisions for the player name
    for division, players in round_pairings.items():
        if player_name in players:
            player_info = players[player_name]
            return {
                "round": current_round,
                "division": division,
                "table": player_info["table"],
                "opponent": player_info["opponent"],
                "record": player_info["record"]
            }

    return None


def delete_tournament(guild_id: int, tournament_name: str) -> bool:
    """Deletes the local tournament JSON file upon conclusion."""
    filepath = _get_filepath(guild_id, tournament_name)
    if filepath.exists():
        os.remove(filepath)
        return True
    return False