import discord
from discord.ext import commands
import random
import string
import asyncio
import os
import datetime
import json
import requests
import time
from flask import Flask, request, jsonify
from threading import Thread
import logging

# Flask app setup
app = Flask(__name__)

# Store verification codes
verification_codes = {}

# Generate a random verification code
def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Discord bot setup with PROPER INTENTS
intents = discord.Intents.default()
intents.message_content = True  # Privileged intent
intents.members = True          # Privileged intent - needed to access guild members
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask API endpoints
@app.route('/api/verification/request', methods=['POST'])
def request_verification():
    data = request.json
    username = data.get('discordUsername')
    
    if not username:
        return jsonify({'success': False, 'message': 'Discord username is required'}), 400
    
    # Generate a verification code
    code = generate_code()
    verification_codes[username] = code
    
    # Schedule the DM to be sent
    asyncio.run_coroutine_threadsafe(send_verification_dm(username, code), bot.loop)
    
    return jsonify({'success': True, 'message': 'Verification code sent'})

@app.route('/api/verification/verify', methods=['POST'])
def verify_code():
    data = request.json
    username = data.get('discordUsername')
    code = data.get('code')
    
    if not username or not code:
        return jsonify({'success': False, 'message': 'Username and code are required'}), 400
    
    stored_code = verification_codes.get(username)
    
    if not stored_code:
        return jsonify({'success': False, 'message': 'No verification code found for this user'}), 400
    
    if code == stored_code:
        # Remove the code after successful verification
        verification_codes.pop(username)
        return jsonify({'success': True, 'message': 'Verification successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid verification code'}), 400

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'bot_online': bot.is_ready()})

async def send_verification_dm(username, code):
    try:
        user = None
        logger.info(f"Attempting to find user: {username}")
        
        # Check if username includes discriminator (e.g., username#1234)
        if '#' in username:
            name, discriminator = username.split('#')
            logger.info(f"Looking for user with name: {name} and discriminator: {discriminator}")
            for guild in bot.guilds:
                for member in guild.members:
                    if member.name.lower() == name.lower() and member.discriminator == discriminator:
                        user = member
                        logger.info(f"Found user in guild: {guild.name}")
                        break
                if user:
                    break
        else:
            # Try to find by username only (less reliable)
            logger.info(f"Looking for user with name: {username} (no discriminator)")
            for guild in bot.guilds:
                for member in guild.members:
                    if member.name.lower() == username.lower():
                        user = member
                        logger.info(f"Found user in guild: {guild.name}")
                        break
                if user:
                    break
        
        if not user:
            logger.error(f"Could not find user: {username}")
            return
        
        # Create a fancy embed for the verification code
        embed = discord.Embed(
            title="Verification Code",
            description=f"Your verification code is: **{code}**\nPlease enter this code in the application to complete verification.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url="https://i.imgur.com/oBPXx0D.png")  # Verification icon
        embed.set_footer(text="This code will expire after verification")
        embed.timestamp = datetime.datetime.now()
        
        # Send the DM with the embed
        logger.info(f"Sending verification code to user: {user.name}")
        await user.send(embed=embed)
        logger.info(f"Verification code sent to {username}")
    except Exception as e:
        logger.error(f"Error sending DM to {username}: {e}")

# Run Flask in a separate thread
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# Custom help command with fancy embeds
class FancyHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="📚 Bot Commands",
            description="Here are all the available commands. Use `!help <command>` for more details on a specific command.",
            color=discord.Color.blurple()
        )
        
        for cog, cmds in mapping.items():
            filtered = await self.filter_commands(cmds, sort=True)
            command_signatures = [f"`!{c.name}`" for c in filtered]
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "General")
                embed.add_field(name=f"⚙️ {cog_name}", value=", ".join(command_signatures), inline=False)
        
        embed.set_footer(text=f"Type !help <command> for more info on a command.")
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Command: !{command.name}",
            description=command.help or "No description available.",
            color=discord.Color.green()
        )
        
        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(f"`!{alias}`" for alias in command.aliases), inline=False)
        
        embed.add_field(name="Usage", value=f"`!{command.name} {command.signature}`", inline=False)
        
        channel = self.get_destination()
        await channel.send(embed=embed)

# Set the custom help command
bot.help_command = FancyHelpCommand()

# Bot's on_ready event (when bot is ready)
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Set the bot's presence (status)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!help for commands"
        ),
        status=discord.Status.online
    )

# Welcome new members
@bot.event
async def on_member_join(member):
    # Send welcome message to the system channel if it exists
    if member.guild.system_channel:
        embed = discord.Embed(
            title=f"Welcome to {member.guild.name}!",
            description=f"Hey {member.mention}, welcome to the server! 🎉\nUse `!help` to see available commands.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{len(member.guild.members)}")
        
        await member.guild.system_channel.send(embed=embed)

# Utility Commands

@bot.command(name="ping", aliases=["latency"])
async def ping(ctx):
    """Check the bot's response time"""
    start_time = time.time()
    message = await ctx.send("Pinging...")
    end_time = time.time()
    
    # Calculate response times
    api_latency = round(bot.latency * 1000)
    bot_latency = round((end_time - start_time) * 1000)
    
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    embed.add_field(name="API Latency", value=f"{api_latency}ms", inline=True)
    embed.add_field(name="Bot Latency", value=f"{bot_latency}ms", inline=True)
    
    await message.edit(content=None, embed=embed)

@bot.command(name="roll", aliases=["dice"])
async def roll(ctx, dice: str = "1d6"):
    """Roll dice in NdN format (e.g. 2d6 for two six-sided dice)"""
    try:
        rolls, limit = map(int, dice.split('d'))
        
        if rolls > 25:
            await ctx.send("I can't roll more than 25 dice at once!")
            return
        
        if limit > 100:
            await ctx.send("Dice can't have more than 100 sides!")
            return
        
        results = [random.randint(1, limit) for _ in range(rolls)]
        
        # Create a fancy embed for the results
        embed = discord.Embed(
            title="🎲 Dice Roll Results",
            description=f"Rolling {dice}...",
            color=discord.Color.gold()
        )
        
        # Add individual rolls
        if len(results) > 1:
            embed.add_field(name="Individual Rolls", value=", ".join(str(r) for r in results), inline=False)
            embed.add_field(name="Total", value=str(sum(results)), inline=True)
            embed.add_field(name="Average", value=f"{sum(results)/len(results):.2f}", inline=True)
        else:
            embed.description = f"Rolling {dice}... Result: **{results[0]}**"
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error: {e}\nFormat must be NdN (e.g. 2d6)")

@bot.command(name="profile", aliases=["avatar", "pfp"])
async def profile(ctx, member: discord.Member = None):
    """Shows a user's profile information and avatar"""
    member = member or ctx.author
    
    embed = discord.Embed(
        title=f"{member.display_name}'s Profile",
        color=member.color
    )
    
    # Add user information
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Username", value=str(member), inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Status", value=str(member.status).title(), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    
    # Add roles if they exist
    if len(member.roles) > 1:  # Exclude @everyone
        role_list = [role.mention for role in reversed(member.roles) if role.name != "@everyone"]
        embed.add_field(name=f"Roles [{len(role_list)}]", value=" ".join(role_list) if role_list else "None", inline=False)
    
    # Add a larger avatar URL at the bottom
    embed.set_image(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name="serverinfo", aliases=["server"])
async def serverinfo(ctx):
    """Shows information about the server"""
    guild = ctx.guild
    
    # Count channels by type
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    
    # Count members by status
    total_members = guild.member_count
    online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
    
    # Create embed
    embed = discord.Embed(
        title=f"{guild.name} Server Information",
        description=guild.description or "No description",
        color=discord.Color.blue()
    )
    
    # Add server icon if it exists
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    # Add basic info
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    
    # Add member info
    embed.add_field(name="Members", value=f"Total: {total_members}\nOnline: {online_members}", inline=True)
    
    # Add channel info
    embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {categories}", inline=True)
    
    # Add role info
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    
    # Add server features if any
    if guild.features:
        embed.add_field(name="Features", value=", ".join(f"`{feature}`" for feature in guild.features), inline=False)
    
    # Add server banner if it exists
    if guild.banner:
        embed.set_image(url=guild.banner.url)
    
    await ctx.send(embed=embed)

@bot.command(name="weather")
async def weather(ctx, *, location: str):
    """Get the current weather for a location"""
    try:
        # You would need to sign up for a weather API like OpenWeatherMap
        # This is a placeholder - replace API_KEY with your actual key
        API_KEY = os.environ.get("WEATHER_API_KEY", "")
        if not API_KEY:
            await ctx.send("Weather API key not configured!")
            return
            
        # Make API request
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()
        
        if response.status_code != 200:
            await ctx.send(f"Error: Could not find weather for '{location}'")
            return
        
        # Extract weather data
        city = data["name"]
        country = data["sys"]["country"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        description = data["weather"][0]["description"]
        icon_code = data["weather"][0]["icon"]
        
        # Create weather embed
        embed = discord.Embed(
            title=f"Weather in {city}, {country}",
            description=f"**{description.capitalize()}**",
            color=discord.Color.blue()
        )
        
        # Add weather icon
        embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{icon_code}@2x.png")
        
        # Add weather details
        embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
        embed.add_field(name="Feels Like", value=f"{feels_like}°C", inline=True)
        embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="Wind Speed", value=f"{wind_speed} m/s", inline=True)
        
        embed.set_footer(text="Powered by OpenWeatherMap")
        embed.timestamp = datetime.datetime.now()
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error retrieving weather data: {e}")

@bot.command(name="poll")
async def poll(ctx, question, *options):
    """Create a poll with reactions (usage: !poll "Question" "Option 1" "Option 2" ...)"""
    if len(options) < 2:
        await ctx.send("You need at least 2 options for a poll!")
        return
    if len(options) > 10:
        await ctx.send("You can't have more than 10 options!")
        return
    
    # Emoji options for the poll
    emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    # Create the poll embed
    embed = discord.Embed(
        title=f"📊 Poll: {question}",
        color=discord.Color.purple()
    )
    
    # Add options to the description
    description = []
    for i, option in enumerate(options):
        description.append(f"{emoji_numbers[i]} {option}")
    
    embed.description = "\n\n".join(description)
    embed.set_footer(text=f"Poll created by {ctx.author.display_name}")
    embed.timestamp = datetime.datetime.now()
    
    # Send the poll and add reactions
    poll_message = await ctx.send(embed=embed)
    
    for i in range(len(options)):
        await poll_message.add_reaction(emoji_numbers[i])

@bot.command(name="remind", aliases=["reminder"])
async def remind(ctx, time: str, *, reminder: str):
    """Set a reminder (usage: !remind 1h30m Check the oven)"""
    # Parse the time string (e.g., 1h30m)
    total_seconds = 0
    time_str = time.lower()
    
    # Extract hours, minutes, seconds
    if 'h' in time_str:
        hours, time_str = time_str.split('h', 1)
        total_seconds += int(hours) * 3600
    
    if 'm' in time_str:
        minutes, time_str = time_str.split('m', 1)
        total_seconds += int(minutes) * 60
    
    if 's' in time_str:
        seconds, time_str = time_str.split('s', 1)
        total_seconds += int(seconds)
    
    if total_seconds == 0:
        await ctx.send("Please specify a valid time (e.g., 1h30m)")
        return
    
    # Calculate when the reminder will trigger
    reminder_time = datetime.datetime.now() + datetime.timedelta(seconds=total_seconds)
    
    # Send confirmation
    await ctx.send(f"⏰ I'll remind you about: **{reminder}** in **{time}**")
    
    # Wait for the specified time
    await asyncio.sleep(total_seconds)
    
    # Send the reminder
    embed = discord.Embed(
        title="⏰ Reminder",
        description=reminder,
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Reminder set {time} ago")
    
    try:
        await ctx.author.send(embed=embed)
    except:
        await ctx.send(f"{ctx.author.mention}, here's your reminder: **{reminder}**")

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear a specified number of messages (default: 5)"""
    if amount < 1 or amount > 100:
        await ctx.send("I can only delete between 1 and 100 messages at a time.")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
    
    # Send confirmation that disappears after 5 seconds
    confirmation = await ctx.send(f"✅ Deleted {len(deleted)-1} messages.")
    await asyncio.sleep(5)
    await confirmation.delete()

@bot.command(name="verify")
async def verify(ctx, username: str):
    """Generate and send a verification code to a user"""
    # Generate a verification code
    code = generate_code()
    verification_codes[username] = code
    
    # Send the code via DM
    await send_verification_dm(username, code)
    
    # Send confirmation
    await ctx.send(f"Verification code sent to {username}. Check your DMs!")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}. Use `!help {ctx.command.name}` for proper usage.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")

if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Get token from environment variable
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("Error: No Discord token found. Set the DISCORD_TOKEN environment variable.")
    else:
        # Start the Discord bot
        bot.run(TOKEN)