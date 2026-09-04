# Tournament Bot — Command Guide

All commands must be run **inside a tournament thread** unless noted otherwise. Player lookup commands (`/my_standing`, `/my_match`) respond privately (only you can see them), so feel free to use them anytime without spamming the thread.

---

## 🧑‍🤝‍🧑 Player Commands

### `/link`
Link your Discord account to your player name in the tournament. Once linked, other commands (`/my_standing`, `/my_match`, `/report_result`) automatically know who you are — you won't need to type your name again.

- `player_name` — start typing your name; autocomplete pulls from the roster, standings, and pairings.

**Example:**
```
/link player_name: Alex Johnson
```
> ✅ You're now registered as **Alex Johnson**. You can use `/report_result` to report your matches.

If someone else already claimed that name, you'll be told the TO has been notified to sort it out — use `/report_result` or contact your TO if this happens unexpectedly.

---

### `/my_match`
Look up your table number, opponent, and record for the **current round**.

- `player_name` *(optional)* — leave blank to look up yourself (requires `/link` first), or specify any name to check someone else's match.

**Example:**
```
/my_match
```
```
/my_match player_name: Alex Johnson
```
> Shows an embed with **Division**, **Record**, **Table**, and **Opponent** (or **BYE**).

---

### `/my_standing`
Look up current rank, record, and tiebreaker stats.

- `player_name` *(optional)* — leave blank to look up yourself, or specify any name.

**Example:**
```
/my_standing
```
```
/my_standing player_name: Alex Johnson
```
> Shows an embed with **Rank**, **Division**, **Record**, **Match Points**, **Drop Round**, **Opponents' Win %**, and **Opponents' Opp Win %**.

> 💡 You'll also automatically get a DM with this same info every time your TO uploads new standings — no need to check manually after each round.

---

### `/report_result`
Report your result for the current round's match. Requires `/link` first. This is sent to your TO for confirmation — it does **not** automatically update standings.

- `result` — choose **Win**, **Loss**, or **Tie** (from your own perspective).
- `game_score` *(optional)* — e.g. `2-1`.

**Example:**
```
/report_result result: Win game_score: 2-1
```
> ✅ Your result (**Win**) has been sent to the tournament's TO for confirmation.

Your TO will receive a DM with the round, table, opponent, and your reported result, and will confirm it in their tournament software.

---

## 🛡️ Tournament Organizer / Admin Commands

> These commands require **Server Administrator** permission, the **Tournament Organizer** role, or being the tournament's creator. They're also hidden from the command list for regular members by default (see the Installation Guide for how to grant TO-role visibility).

### `/create_tournament`
Creates a new tournament and a dedicated thread for it. Run this in a normal channel — **not** inside an existing thread.

- `name` — the tournament's display name.

**Example:**
```
/create_tournament name: Fall Regional 2026
```
> ✅ Tournament **Fall Regional 2026** created! Manage it in thread: #🏆-fall-regional-2026

---

### `/upload_roster`
Uploads the initial player registration report. Run this **inside the tournament thread**.

- `roster` — attach the `.html` roster file exported from your tournament software.

**Example:**
```
/upload_roster roster: [attach roster.html]
```
> Posts an embed listing all registered players, grouped by division.

---

### `/upload_pairing`
Uploads a round's pairings. Run this **inside the tournament thread**.

- `pairing` — attach the `.html` pairings file for the round.

**Example:**
```
/upload_pairing pairing: [attach round3_pairings.html]
```
> Posts a sorted, table-aligned pairings embed publicly, and **automatically DMs every registered player** their table, opponent, and record for that round — with a link back to the thread. You'll get a private summary of how many DMs went through.

---

### `/upload_standing`
Uploads updated standings. Run this **inside the tournament thread**.

- `standing` — attach the `.html` standings file.

**Example:**
```
/upload_standing standing: [attach round3_standings.html]
```
> Posts a ranked standings embed publicly, grouped by division, and **automatically DMs every registered player** their rank, record, and tiebreakers — with a link back to the thread.

---

### `/link_player`
Manually link (or reassign) a Discord member to a player name — overrides any existing claim. Useful for resolving registration conflicts or linking players who don't want to self-register.

- `player_name` — autocompletes from roster/standings/pairings.
- `member` — the Discord member to link.

**Example:**
```
/link_player player_name: Alex Johnson member: @alexj
```
> ✅ **Alex Johnson** is now linked to @alexj.

---

### `/unlink_player`
Removes a player-name's Discord link, e.g. to fix a mistaken registration.

- `player_name` — autocompletes from all known names.

**Example:**
```
/unlink_player player_name: Alex Johnson
```
> ✅ **Alex Johnson** has been unlinked.

---

### `/delete_tournament`
Deletes all stored tournament data and removes the thread. **This cannot be undone.** Run this inside the tournament thread you want to delete.

**Example:**
```
/delete_tournament
```
> 🗑️ Deleting tournament state and removing thread...
