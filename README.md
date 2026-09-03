# Tournament Bot

A Discord bot for managing tournament-style events inside dedicated threads: rosters, pairings, and standings are parsed from HTML reports exported by tournament software, and players can self-serve lookups and self-report results.

---

## Documentation

- 📥 [Installation Guide](docs/installation-guide.md) — for Tournament Organizers setting up the bot
- 📖 [Command Guide](docs/command-guide.md) — full command reference with examples

## Requirements

- Python 3.11+ (uses `X | None` union type hints)
- [discord.py](https://github.com/Rapptz/discord.py) 2.x (for `app_commands` / slash command support)
- `python-dotenv`

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your-bot-token-here
DEV_GUILD_ID=123456789012345678   # optional — enables instant slash-command sync to a single test server
```

- `DISCORD_TOKEN` — required. Your bot's token from the [Discord Developer Portal](https://discord.com/developers/applications).
- `DEV_GUILD_ID` — optional. If set, slash commands sync instantly to that one guild instead of globally (global sync can take up to an hour to propagate). Recommended during development.

---

## Running the Bot

```bash
python main.py
```

`main.py` loads both tournament cogs and syncs the command tree on startup (`setup_hook`). You should see:
```
✅ Cog loaded: cogs.tournament_admin
✅ Cog loaded: cogs.tournament_player
⚡ Instant slash command sync enabled for Dev Guild ID: ...
🤖 Logged in as ...
```

---

## Project Structure

```
.
├── main.py                          # Bot entrypoint; loads cogs, syncs commands
├── cogs/
│   ├── tournament_admin.py          # TO-only commands (create/upload/delete/assign)
│   └── tournament_player.py         # Player-facing commands (register/lookup/report)
├── utils/
│   ├── tournament_helpers.py        # Shared permission checks, DM helpers, autocompletes
│   ├── parser.py                    # HTML report parsing (roster/pairings/standings)
│   └── storage.py                   # Tournament data persistence, keyed by (guild_id, thread_id)
└── .env                             # Local secrets (not committed)
```

### Why two cogs?

Tournament commands split naturally into two audiences with different permission models:

- **`tournament_admin.py`** — gated by `is_tournament_admin()`: Server Administrators, the `Tournament Organizer` role, or the tournament's creator (`organizer_id`). These commands also carry `@app_commands.default_permissions(manage_guild=True)`, hiding them from regular members in Discord's UI by default.
- **`tournament_player.py`** — open to everyone; self-service lookups and self-reporting.

Both import shared logic from `utils/tournament_helpers.py` rather than duplicating it, so permission checks, DM delivery, and autocomplete behavior stay in one place.

---

## Data Model

Each tournament is a single dict, persisted via `utils.storage` keyed by `(guild_id, thread_id)`:

```python
{
    "tournament_name": str,
    "guild_id": int,
    "thread_id": int,
    "organizer_id": int,          # Discord user ID of whoever ran /create_tournament
    "current_round": int,
    "players": dict,              # from parse_player_list() — roster
    "rounds": {                   # keyed by round number (str)
        "1": { "<Division>": { "<PlayerName>": {"table": ..., "opponent": ..., "record": ...} } }
    },
    "standings": dict,            # from parse_standings() — keyed by player name
    "registrations": {            # player_name -> Discord user ID
        "<PlayerName>": int
    }
}
```

`registrations` is the link between a player's in-game name and their Discord account, built up via `/register` and `/assign_player`. It powers:
- Defaulting `player_name` on `/check_standing` and `/my_match` to the caller.
- Sending automatic DMs on `/upload_pairing` and `/upload_standing`.
- Resolving who's reporting on `/report_result`.

> ⚠️ `organizer_id` and `registrations` were added after the tournament system's initial version. Tournaments created before that change won't have `organizer_id` set — code that reads it should treat a missing key as "no organizer on record" and fall back accordingly (see `send_organizer_dm` in `tournament_helpers.py`).

---

## Key Helpers (`utils/tournament_helpers.py`)

| Function | Purpose |
|---|---|
| `is_tournament_admin()` | `app_commands.check` — gates TO-only commands. |
| `handle_tournament_permission_error()` | Shared `cog_app_command_error` logic for permission failures. |
| `send_dm(client, user_id, ...)` | Best-effort DM to any user by ID; returns `bool` success. |
| `send_organizer_dm(client, tournament_data, content)` | DMs the tournament's creator specifically. |
| `get_registered_player_name(tournament_data, user_id)` | Reverse-lookup: Discord user → their registered player name. |
| `resolve_player_name(tournament_data, interaction, player_name)` | Used by lookup commands to default an omitted `player_name` to the caller's registered name. |
| `collect_all_player_names(tournament_data)` | Union of names across roster, standings, and all rounds — used for `/register` validation and autocomplete. |
| `player_name_autocomplete` / `all_player_names_autocomplete` | Autocomplete callbacks, shared across both cogs. |

---

## HTML Parsing (`utils/parser.py`)

The `Parser` class takes raw HTML from tournament software exports and produces the structures above:

```python
parser = Parser(html_content)
parser.parse_meta()
roster_data = parser.parse_player_list()      # -> dict
pairings_data = parser.parse_pairing()         # -> {round_num: {division: {player: {...}}}}
standings_data = parser.parse_standings()      # -> {player: {...}}
```

`ValueError` with `"Same name for players"` in the message is handled specially by the upload commands (surfaced as a "duplicate player name" warning) — keep this substring stable if you touch the parser's error messages.

---

## Notes for Contributors

- All Discord-facing responses that reveal personal info (standings, match details, registration status) use `ephemeral=True` — don't remove this without a reason.
- DM sends are always wrapped in `send_dm()` / `send_organizer_dm()`, which catch `Forbidden`/`HTTPException`/`NotFound` and return `False` rather than raising — callers should check the return value and fall back gracefully (see the in-thread ping fallback in `report_result` and `register`).
- `TO_ROLE_NAME = "Tournament Organizer"` is a hardcoded string match against role names — if you rename the role concept, update this constant, not the string literal in the role itself.
- New TO-only commands should be added to `tournament_admin.py`, decorated with both `@is_tournament_admin()` and `@app_commands.default_permissions(manage_guild=True)`, to stay consistent with the permission + visibility model.
