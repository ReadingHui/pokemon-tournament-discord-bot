import discord
from discord import app_commands

from utils.storage import load_tournament_by_thread

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


async def handle_tournament_permission_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
) -> None:
    """Shared cog_app_command_error logic for tournament cogs guarded by is_tournament_admin()."""
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


def get_to_role(guild: discord.Guild) -> discord.Role | None:
    """Looks up the Tournament Organizer role in the guild, if it exists."""
    return discord.utils.get(guild.roles, name=TO_ROLE_NAME)


async def send_dm(
    client: discord.Client,
    user_id: int,
    content: str = None,
    embed: discord.Embed = None
) -> bool:
    """Attempts to DM a Discord user by ID. Returns True if the DM was sent successfully."""
    try:
        user = client.get_user(user_id) or await client.fetch_user(user_id)
        await user.send(content=content, embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return False


async def send_organizer_dm(client: discord.Client, tournament_data: dict, content: str) -> bool:
    """Attempts to DM the tournament's creator. Returns True if the DM was sent successfully."""
    organizer_id = tournament_data.get("organizer_id")
    if not organizer_id:
        return False

    return await send_dm(client, organizer_id, content=content)


def get_registered_player_name(tournament_data: dict, user_id: int) -> str | None:
    """Returns the player name a given Discord user is registered as, if any."""
    registrations = tournament_data.get("registrations", {})
    for player_name, registered_id in registrations.items():
        if registered_id == user_id:
            return player_name
    return None


def resolve_player_name(
    tournament_data: dict,
    interaction: discord.Interaction,
    player_name: str | None
) -> tuple[str | None, str | None]:
    """Resolves which player name a lookup command should use: the explicit argument if given,
    otherwise the caller's linked name. Returns (name, error_message); error_message is
    set (and name is None) if no name was given and the caller isn't linked."""
    if player_name:
        return player_name, None

    registered_name = get_registered_player_name(tournament_data, interaction.user.id)
    if registered_name:
        return registered_name, None

    return None, (
        "❌ You didn't specify a `player_name` and you're not linked yet. "
        "Use `/link` to link your Discord account, or pass a `player_name` explicitly."
    )


def collect_all_player_names(tournament_data: dict) -> set[str]:
    """Union of every player name known to the tournament: roster, standings, and all round pairings."""
    names = set(tournament_data.get("players", {}).keys())
    names.update(tournament_data.get("standings", {}).keys())
    for round_pairings in tournament_data.get("rounds", {}).values():
        for div_players in round_pairings.values():
            names.update(div_players.keys())
    return names


async def player_name_autocomplete(
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
