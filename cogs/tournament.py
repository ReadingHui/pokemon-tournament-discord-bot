import discord
from discord import app_commands
from discord.ext import commands

class TournamentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Map active tournament thread IDs to tournament data
        # Structure: { thread_id (int): {"name": str, ...} }
        self.active_tournaments: dict[int, dict] = {}

    # 1. Admin-only: Create Tournament
    @app_commands.command(name="create_tournament", description="Create a new tournament")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_tournament(self, interaction: discord.Interaction, name: str):
        # Create dedicated thread
        thread = await interaction.channel.create_thread(name=f"🏆-{name}")
        
        # Register the EXACT thread ID
        self.active_tournaments[thread.id] = {
            "name": name,
            "created_by": interaction.user.id
        }

        await interaction.response.send_message(
            f"Tournament **{name}** created! Managed inside {thread.mention}", 
            ephemeral=True
        )

    # 1. Admin-only: Delete Tournament (Restricted strictly to the specific created thread)
    @app_commands.command(name="delete_tournament", description="Delete this active tournament thread")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete_tournament(self, interaction: discord.Interaction):
        thread_id = interaction.channel.id

        # Check if the current channel is a registered tournament thread
        if thread_id not in self.active_tournaments:
            await interaction.response.send_message(
                "❌ This command can only be used inside the exact thread created for an active tournament.",
                ephemeral=True
            )
            return

        tournament_data = self.active_tournaments.pop(thread_id)
        tournament_name = tournament_data["name"]

        await interaction.response.send_message(
            f"🗑️ Deleting tournament **{tournament_name}** and removing thread...",
            ephemeral=True
        )
        
        # Delete the exact thread channel
        await interaction.channel.delete()

    # 2. General Access: /my_match (Restricted to the specific tournament thread)
    @app_commands.command(name="my_match", description="View your current match pairing")
    async def my_match(self, interaction: discord.Interaction):
        thread_id = interaction.channel.id

        if thread_id not in self.active_tournaments:
            await interaction.response.send_message(
                "❌ Please use this command inside the specific tournament thread.", 
                ephemeral=True
            )
            return

        tournament_name = self.active_tournaments[thread_id]["name"]
        await interaction.response.send_message(
            f"Fetching match for **{interaction.user.display_name}** in **{tournament_name}**...",
            ephemeral=True
        )

    # Error handler for missing permissions
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "⛔ You do not have permission to run this command.", 
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(TournamentCog(bot))