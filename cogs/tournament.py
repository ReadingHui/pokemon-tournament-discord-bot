import discord
from discord import app_commands
from discord.ext import commands

from utils.parser import Parser
from utils.storage import (
    load_tournament_by_thread,
    save_tournament_by_thread,
    delete_tournament_by_thread
)

TO_ROLE_NAME = "Tournament Organizer"


def is_tournament_admin():
    """Custom check: allows Server Administrators, users with the TO_ROLE_NAME role,
    or the Discord user who created the tournament tied to the current thread."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False

        if interaction.user.guild_permissions.administrator:
            return True

        if any(role.name == TO_ROLE_NAME for role in interaction.user.roles):
            return True

        if isinstance(interaction.channel, discord.Thread):
            tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
            if tournament_data and tournament_data.get("organizer_id") == interaction.user.id:
                return True

        return False

    return app_commands.check(predicate)


def get_to_role(guild: discord.Guild) -> discord.Role | None:
    """Looks up the Tournament Organizer role in the guild, if it exists."""
    return discord.utils.get(guild.roles, name=TO_ROLE_NAME)


async def send_organizer_dm(client: discord.Client, tournament_data: dict, content: str) -> bool:
    """Attempts to DM the tournament's creator. Returns True if the DM was sent successfully."""
    organizer_id = tournament_data.get("organizer_id")
    if not organizer_id:
        return False

    try:
        user = client.get_user(organizer_id) or await client.fetch_user(organizer_id)
        await user.send(content)
        return True
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return False


def resolve_player_name(
    tournament_data: dict,
    interaction: discord.Interaction,
    player_name: str | None
) -> tuple[str | None, str | None]:
    """Resolves which player name a lookup command should use: the explicit argument if given,
    otherwise the caller's registered name. Returns (name, error_message); error_message is
    set (and name is None) if no name was given and the caller isn't registered."""
    if player_name:
        return player_name, None

    registered_name = get_registered_player_name(tournament_data, interaction.user.id)
    if registered_name:
        return registered_name, None

    return None, (
        "❌ You didn't specify a `player_name` and you're not registered yet. "
        "Use `/register` to link your Discord account, or pass a `player_name` explicitly."
    )


def get_registered_player_name(tournament_data: dict, user_id: int) -> str | None:
    """Returns the player name a given Discord user is registered as, if any."""
    registrations = tournament_data.get("registrations", {})
    for player_name, registered_id in registrations.items():
        if registered_id == user_id:
            return player_name
    return None


def collect_all_player_names(tournament_data: dict) -> set[str]:
    """Union of every player name known to the tournament: roster, standings, and all round pairings."""
    names = set(tournament_data.get("players", {}).keys())
    names.update(tournament_data.get("standings", {}).keys())
    for round_pairings in tournament_data.get("rounds", {}).values():
        for div_players in round_pairings.values():
            names.update(div_players.keys())
    return names


class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Catches permission failure and returns an ephemeral error message to the user."""
        if isinstance(error, app_commands.CheckFailure):
            msg = (
                f"❌ You need Server Administrator permissions, the **{TO_ROLE_NAME}** role, "
                f"or to be this tournament's creator to use this command."
            )
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        else:
            raise error

    async def player_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocompletes player names from roster, standings, or round pairings in the thread."""
        if not isinstance(interaction.channel, discord.Thread):
            return []

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            return []

        # Check roster first, then standings, then fallback to current round pairings
        players = list(tournament_data.get("players", {}).keys())
        if not players:
            players = list(tournament_data.get("standings", {}).keys())
        if not players:
            current_round = str(tournament_data.get("current_round", 0))
            round_pairings = tournament_data.get("rounds", {}).get(current_round, {})
            for div_players in round_pairings.values():
                players.extend(div_players.keys())

        matching_players = [
            app_commands.Choice(name=name, value=name)
            for name in players
            if current.lower() in name.lower()
        ]
        return matching_players[:25]

    async def all_player_names_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocompletes from the full set of known player names: roster, standings, and all round pairings."""
        if not isinstance(interaction.channel, discord.Thread):
            return []

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            return []

        names = sorted(collect_all_player_names(tournament_data))
        matching_names = [
            app_commands.Choice(name=name, value=name)
            for name in names
            if current.lower() in name.lower()
        ]
        return matching_names[:25]

    @app_commands.command(
        name="create_tournament",
        description="Create a new tournament and dedicated discussion thread."
    )
    @app_commands.describe(name="Tournament name")
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def create_tournament(self, interaction: discord.Interaction, name: str):
        if isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ You cannot create a tournament inside an existing thread.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        thread = await interaction.channel.create_thread(
            name=f"🏆 {name}",
            type=discord.ChannelType.public_thread
        )

        tournament_data = {
            "tournament_name": name,
            "guild_id": interaction.guild_id,
            "thread_id": thread.id,
            "organizer_id": interaction.user.id,
            "current_round": 0,
            "players": {},
            "rounds": {},
            "standings": {},
            "registrations": {}
        }
        save_tournament_by_thread(interaction.guild_id, thread.id, tournament_data)

        created_timestamp = int(discord.utils.utcnow().timestamp())

        await interaction.followup.send(
            f"✅ Tournament **{name}** created! Manage it in thread: {thread.mention}"
        )

        await thread.send(
            f"🏆 **Welcome to {name}!**\n"
            f"👤 **Organizer:** {interaction.user.mention} (`{interaction.user.name}`)\n"
            f"📅 **Created On:** <t:{created_timestamp}:F>\n\n"
            f"Run `/upload_roster`, `/upload_pairing`, and `/upload_standing` directly in this thread."
        )

    @app_commands.command(
        name="upload_roster",
        description="Upload roster HTML file (Must be executed inside tournament thread)."
    )
    @app_commands.describe(roster="HTML roster report file")
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def upload_roster(self, interaction: discord.Interaction, roster: discord.Attachment):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ This command can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        if not roster.filename.endswith((".html", ".htm")):
            await interaction.response.send_message(
                "❌ Invalid file type! Please attach a `.html` roster report.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            html_bytes = await roster.read()
            html_content = html_bytes.decode("utf-8", errors="ignore")

            parser = Parser(html_content)
            parser.parse_meta()
            roster_data = parser.parse_player_list()

            if not roster_data or not isinstance(roster_data, dict):
                raise ValueError("Parsed roster content is empty or malformed.")
        except ValueError as ve:
            if "Same name for players" in str(ve):
                await interaction.followup.send(
                    "⚠️ **Duplicate Player Name Detected:** The uploaded report contains multiple players with the exact same name. Please adjust duplicate names in your tournament software (e.g., adding a last initial) and re-upload.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ **Parsing Error:** {ve}",
                    ephemeral=True
                )
            return
        except Exception:
            await interaction.followup.send(
                "❌ **Parsing Error:** The uploaded file could not be parsed as a valid roster HTML report.",
                ephemeral=True
            )
            return

        tournament_data["players"] = roster_data
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        divisions = {}
        for player_name, info in roster_data.items():
            div = info.get("age_division", "General")
            divisions.setdefault(div, []).append(player_name)

        embeds_to_send = []
        current_embed = discord.Embed(
            title=f"📋 Roster Uploaded — {tournament_data['tournament_name']}",
            description=f"Successfully loaded **{len(roster_data)}** registered players.",
            color=discord.Color.green()
        )
        current_char_count = len(current_embed.title or "") + len(current_embed.description or "")

        for div_name, p_list in divisions.items():
            lines = [f"{idx}. {p}" for idx, p in enumerate(p_list, 1)]

            chunks = []
            current_chunk = []
            current_chunk_len = 0

            for line in lines:
                if current_chunk_len + len(line) + 1 > 1000:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_chunk_len = len(line)
                else:
                    current_chunk.append(line)
                    current_chunk_len += len(line) + 1
            if current_chunk:
                chunks.append("\n".join(current_chunk))

            for i, chunk in enumerate(chunks):
                field_name = f"🏆 {div_name} ({len(p_list)})" if len(chunks) == 1 else f"🏆 {div_name} ({len(p_list)}) — Part {i+1}/{len(chunks)}"
                field_len = len(field_name) + len(chunk)

                if current_char_count + field_len > 1800 or len(current_embed.fields) >= 20:
                    embeds_to_send.append(current_embed)
                    current_embed = discord.Embed(
                        title=f"📋 Roster (Continued) — {tournament_data['tournament_name']}",
                        color=discord.Color.green()
                    )
                    current_char_count = len(current_embed.title or "")

                current_embed.add_field(name=field_name, value=chunk, inline=False)
                current_char_count += field_len

        if len(current_embed.fields) > 0 or not embeds_to_send:
            embeds_to_send.append(current_embed)

        for embed in embeds_to_send:
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="upload_pairing",
        description="Upload pairings HTML file (Must be executed inside tournament thread)."
    )
    @app_commands.describe(pairing="HTML pairings report file")
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def upload_pairing(self, interaction: discord.Interaction, pairing: discord.Attachment):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ This command can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        if not pairing.filename.endswith((".html", ".htm")):
            await interaction.response.send_message(
                "❌ Invalid file type! Please attach a `.html` pairings report.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            html_bytes = await pairing.read()
            html_content = html_bytes.decode("utf-8", errors="ignore")

            parser = Parser(html_content)
            pairings_data = parser.parse_pairing()

            if not pairings_data or not isinstance(pairings_data, dict):
                raise ValueError("Parsed pairings content is empty or malformed.")

            round_num = list(pairings_data.keys())[0]
            round_info = pairings_data[round_num]

            if not round_info:
                raise ValueError("No pairing details found in parsed round data.")
        except ValueError as ve:
            if "Same name for players" in str(ve):
                await interaction.followup.send(
                    "⚠️ **Duplicate Player Name Detected:** The uploaded report contains multiple players with the exact same name. Please adjust duplicate names in your tournament software (e.g., adding a last initial) and re-upload.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ **Parsing Error:** {ve}",
                    ephemeral=True
                )
            return
        except Exception:
            await interaction.followup.send(
                "❌ **Parsing Error:** The uploaded file could not be parsed as a valid pairings HTML report.",
                ephemeral=True
            )
            return

        tournament_data["current_round"] = int(round_num)
        tournament_data["rounds"][str(round_num)] = round_info
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        embeds_to_send = []
        current_embed = discord.Embed(
            title=f"⚔️ Round {round_num} Pairings — {tournament_data['tournament_name']}",
            description="Players can also run `/my_match` to look up match details privately.",
            color=discord.Color.blue()
        )
        current_char_count = len(current_embed.title or "") + len(current_embed.description or "")

        for div_name, players in round_info.items():
            # Sort players alphabetically by Name
            sorted_players = sorted(players.items(), key=lambda x: x[0].lower())

            lines = []
            for p_name, p_data in sorted_players:
                tbl = str(p_data.get("table", "N/A")).strip()
                table_str = f"Table {tbl}" if tbl.lower() != "bye" else "Bye"
                
                # Left-align and pad to 9 characters inside the inline code block
                table_padded = f"{table_str:<9}"
                lines.append(f"`{table_padded}` **{p_name}**")

            # Chunk into fields <= 1000 characters
            chunks = []
            current_chunk = []
            current_chunk_len = 0

            for line in lines:
                if current_chunk_len + len(line) + 1 > 1000:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_chunk_len = len(line)
                else:
                    current_chunk.append(line)
                    current_chunk_len += len(line) + 1
            if current_chunk:
                chunks.append("\n".join(current_chunk))

            # Add fields and handle pagination across embeds
            for i, chunk in enumerate(chunks):
                if len(chunks) == 1:
                    field_name = f"🏆 {div_name} ({len(sorted_players)} Players)"
                else:
                    field_name = f"🏆 {div_name} ({len(sorted_players)} Players) — Part {i+1}/{len(chunks)}"

                field_len = len(field_name) + len(chunk)

                if current_char_count + field_len > 1800 or len(current_embed.fields) >= 20:
                    embeds_to_send.append(current_embed)
                    current_embed = discord.Embed(
                        title=f"⚔️ Round {round_num} Pairings (Continued) — {tournament_data['tournament_name']}",
                        color=discord.Color.blue()
                    )
                    current_char_count = len(current_embed.title or "")

                current_embed.add_field(name=field_name, value=chunk, inline=False)
                current_char_count += field_len

        if len(current_embed.fields) > 0 or not embeds_to_send:
            embeds_to_send.append(current_embed)

        for embed in embeds_to_send:
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="upload_standing",
        description="Upload standings HTML file (Must be executed inside tournament thread)."
    )
    @app_commands.describe(standing="HTML standings report file")
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def upload_standing(self, interaction: discord.Interaction, standing: discord.Attachment):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ This command can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        if not standing.filename.endswith((".html", ".htm")):
            await interaction.response.send_message(
                "❌ Invalid file type! Please attach a `.html` standings report.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            html_bytes = await standing.read()
            html_content = html_bytes.decode("utf-8", errors="ignore")

            parser = Parser(html_content)
            standings_data = parser.parse_standings()

            if not standings_data or not isinstance(standings_data, dict):
                raise ValueError("Parsed standings content is empty or malformed.")
        except ValueError as ve:
            if "Same name for players" in str(ve):
                await interaction.followup.send(
                    "⚠️ **Duplicate Player Name Detected:** The uploaded report contains multiple players with the exact same name. Please adjust duplicate names in your tournament software (e.g., adding a last initial) and re-upload.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ **Parsing Error:** {ve}",
                    ephemeral=True
                )
            return
        except Exception:
            await interaction.followup.send(
                "❌ **Parsing Error:** The uploaded file could not be parsed as a valid standings HTML report.",
                ephemeral=True
            )
            return

        tournament_data["standings"] = standings_data
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        # Extract round label header from the first entry
        round_title = "Standings"
        for p_info in standings_data.values():
            if p_info.get("Rounds"):
                round_title = p_info["Rounds"].strip()
                break

        # Group players by division and sort by Rank
        divisions = {}
        for player_name, info in standings_data.items():
            div = info.get("Division", "General")
            divisions.setdefault(div, []).append((info.get("Rank", 999), player_name, info))

        for div in divisions:
            divisions[div].sort(key=lambda x: x[0])

        embeds_to_send = []
        current_embed = discord.Embed(
            title=f"📊 {round_title} — {tournament_data['tournament_name']}",
            description=f"Standings updated for **{len(standings_data)}** total players. Use `/check_standing` to view individual tiebreaker stats.",
            color=discord.Color.gold()
        )
        current_char_count = len(current_embed.title or "") + len(current_embed.description or "")

        for div_name, player_tuples in divisions.items():
            # Build vertical formatted lines: "1. Player Name — Record (Pts)"
            lines = [
                f"**#{rank}** **{p_name}** — `{info.get('Record', 'N/A')}`" if info.get('Top_cut') else f"**#{rank}** {p_name} — `{info.get('Record', 'N/A')}`"
                for rank, p_name, info in player_tuples
            ]

            chunks = []
            current_chunk = []
            current_chunk_len = 0

            for line in lines:
                if current_chunk_len + len(line) + 1 > 1000:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_chunk_len = len(line)
                else:
                    current_chunk.append(line)
                    current_chunk_len += len(line) + 1
            if current_chunk:
                chunks.append("\n".join(current_chunk))

            for i, chunk in enumerate(chunks):
                field_name = f"🥇 {div_name} ({len(player_tuples)})" if len(chunks) == 1 else f"🥇 {div_name} ({len(player_tuples)}) — Part {i+1}/{len(chunks)}"
                field_len = len(field_name) + len(chunk)

                if current_char_count + field_len > 1800 or len(current_embed.fields) >= 20:
                    embeds_to_send.append(current_embed)
                    current_embed = discord.Embed(
                        title=f"📊 {round_title} (Continued) — {tournament_data['tournament_name']}",
                        color=discord.Color.gold()
                    )
                    current_char_count = len(current_embed.title or "")

                current_embed.add_field(name=field_name, value=chunk, inline=False)
                current_char_count += field_len

        if len(current_embed.fields) > 0 or not embeds_to_send:
            embeds_to_send.append(current_embed)

        for embed in embeds_to_send:
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="check_standing",
        description="Lookup your current rank, record, and tiebreaker stats in this thread."
    )
    @app_commands.describe(player_name="Player name to look up (defaults to your registered name if omitted)")
    @app_commands.autocomplete(player_name=player_name_autocomplete)
    async def check_standing(self, interaction: discord.Interaction, player_name: str = None):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ `/check_standing` can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        player_name, error = resolve_player_name(tournament_data, interaction, player_name)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        standings = tournament_data.get("standings", {})
        if not standings:
            await interaction.response.send_message(
                "❌ No standings have been uploaded for this tournament yet.",
                ephemeral=True
            )
            return

        info = standings.get(player_name)
        if not info:
            await interaction.response.send_message(
                f"❌ Player **{player_name}** not found in current standings.",
                ephemeral=True
            )
            return

        rounds_header = info.get("Rounds", "Current Standings").strip()

        embed = discord.Embed(
            title=f"📊 {rounds_header}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Player", value=player_name, inline=True)
        embed.add_field(name="Rank", value=f"**#{info.get('Rank', 'N/A')}**", inline=True)
        embed.add_field(name="Division", value=info.get("Division", "N/A"), inline=True)

        embed.add_field(name="Record", value=info.get("Record", "N/A"), inline=True)
        embed.add_field(name="Match Points", value=str(info.get("Match Points", "0")), inline=True)
        embed.add_field(name="Drop Round", value=info.get("Drop Round", "N/A"), inline=True)

        embed.add_field(name="Opponents' Win %", value=info.get("Opponents' win %", "N/A"), inline=True)
        embed.add_field(name="Opponents' Opp Win %", value=info.get("Opponents' opponents' win %", "N/A"), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="delete_tournament",
        description="Delete tournament data and remove this thread."
    )
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def delete_tournament(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ This command can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        await interaction.response.send_message("🗑️ Deleting tournament state and removing thread...")

        thread = interaction.channel
        delete_tournament_by_thread(interaction.guild_id, thread.id)
        await thread.delete()

    @app_commands.command(
        name="my_match",
        description="Lookup your match pairing for the active round in this thread."
    )
    @app_commands.describe(player_name="Player name to look up (defaults to your registered name if omitted)")
    @app_commands.autocomplete(player_name=player_name_autocomplete)
    async def my_match(self, interaction: discord.Interaction, player_name: str = None):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ `/my_match` can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        player_name, error = resolve_player_name(tournament_data, interaction, player_name)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        current_round = str(tournament_data.get("current_round", 0))
        if current_round == "0" or current_round not in tournament_data.get("rounds", {}):
            await interaction.response.send_message(
                "❌ No active pairings found for this tournament yet.",
                ephemeral=True
            )
            return

        round_pairings = tournament_data["rounds"][current_round]
        status = None

        for division, players in round_pairings.items():
            if player_name in players:
                info = players[player_name]
                status = {
                    "round": current_round,
                    "division": division,
                    "table": info["table"],
                    "opponent": info["opponent"],
                    "record": info["record"]
                }
                break

        if not status:
            await interaction.response.send_message(
                f"❌ Player **{player_name}** not found in Round {current_round} pairings.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Match Info — Round {status['round']}",
            color=discord.Color.green()
        )
        embed.add_field(name="Player", value=player_name, inline=True)
        embed.add_field(name="Division", value=status["division"], inline=True)
        embed.add_field(name="Record", value=status["record"], inline=True)

        if status["table"] == "Bye":
            embed.add_field(name="Table", value="**BYE**", inline=False)
            embed.add_field(name="Opponent", value="N/A", inline=False)
        else:
            embed.add_field(name="Table", value=f"**Table {status['table']}**", inline=True)
            embed.add_field(name="Opponent", value=status["opponent"], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="register",
        description="Link your Discord account to your player name in this tournament."
    )
    @app_commands.describe(player_name="Your full registered player name")
    @app_commands.autocomplete(player_name=all_player_names_autocomplete)
    async def register(self, interaction: discord.Interaction, player_name: str):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ `/register` can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        known_names = collect_all_player_names(tournament_data)
        if player_name not in known_names:
            await interaction.response.send_message(
                f"❌ **{player_name}** was not found in the roster, standings, or pairings for this tournament.",
                ephemeral=True
            )
            return

        registrations = tournament_data.setdefault("registrations", {})

        existing_name = get_registered_player_name(tournament_data, interaction.user.id)
        if existing_name and existing_name != player_name:
            await interaction.response.send_message(
                f"❌ You're already registered as **{existing_name}**. "
                f"Ask a {TO_ROLE_NAME} to reassign you with `/assign_player` if this needs to change.",
                ephemeral=True
            )
            return

        claimed_by = registrations.get(player_name)
        if claimed_by is not None and claimed_by != interaction.user.id:
            alert = (
                f"⚠️ In **{tournament_data.get('tournament_name', 'your tournament')}** "
                f"({interaction.channel.mention}) — {interaction.user.mention} ({interaction.user}) attempted "
                f"to register as **{player_name}**, which is already claimed by <@{claimed_by}>. "
                f"Use `/assign_player` to resolve."
            )
            delivered = await send_organizer_dm(interaction.client, tournament_data, alert)
            if not delivered:
                to_role = get_to_role(interaction.guild)
                fallback_mention = to_role.mention if to_role else f"**{TO_ROLE_NAME}**"
                await interaction.channel.send(f"{fallback_mention} {alert}")

            await interaction.response.send_message(
                f"⚠️ **{player_name}** is already claimed by another user. "
                f"The tournament's TO has been notified to resolve this.",
                ephemeral=True
            )
            return

        registrations[player_name] = interaction.user.id
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        await interaction.response.send_message(
            f"✅ You're now registered as **{player_name}**. You can use `/report_result` to report your matches.",
            ephemeral=True
        )

    @app_commands.command(
        name="assign_player",
        description="(TO) Manually link a Discord member to a player name, overriding any existing claim."
    )
    @app_commands.describe(player_name="Player name to assign", member="Discord member to link to this name")
    @app_commands.autocomplete(player_name=all_player_names_autocomplete)
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def assign_player(self, interaction: discord.Interaction, player_name: str, member: discord.Member):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ This command can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        known_names = collect_all_player_names(tournament_data)
        if player_name not in known_names:
            await interaction.response.send_message(
                f"❌ **{player_name}** was not found in the roster, standings, or pairings for this tournament.",
                ephemeral=True
            )
            return

        registrations = tournament_data.setdefault("registrations", {})

        # Clear any other name previously claimed by this member, so they don't end up double-registered.
        previous_name = get_registered_player_name(tournament_data, member.id)
        if previous_name and previous_name != player_name:
            del registrations[previous_name]

        registrations[player_name] = member.id
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        await interaction.response.send_message(
            f"✅ **{player_name}** is now linked to {member.mention}.",
            ephemeral=True
        )

    @app_commands.command(
        name="unregister_player",
        description="(TO) Remove the Discord link for a player name."
    )
    @app_commands.describe(player_name="Player name to unlink")
    @app_commands.autocomplete(player_name=all_player_names_autocomplete)
    @app_commands.default_permissions(manage_guild=True)
    @is_tournament_admin()
    async def unregister_player(self, interaction: discord.Interaction, player_name: str):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ This command can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        registrations = tournament_data.setdefault("registrations", {})
        if player_name not in registrations:
            await interaction.response.send_message(
                f"❌ **{player_name}** is not currently linked to anyone.",
                ephemeral=True
            )
            return

        del registrations[player_name]
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        await interaction.response.send_message(
            f"✅ **{player_name}** has been unlinked.",
            ephemeral=True
        )

    @app_commands.command(
        name="report_result",
        description="Report your match result for the current round (sent to the TO for confirmation)."
    )
    @app_commands.describe(
        result="The outcome of your match, from your perspective",
        game_score="Optional game score, e.g. 2-1"
    )
    @app_commands.choices(result=[
        app_commands.Choice(name="Win", value="Win"),
        app_commands.Choice(name="Loss", value="Loss"),
        app_commands.Choice(name="Tie", value="Tie"),
    ])
    async def report_result(
        self,
        interaction: discord.Interaction,
        result: app_commands.Choice[str],
        game_score: str = None
    ):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ `/report_result` can only be used inside a tournament thread.",
                ephemeral=True
            )
            return

        tournament_data = load_tournament_by_thread(interaction.guild_id, interaction.channel.id)
        if not tournament_data:
            await interaction.response.send_message(
                "❌ No active tournament associated with this thread.",
                ephemeral=True
            )
            return

        player_name = get_registered_player_name(tournament_data, interaction.user.id)
        if not player_name:
            await interaction.response.send_message(
                "❌ You're not registered yet. Use `/register` to link your Discord account to your player name first.",
                ephemeral=True
            )
            return

        current_round = str(tournament_data.get("current_round", 0))
        round_pairings = tournament_data.get("rounds", {}).get(current_round)
        if current_round == "0" or not round_pairings:
            await interaction.response.send_message(
                "❌ No active pairings found for this tournament yet.",
                ephemeral=True
            )
            return

        division, match_info = None, None
        for div, players in round_pairings.items():
            if player_name in players:
                division = div
                match_info = players[player_name]
                break

        if not match_info:
            await interaction.response.send_message(
                f"❌ **{player_name}** was not found in Round {current_round} pairings.",
                ephemeral=True
            )
            return

        if str(match_info.get("table", "")).strip().lower() == "bye":
            await interaction.response.send_message(
                "ℹ️ You have a bye this round — there's no match to report.",
                ephemeral=True
            )
            return

        score_line = f" (`{game_score}`)" if game_score else ""
        report = (
            f"📣 Match result reported in **{tournament_data.get('tournament_name', 'your tournament')}** "
            f"({interaction.channel.mention}):\n"
            f"**Round {current_round} • {division} • Table {match_info.get('table', 'N/A')}**\n"
            f"{interaction.user.mention} ({interaction.user}) reports **{player_name}** as a "
            f"**{result.value}**{score_line} vs opponent **{match_info.get('opponent', 'N/A')}**.\n"
            f"⚠️ Unconfirmed — please verify and enter this result in your tournament software."
        )
        delivered = await send_organizer_dm(interaction.client, tournament_data, report)
        if not delivered:
            to_role = get_to_role(interaction.guild)
            fallback_mention = to_role.mention if to_role else f"**{TO_ROLE_NAME}**"
            await interaction.channel.send(f"{fallback_mention} {report}")

        await interaction.response.send_message(
            f"✅ Your result (**{result.value}**) has been sent to the tournament's TO for confirmation.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Tournament(bot))