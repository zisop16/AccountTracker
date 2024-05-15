import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv, find_dotenv
import re
import asyncio

import ServerIDs

load_dotenv(find_dotenv())
BOT_TOKEN = os.getenv("TOKEN")

account_names = ["Seforius", "Gloopie1", "Syrup", "Ethan"]
reasons = ["PVP", "Questing", "Raiding", "Farming"]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = commands.Bot(intents=intents, command_prefix='/')

def toggle_invites(setting: bool):
    text = '1' if setting else '0'
    with open("invites.txt", 'w') as settings_file:
        settings_file.write(text)

def invites_allowed():
    with open("invites.txt", 'r') as settings_file:
        text = settings_file.read()
        return text == '1'

async def get_status_message(server: discord.Guild):
    status_channel = server.get_channel(ServerIDs.status_channel)
    messages = status_channel.history(limit=200, oldest_first=False)
    async for message in messages:
        if message.author == client.user:
            return message
    return None

@client.tree.command(name="invites")
@app_commands.describe(setting="Whether to allow invites")
async def set_invites_permission(interaction: discord.Interaction, setting: bool):
    """
    Configure invite permissions for the server
    If disabled, I will automatically delete all invite links generated by any user
    """
    await interaction.response.defer(ephemeral=True)
    toggle_invites(setting)
    await interaction.followup.send(content=f"I've {'enabled' if setting else 'disabled'} invite links for the server")

@client.tree.command(name="track")
async def start_tracking(interaction: discord.Interaction):
    """
    Make the tracker post an initial message tracking logins of each account
    """
    await interaction.response.defer(ephemeral=True)
    status_channel = interaction.guild.get_channel(ServerIDs.status_channel)
    
    status_embed = discord.Embed(
        title="Login Statuses"
    )
    for name in account_names:
        status_embed.add_field(name=f"Account: {name}", value="Status: Logged out", inline=False)

    message = await status_channel.send(embed=status_embed)
    await interaction.followup.send(embed=discord.Embed(
        description = f"I've begun tracking your logins in {status_channel.mention}"
    ), ephemeral=True)


info_regex = re.compile("Status: Logged in by (.*)\nFor: (.*)")

@client.tree.command(name="login")
@app_commands.describe(account_name="The account to log in", reason="Reason for using the account")
@app_commands.choices(account_name=[
    app_commands.Choice(name=name, value=name) for name in account_names
])
async def login(interaction: discord.Interaction, account_name: app_commands.Choice[str], reason: str):
    """
    Indicate to others that you have logged into an account, and specify a reason
    """
    await interaction.response.defer(ephemeral=True)
    status_message = await get_status_message(interaction.guild)
    if status_message is None:
        await interaction.followup.send(
            content="I looked through the most recent 200 messages of the status channel, " +
            "and couldn't find mine. Please stop spamming this channel, or use /track to begin tracking.", 
            ephemeral=True
        )
        return
    embed: discord.Embed = status_message.embeds[0]
    target = f"Account: {account_name.value}"
    for ind, field in enumerate(embed.fields):
        if field.name == target:
            # Status is either of the form
            # Status: Logged out
            # Or 
            # Status: Logged in by {username}\nFor: {reason}
            account_status = field.value
            target_ind = ind
            logged_in: re.Match[str] = info_regex.match(account_status)
            if logged_in is not None:
                previous_user, previous_reason = logged_in.groups()
            break

    if logged_in:
        await interaction.followup.send(content=f"Account: {account_name.value} is already being used by {previous_user}\nReason: {previous_reason}")
        return
    
    embed.remove_field(target_ind)
    embed.add_field(name=f"Account: {account_name.value}", value=f"Status: Logged in by {interaction.user.mention}\nFor: {reason}", inline=False)
    await status_message.edit(embed=embed)

    await interaction.followup.send(embed=discord.Embed(
        description = f"I've updated the account statuses to indicate that you're currently logged into: {account_name.value}"
    ), ephemeral=True)

@client.tree.command(name="logout")
@app_commands.describe(account_name="The account to log out")
@app_commands.choices(account_name=[
    app_commands.Choice(name=name, value=name) for name in account_names
])
async def logout(interaction: discord.Interaction, account_name: app_commands.Choice[str]):
    """
    Indicate to others that you have logged out of an account
    """
    await interaction.response.defer(ephemeral=True)
    status_message = await get_status_message(interaction.guild)
    if status_message is None:
        await interaction.followup.send(
            content="I looked through the most recent 200 messages of the status channel, " +
            "and couldn't find mine. Please stop spamming this channel, or use /track to begin tracking.", 
            ephemeral=True
        )
        return
    embed: discord.Embed = status_message.embeds[0]
    target = f"Account: {account_name.value}"
    for ind, field in enumerate(embed.fields):
        if field.name == target:
            # Status is either of the form
            # Status: Logged out
            # Or 
            # Status: Logged in by {username}\nFor: {reason}
            account_status = field.value
            target_ind = ind
            logged_in: re.Match[str] = info_regex.match(account_status)
            if logged_in is not None:
                previous_user, previous_reason = logged_in.groups()
            break
    if not logged_in:
        await interaction.followup.send(content="You can't log this account out, because nobody is using it.", ephemeral=True)
        return
    embed.remove_field(target_ind)
    embed.add_field(name=f"Account: {account_name.value}", value=f"Status: Logged out", inline=False)
    logout_message = interaction.followup.send(
        content=f"You logged {previous_user} out of the account: {account_name.value}", ephemeral=True
    )
    edit = status_message.edit(embed=embed)
    await logout_message, await edit

@tasks.loop(seconds = 30)
async def delete_invites():
    if invites_allowed():
        return
    server = client.get_guild(ServerIDs.server)
    for invite in await server.invites():
        await invite.delete()

@client.event
async def on_ready():
    await client.tree.sync()
    await delete_invites.start()

client.run(BOT_TOKEN)