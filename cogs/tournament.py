import discord
from discord import app_commands
from discord.ext import commands

from utils.parser import Parser
from utils.storage import (
    load_tournament_by_thread,
    save_tournament_by_thread,
    delete_tournament_by_thread
)


class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="create_tournament",
        description="Create a new tournament and dedicated discussion thread."
    )
    @app_commands.describe(name="Tournament name")
    async def create_tournament(self, interaction: discord.Interaction, name: str):
        if isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ You cannot create a tournament inside an existing thread.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        # Create public thread in the current text channel
        thread = await interaction.channel.create_thread(
            name=f"🏆 {name}",
            type=discord.ChannelType.public_thread
        )

        # Initialize storage entry keyed directly by thread.id
        tournament_data = {
            "tournament_name": name,
            "guild_id": interaction.guild_id,
            "thread_id": thread.id,
            "current_round": 0,
            "players": {},
            "rounds": {}
        }
        save_tournament_by_thread(interaction.guild_id, thread.id, tournament_data)

        await interaction.followup.send(
            f"✅ Tournament **{name}** created! Manage it in thread: {thread.mention}"
        )
        await thread.send(
            f"🏆 **Welcome to {name}!**\n"
            f"Run `/upload_roster` and `/upload_pairing` directly in this thread."
        )

    @app_commands.command(
        name="upload_roster",
        description="Upload roster HTML file (Must be executed inside tournament thread)."
    )
    @app_commands.describe(roster="HTML roster report file")
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
                "❌ Please attach a valid `.html` roster file.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        html_bytes = await roster.read()
        html_content = html_bytes.decode("utf-8", errors="ignore")

        parser = Parser(html_content)
        parser.parse_meta()
        roster_data = parser.parse_player_list()

        if not roster_data:
            await interaction.followup.send("❌ Failed to parse roster HTML.", ephemeral=True)
            return

        tournament_data["players"] = roster_data
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        # Build roster summary embed
        divisions = {}
        for player_name, info in roster_data.items():
            div = info.get("age_division", "General")
            divisions.setdefault(div, []).append(player_name)

        embed = discord.Embed(
            title=f"📋 Roster Uploaded — {tournament_data['tournament_name']}",
            description=f"Loaded **{len(roster_data)}** total players.",
            color=discord.Color.green()
        )

        for div_name, p_list in divisions.items():
            preview = ", ".join(p_list[:10])
            if len(p_list) > 10:
                preview += f" ...and {len(p_list) - 10} more"
            embed.add_field(
                name=f"{div_name} ({len(p_list)})",
                value=preview or "None",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="upload_pairing",
        description="Upload pairings HTML file (Must be executed inside tournament thread)."
    )
    @app_commands.describe(pairing="HTML pairings report file")
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
                "❌ Please attach a valid `.html` pairings file.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        html_bytes = await pairing.read()
        html_content = html_bytes.decode("utf-8", errors="ignore")

        parser = Parser(html_content)
        pairings_data = parser.parse_pairing()

        if not pairings_data:
            await interaction.followup.send("❌ Failed to parse pairings HTML.", ephemeral=True)
            return

        round_num = list(pairings_data.keys())[0]
        round_info = pairings_data[round_num]

        tournament_data["current_round"] = int(round_num)
        tournament_data["rounds"][str(round_num)] = round_info
        save_tournament_by_thread(interaction.guild_id, interaction.channel.id, tournament_data)

        embed = discord.Embed(
            title=f"⚔️ Round {round_num} Pairings — {tournament_data['tournament_name']}",
            description="Pairings updated! Players can run `/my_match` in this thread to check their table and opponent.",
            color=discord.Color.blue()
        )

        for div_name, players in round_info.items():
            active_tables = len([p for p, d in players.items() if d["table"] != "Bye"]) // 2
            byes = len([p for p, d in players.items() if d["table"] == "Bye"])
            embed.add_field(
                name=div_name,
                value=f"**{len(players)}** Players | **{active_tables}** Active Tables | **{byes}** Bye(s)",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="delete_tournament",
        description="Delete tournament data and remove this thread."
    )
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