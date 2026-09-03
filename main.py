import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
# Optional: Set GUILD_ID in .env for instant slash command sync during development
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")


class TournamentBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True  # Required if handling standard text commands

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        """Asynchronously loads cogs and syncs application slash commands."""
        # Load the tournament cogs (split across admin and player command sets)
        await self.load_extension("cogs.tournament_admin")
        print("✅ Cog loaded: cogs.tournament_admin")

        await self.load_extension("cogs.tournament_player")
        print("✅ Cog loaded: cogs.tournament_player")

        # Sync slash command tree
        if DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"⚡ Instant slash command sync enabled for Dev Guild ID: {DEV_GUILD_ID}")
        else:
            await self.tree.sync()
            print("🌐 Global slash commands synced (may take up to an hour to propagate globally).")

    async def on_ready(self) -> None:
        print(f"🤖 Logged in as {self.user} (ID: {self.user.id})")
        print("🏆 Tournament Manager Bot is online and listening for commands.")


async def main():
    if not TOKEN:
        raise ValueError("❌ DISCORD_TOKEN is missing. Ensure it is defined in your environment or .env file.")

    bot = TournamentBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())