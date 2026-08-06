# Discord Tournament Management Bot

A thread-based Discord bot built with `discord.py` for tournament organizers. It parses standard HTML tournament reports (rosters and pairings) to automate round updates and provide instant `/my_match` lookups for players.

---

## ⚡ Installation & Setup

### 1. Prerequisites & Environment Setup
Ensure you have Python 3.10 or higher installed.

```bash
# Clone the repository
git clone [https://github.com/your-username/discord-tournament-bot.git](https://github.com/your-username/discord-tournament-bot.git)
cd discord-tournament-bot

# (Optional) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt