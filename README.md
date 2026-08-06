Here are the updated `README.md` and Discord announcement post incorporating the new standings commands and updated pairing layout.

---

### `README.md`

```markdown
# 🏆 Tournament Discord Bot

A Discord bot for managing Swiss card game tournaments. Parse HTML export reports from tournament software directly inside thread channels to publish pairings, standings, and player rosters.

## 🚀 Features

* **Thread-Isolated Tournaments:** Create dedicated threads per tournament to keep main channels clean.
* **HTML Parsing:** Directly parses exported Roster, Pairings, and Standings HTML reports.
* **Monospace Padded Alignment:** Formats table numbers with fixed-width spacing so player names align cleanly.
* **Player Self-Service Commands:** Players can look up their exact pairing or rank/tiebreakers privately (`ephemeral`).
* **Discord Pagination & Chunking:** Multi-embed auto-chunking prevents Discord 2,000-character limit overflows on large events.

---

## 🛠️ Commands

### 🛡️ Organizer Commands (Requires Admin or `Tournament Organizer` Role)

| Command | Description |
| :--- | :--- |
| `/create_tournament <name>` | Creates a new tournament thread and initializes state. |
| `/upload_roster <attachment>` | Uploads roster `.html` report and posts player lists by division. |
| `/upload_pairing <attachment>` | Uploads pairings `.html` report. Formats lists alphabetically with padded table tags. |
| `/upload_standing <attachment>` | Uploads standings `.html` report. Posts ranked standings per division. |
| `/delete_tournament` | Deletes tournament state and removes the active thread. |

### 👤 Player Commands (Usable by Anyone in Tournament Thread)

| Command | Description |
| :--- | :--- |
| `/my_match <player_name>` | Displays active round table number, opponent, and current record privately. |
| `/check_standing <player_name>` | Displays current rank, match points, record, and tiebreaker percentages privately. |

---

## 📁 How File Uploads Work

1. Generate a **Roster**, **Pairings**, or **Standings** report in your tournament management software.
2. When the report opens in your browser, copy the local file path from the URL bar (e.g., `file:///C:/Users/.../pairings.html`).
3. In Discord, run `/upload_roster`, `/upload_pairing`, or `/upload_standing`.
4. Paste the path into the attachment file selector dialog and submit.

```

---

### Discord Announcement / Guide Post

📁 **Tournament Commands & Upload Guide**

Here is how to upload files and use player commands during events!

---

### 🛡️ For Tournament Organizers

**How to Upload Reports:**

1. Generate the **Roster**, **Pairings**, or **Standings** report in your tournament software.
2. Copy the file path directly from your web browser's address bar (`file:///C:/...`).
3. Run the upload command in the tournament thread, click the file box, paste the path (`Ctrl + V`), and hit Enter!

**Upload Commands:**

* `/upload_roster` — Upload initial player registrations.
* `/upload_pairing` — Upload round pairings. Displays an alphabetically sorted roster with fixed-width aligned table numbers (`Table 1  `, `Bye      `).
* `/upload_standing` — Upload standings. Updates overall rankings and tiebreakers for all divisions.

---

### 👤 For Players

You can check your match assignments and tiebreaker standings privately inside the tournament thread at any time:

* ⚔️ `/my_match` — Auto-completes your name and shows your current **Table Number**, **Opponent**, and **Record**.
* 📊 `/check_standing` — Shows your **Rank**, **Match Points**, **Record**, **Opponents' Win %**, and **Opponents' Opponents' Win %**.

*(Note: Both player lookup commands respond privately to you so they won't spam the thread!)*