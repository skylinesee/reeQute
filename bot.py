import discord
from discord.ext import commands
import os
import random
from datetime import datetime

# Set up intents for the bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create bot instance with command prefix
bot = commands.Bot(command_prefix='!', intents=intents)

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Bot is logged in as {bot.user}')
    print(f'Bot is in {len(bot.guilds)} servers')
    
    # Set bot status
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

# Event: New member joins
@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(f'Welcome to the server, {member.mention}! Type !help to see available commands.')

# Command: Ping
@bot.command()
async def ping(ctx):
    """Check the bot's response time"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'Pong! Latency: {latency}ms')

# Command: Roll dice
@bot.command()
async def roll(ctx, dice: str = '1d6'):
    """Roll dice in NdN format (e.g. 2d6 for two six-sided dice)"""
    try:
        rolls, limit = map(int, dice.split('d'))
        if rolls > 10:
            await ctx.send("I can't roll more than 10 dice at once!")
            return
        
        results = [random.randint(1, limit) for _ in range(rolls)]
        await ctx.send(f'🎲 Results: {", ".join(str(r) for r in results)}')
        if len(results) > 1:
            await ctx.send(f'Total: {sum(results)}')
    except Exception:
        await ctx.send('Format must be NdN (e.g. 2d6)')

# Command: Server info
@bot.command()
async def serverinfo(ctx):
    """Display information about the server"""
    guild = ctx.guild
    
    # Create an embed with server information
    embed = discord.Embed(title=f"{guild.name} Info", color=discord.Color.blue())
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="Channels", value=f"{len(guild.text_channels)} text | {len(guild.voice_channels)} voice", inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await ctx.send(embed=embed)

# Command: Poll
@bot.command()
async def poll(ctx, question, *options):
    """Create a simple poll (usage: !poll "Question" "Option 1" "Option 2" ...)"""
    if len(options) < 2:
        await ctx.send("You need at least 2 options for a poll!")
        return
    if len(options) > 10:
        await ctx.send("You can't have more than 10 options!")
        return
    
    # Emoji numbers for options
    emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    # Create embed for poll
    embed = discord.Embed(title=question, color=discord.Color.green())
    description = []
    
    for i, option in enumerate(options):
        description.append(f"{emoji_numbers[i]} {option}")
    
    embed.description = "\n".join(description)
    embed.set_footer(text=f"Poll by {ctx.author.display_name}")
    
    poll_message = await ctx.send(embed=embed)
    
    # Add reactions
    for i in range(len(options)):
        await poll_message.add_reaction(emoji_numbers[i])

# Command: Clear messages
@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear a specified number of messages (default: 5)"""
    if amount < 1 or amount > 100:
        await ctx.send("I can only delete between 1 and 100 messages at a time.")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
    await ctx.send(f"Deleted {len(deleted)-1} messages.", delete_after=5)

# Command: User info
@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """Display information about a user"""
    member = member or ctx.author
    
    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    
    embed = discord.Embed(title=f"{member.display_name}'s Info", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    
    if roles:
        embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles), inline=False)
    
    await ctx.send(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use !help to see available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        print(f"An error occurred: {error}")

# Run the bot with token from environment variable
if __name__ == "__main__":
    # Get token from environment variable
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("Error: No Discord token found. Set the DISCORD_TOKEN environment variable.")
    else:
        bot.run(TOKEN)