import discord
from discord import app_commands
from discord.ext import commands

from utils.storage import load_tournament_by_thread, save_tournament_by_thread
from utils.tournament_helpers import (
    TO_ROLE_NAME,
    get_to_role,
    send_organizer_dm,
    resolve_player_name,
    get_registered_player_name,
    collect_all_player_names,
    player_name_autocomplete,
    all_player_names_autocomplete,
)


class TournamentPlayer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="my_standing",
        description="Lookup your current rank, record, and tiebreaker stats in this thread."
    )
    @app_commands.describe(player_name="Player name to look up (defaults to your registered name if omitted)")
    @app_commands.autocomplete(player_name=player_name_autocomplete)
    async def my_standing(self, interaction: discord.Interaction, player_name: str = None):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ `/my_standing` can only be used inside a tournament thread.",
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
        name="link",
        description="Link your Discord account to your player name in this tournament."
    )
    @app_commands.describe(player_name="Your full registered player name")
    @app_commands.autocomplete(player_name=all_player_names_autocomplete)
    async def link(self, interaction: discord.Interaction, player_name: str):
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ `/link` can only be used inside a tournament thread.",
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
        if existing_name == player_name:
            await interaction.response.send_message(
                f"❌ You're already registered as **{player_name}**.",
                ephemeral=True
            )
            return

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
            f"✅ You're now linked to **{player_name}**. You can use `/report_result` to report your matches."
            f"If you would like to receive notification when new pairings/standings is up, "
            f"remember to turn on 'Allow DMs from other members in this server' at this server -> Privacy Setting",
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
                "❌ You're not linked yet. Use `/link` to link your Discord account to your player name first.",
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
    await bot.add_cog(TournamentPlayer(bot))
