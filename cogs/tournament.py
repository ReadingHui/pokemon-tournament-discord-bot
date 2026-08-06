import io
import discord
from discord import app_commands
from discord.ext import commands

from utils.parser import Parser
from utils.storage import (
    create_tournament,
    update_pairings,
    get_player_status,
    delete_tournament,
    load_tournament
)


class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    tournament_group = app_commands.Group(
        name="tournament",
        description="Manage tournament pairings, rosters, and lifecycles."
    )

    @tournament_group.command(name="start", description="Initialize a new tournament with a roster HTML file.")
    @app_commands.describe(
        name="Unique tournament identifier",
        roster_file="HTML file containing the initial player roster"
    )
    async def start_tournament(
        self,
        interaction: discord.Interaction,
        name: str,
        roster_file: discord.Attachment
    ):
        await interaction.response.defer(thinking=True)

        if not roster_file.filename.endswith((".html", ".htm")):
            await interaction.followup.send("❌ Please attach a valid `.html` roster file.", ephemeral=True)
            return

        # Download attachment into memory and parse
        html_bytes = await roster_file.read()
        html_content = html_bytes.decode("utf-8", errors="ignore")
        
        parser = Parser(html_content)
        report_type, tournament_name, organizer_name, date_time = parser.parse_meta()
        roster_data = parser.parse_player_list()
        if not roster_data:
            await interaction.followup.send("❌ Failed to parse roster HTML. Check file structure.", ephemeral=True)
            return

        # Create a dedicated thread for tournament announcements
        channel = interaction.channel
        thread = await channel.create_thread(
            name=f"🏆 {name}",
            type=discord.ChannelType.public_thread
        )

        # Save to persistent storage
        create_tournament(
            guild_id=interaction.guild_id,
            tournament_name=name,
            thread_id=thread.id,
            roster=roster_data
        )

        await interaction.followup.send(
            f"✅ Tournament **{name}** started! Created thread: {thread.mention}\n"
            f"Loaded **{len(roster_data)}** players."
        )

    @tournament_group.command(name="pairings", description="Upload round pairings HTML file.")
    @app_commands.describe(
        name="Tournament name",
        round_num="Round number (e.g., 1)",
        pairings_file="HTML file containing the round pairings"
    )
    async def upload_pairings(
        self,
        interaction: discord.Interaction,
        name: str,
        round_num: int,
        pairings_file: discord.Attachment
    ):
        await interaction.response.defer(thinking=True)

        if not pairings_file.filename.endswith((".html", ".htm")):
            await interaction.followup.send("❌ Please attach a valid `.html` pairings file.", ephemeral=True)
            return

        html_bytes = await pairings_file.read()
        html_content = html_bytes.decode("utf-8", errors="ignore")

        parser = Parser(html_content)
        pairings_data = parser.parse_pairing()
        if not pairings_data:
            await interaction.followup.send("❌ Failed to parse pairings HTML.", ephemeral=True)
            return

        try:
            tournament_data = update_pairings(
                guild_id=interaction.guild_id,
                tournament_name=name,
                round_num=str(round_num),
                pairings_data=pairings_data
            )
        except FileNotFoundError:
            await interaction.followup.send(f"❌ Tournament **{name}** does not exist.", ephemeral=True)
            return

        # Notify the thread created during /tournament start
        thread_id = tournament_data.get("thread_id")
        thread = interaction.guild.get_thread(thread_id)

        embed = discord.Embed(
            title=f"🏆 {name} — Round {round_num} Pairings",
            description="Pairings have been updated! Use `/my_match` to view your table and opponent.",
            color=discord.Color.blue()
        )

        for division, players in pairings_data.get(str(round_num), {}).items():
            total_matches = len([p for p, info in players.items() if info["table"] != "Bye"]) // 2
            embed.add_field(
                name=division,
                value=f"**{len(players)}** Players | **{total_matches}** Active Tables",
                inline=False
            )

        if thread:
            await thread.send(embed=embed)
            await interaction.followup.send(f"✅ Round {round_num} posted in {thread.mention}!")
        else:
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="my_match", description="Lookup your current table assignment and opponent.")
    @app_commands.describe(
        tournament_name="Tournament name",
        player_name="Your full registered player name"
    )
    async def my_match(
        self,
        interaction: discord.Interaction,
        tournament_name: str,
        player_name: str
    ):
        status = get_player_status(interaction.guild_id, tournament_name, player_name)

        if not status:
            await interaction.response.send_message(
                f"❌ Could not find active pairings for **{player_name}** in **{tournament_name}**.",
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

    @tournament_group.command(name="end", description="Conclude tournament and cleanup storage/threads.")
    @app_commands.describe(name="Tournament name to delete")
    async def end_tournament(self, interaction: discord.Interaction, name: str):
        data = load_tournament(interaction.guild_id, name)
        if not data:
            await interaction.response.send_message(f"❌ Tournament **{name}** not found.", ephemeral=True)
            return

        thread_id = data.get("thread_id")
        if thread_id:
            thread = interaction.guild.get_thread(thread_id)
            if thread:
                await thread.delete()

        delete_tournament(interaction.guild_id, name)
        await interaction.response.send_message(f"🗑️ Tournament **{name}** ended and data cleaned up.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tournament(bot))