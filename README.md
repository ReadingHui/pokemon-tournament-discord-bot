# 🏆 Discord Tournament Bot

A specialized Discord bot for tournament management. It parses HTML roster and pairing reports (e.g., from tournament software) and provides real-time thread-scoped tournament updates, player lookups with autocomplete, and round statistics.

---

## 🚀 Installation & Setup

### 1. Install Dependencies

Ensure you have Python 3.10+ installed, then install the required Python packages:

```bash
pip install -r requirements.txt

```

### 2. Configure Environment Variables

Create a `.env` file in the project root directory with the following variables:

```env
DISCORD_TOKEN=your_discord_bot_token_here
DEV_GUILD_ID=your_test_server_id_here

```

* **`DISCORD_TOKEN`**: Your bot token from the Discord Developer Portal.
* **`DEV_GUILD_ID`**: (Optional) Server ID for instant slash command synchronization during development.

### 3. Discord Developer Portal Configuration

1. Go to the [Discord Developer Portal](https://www.google.com/search?q=https://discord.com/developers/applications).
2. Select your Application $\rightarrow$ **Bot** $\rightarrow$ Enable **Message Content Intent** under *Privileged Gateway Intents*.
3. Go to **OAuth2 $\rightarrow$ URL Generator**.
* **Scopes:** `bot`, `applications.commands`
* **Bot Permissions:** `Send Messages`, `Create Public Threads`, `Send Messages in Threads`, `Read Message History`


4. Copy the generated link and invite the bot to your server.

### 4. Role Setup

Create a role named **`Tournament Organizer`** on your Discord server. Members with this role (or users with **Administrator** permissions) will be authorized to execute tournament administration commands.

### 5. Launch the Bot

```bash
python main.py

```

---

## 🛠️ How Commands Work

All tournament states are bound to **Discord Threads**, isolating each tournament's data to its dedicated discussion space.

### 👑 Administrative Commands

*Requires Server Administrator permissions or the `Tournament Organizer` role.*

| Command | Arguments | Context | Description |
| --- | --- | --- | --- |
| `/create_tournament` | `name: string` | Server Text Channel | Creates a new public thread (e.g., `🏆 Tournament Name`) with a welcome message containing the organizer's tag and timestamp. Initializes tournament storage. |
| `/upload_roster` | `roster: attachment` | Inside Tournament Thread | Uploads and parses a `.html` roster report. Displays registered player counts broken down by age/division. |
| `/upload_pairing` | `pairing: attachment` | Inside Tournament Thread | Uploads and parses a `.html` pairing report for the current round. Updates current standings and active table numbers. |
| `/delete_tournament` | *None* | Inside Tournament Thread | Deletes the JSON storage file associated with the thread and permanently removes the Discord thread. |

### 👥 Player Commands

*Available to all server members.*

| Command | Arguments | Context | Description |
| --- | --- | --- | --- |
| `/my_match` | `player_name: string` | Inside Tournament Thread | Queries the active round pairing for a given player. Displays assigned table, opponent, and current record in an ephemeral message. |

> **💡 Interactive Features:**
> * **Player Name Autocomplete:** Typing into `/my_match` dynamically autocompletes player names based on the active thread's uploaded roster.
> * **Error Handling:** If an unreadable or incorrect HTML file is uploaded to `/upload_roster` or `/upload_pairing`, the bot catches parsing failures and returns an error without crashing.
> 
> 

---

## 📁 Project Structure

```text
├── main.py                # Bot entrypoint & command tree synchronization
├── .env                   # Environment variables (token, dev guild ID)
├── requirements.txt       # Python dependencies
├── utils/
│   ├── parser.py          # HTML parser for rosters and pairings
│   └── storage.py         # JSON storage utilities (thread-ID keyed)
├── cogs/
│   └── tournament.py      # Slash commands, permissions, and autocomplete logic
└── data/                  # Local storage for thread JSON databases