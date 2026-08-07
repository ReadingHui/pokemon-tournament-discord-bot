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
    """Custom check: allows Server Administrators or users with the TO_ROLE_NAME role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False

        if interaction.user.guild_permissions.administrator:
            return True

        return any(role.name == TO_ROLE_NAME for role in interaction.user.roles)

    return app_commands.check(predicate)


class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Catches permission failure and returns an ephemeral error message to the user."""
        if isinstance(error, app_commands.CheckFailure):
            msg = f"❌ You need Server Administrator permissions or the **{TO_ROLE_NAME}** role to use this command."
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

    @app_commands.command(
        name="create_tournament",
        description="Create a new tournament and dedicated discussion thread."
    )
    @app_commands.describe(name="Tournament name")
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
            "current_round": 0,
            "players": {},
            "rounds": {},
            "standings": {}
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
                f"**#{rank}** {p_name} — `{info.get('Record', 'N/A')}`"
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
    @app_commands.describe(player_name="Your full registered player name")
    @app_commands.autocomplete(player_name=player_name_autocomplete)
    async def check_standing(self, interaction: discord.Interaction, player_name: str):
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
    @app_commands.describe(player_name="Your full registered player name")
    @app_commands.autocomplete(player_name=player_name_autocomplete)
    async def my_match(self, interaction: discord.Interaction, player_name: str):
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Tournament(bot))