import discord
import random
import string
import asyncio
import os
import time
from flask import Flask, request, jsonify
from threading import Thread
import logging
from discord.ext import commands

# Flask app setup
app = Flask(__name__)

# Store verification codes, temporary access, and bot configuration
verification_codes = {}
temp_access = {}  # Store user IDs and expiration times
bot_config = {
    "verification_category": None  # Will store the category ID
}

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
    
    # Schedule the verification room creation and code sending
    asyncio.run_coroutine_threadsafe(create_verification_room(username, code), bot.loop)
    
    return jsonify({'success': True, 'message': 'Verification code sent'})

@app.route('/api/verification/verify', methods=['POST'])
def verify_code():
    data = request.json
    username = data.get('discordUsername')
    code = data.get('code')
    
    if not username or not code:
        return jsonify({'success': False, 'message': 'Username and code are required'}), 400
    
    # Check if user has temporary access
    for user_id, expiry in temp_access.items():
        user = None
        for guild in bot.guilds:
            user = guild.get_member(int(user_id))
            if user and user.name.lower() == username.lower():
                if time.time() < expiry:
                    # User has temporary access
                    return jsonify({'success': True, 'message': 'Verification successful (temporary access)'})
    
    stored_code = verification_codes.get(username)
    
    if not stored_code:
        return jsonify({'success': False, 'message': 'No verification code found for this user'}), 400
    
    if code == stored_code:
        # Remove the code after successful verification
        verification_codes.pop(username)
        return jsonify({'success': True, 'message': 'Verification successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid verification code'}), 400

async def create_verification_room(username, code):
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
        
        # Check if verification category is set
        if not bot_config["verification_category"]:
            logger.error("Verification category not set")
            await user.send("Error: Verification category not set. Please contact an administrator.")
            return
        
        # Get the guild and category
        guild = user.guild
        category = guild.get_channel(bot_config["verification_category"])
        
        if not category:
            logger.error("Verification category not found")
            await user.send("Error: Verification category not found. Please contact an administrator.")
            return
        
        # Create a private channel for the user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Check if a channel already exists for this user
        existing_channel = discord.utils.get(category.channels, name=f"verify-{user.name.lower()}")
        
        if existing_channel:
            channel = existing_channel
            logger.info(f"Using existing verification channel for {user.name}")
        else:
            channel = await guild.create_text_channel(
                name=f"verify-{user.name.lower()}",
                category=category,
                overwrites=overwrites
            )
            logger.info(f"Created verification channel for {user.name}")
        
        # Send the verification code in the channel
        embed = discord.Embed(
            title="Verification Code",
            description=f"Your verification code is: **{code}**\nPlease enter this code in the application to complete verification.",
            color=discord.Color.blue()
        )
        
        await channel.send(f"Welcome {user.mention}!", embed=embed)
        logger.info(f"Verification code sent to {username} in verification channel")
        
    except Exception as e:
        logger.error(f"Error creating verification room for {username}: {e}")
        if user:
            await user.send(f"An error occurred: {str(e)}")

# Run Flask in a separate thread
def run_flask():
    app.run(host='0.0.0.0', port=5000)

# Custom help command
class MyHelpCommand(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        # Show main commands
        embed = discord.Embed(title="Bot Commands", description="Check out the bot commands!", color=discord.Color.blue())
        for cog, commands in mapping.items():
            command_list = [command.name for command in commands if not command.hidden]
            if command_list:
                embed.add_field(name=cog.qualified_name if cog else "Main Commands", value="\n".join(command_list), inline=False)
        channel = self.context.channel
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        # Information about a single command
        embed = discord.Embed(title=f"{command.name} Command", description=command.help or "No description.", color=discord.Color.green())
        await self.context.send(embed=embed)

    async def send_cog_help(self, cog):
        # Information about a specific cog
        embed = discord.Embed(title=f"{cog.qualified_name} Commands", description="Commands under this cog", color=discord.Color.orange())
        for command in cog.get_commands():
            embed.add_field(name=command.name, value=command.help or "No description.", inline=False)
        await self.context.send(embed=embed)

# Set the custom help command
bot.help_command = MyHelpCommand()

# Bot's on_ready event (when bot is ready)
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # Set the bot's presence (status)
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

# Ping command
@bot.command()
async def ping(ctx):
    """Ping command!"""
    await ctx.send('Pong!')

# Roll command
@bot.command()
async def roll(ctx, dice: str):
    """Roll a dice! Example usage: !roll 2d6"""
    await ctx.send(f'Rolled dice result: {dice}')

# Profile command
@bot.command()
async def profile(ctx, member: discord.Member = None):
    """Shows a user's profile picture."""
    member = member or ctx.author  # Use the provided member or the command author
    await ctx.send(member.avatar.url)

# NEW COMMAND: Set Category for verification rooms
@bot.command()
async def setcategory(ctx, category_id: str = None):
    """Sets the category for verification rooms. Usage: !setcategory <category_id>"""
    # Check if user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need administrator permissions to use this command.")
        return
    
    if not category_id:
        await ctx.send("Please provide a category ID. Usage: `!setcategory <category_id>`")
        return
    
    # Remove # if present (in case they use #category-id format)
    category_id = category_id.replace('#', '').strip()
    
    try:
        # Try to convert to int
        category_id = int(category_id)
    except ValueError:
        await ctx.send("Invalid category ID. Please provide a valid category ID.")
        return
    
    # Find the category
    category = ctx.guild.get_channel(category_id)
    
    if not category or category.type != discord.ChannelType.category:
        await ctx.send("Category not found. Please provide a valid category ID.")
        return
    
    # Store the category ID in the bot configuration
    bot_config["verification_category"] = category.id
    await ctx.send(f"Verification category set to '{category.name}' (ID: {category.id})")

# NEW COMMAND: Verify a user without code or give temporary access
@bot.command()
async def verify(ctx, member: discord.Member = None, time_minutes: int = 0):
    """Verifies a user without code or gives temporary access. Usage: !verify @user [time_in_minutes]"""
    # Check if user has permission to verify others
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You need 'Manage Roles' permission to verify users.")
        return
    
    if not member:
        await ctx.send("Please mention a user to verify. Usage: `!verify @user [time_in_minutes]`")
        return
    
    if time_minutes > 0:
        # Give temporary access
        expiry_time = time.time() + (time_minutes * 60)
        temp_access[str(member.id)] = expiry_time
        
        await ctx.send(f"{member.mention} has been granted temporary access for {time_minutes} minutes.")
        
        # Send DM to the user
        try:
            await member.send(f"You have been granted temporary access for {time_minutes} minutes.")
        except:
            await ctx.send("Could not send DM to the user, but temporary access has been granted.")
        
        # Schedule removal of temporary access
        async def remove_temp_access():
            await asyncio.sleep(time_minutes * 60)
            if str(member.id) in temp_access:
                del temp_access[str(member.id)]
                logger.info(f"Removed temporary access for {member.name}")
                try:
                    await member.send("Your temporary access has expired.")
                except:
                    pass
        
        asyncio.create_task(remove_temp_access())
    else:
        # Permanent verification - you could add a role here if needed
        await ctx.send(f"{member.mention} has been verified permanently.")
        
        # Send DM to the user
        try:
            await member.send("You have been verified permanently.")
        except:
            await ctx.send("Could not send DM to the user, but verification has been completed.")

# NEW COMMAND: List all verification channels
@bot.command()
async def listverify(ctx):
    """Lists all verification channels."""
    # Check if user has permission
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.send("You need 'Manage Channels' permission to list verification channels.")
        return
    
    # Check if verification category is set
    if not bot_config["verification_category"]:
        await ctx.send("Verification category not set. Please use `!setcategory` first.")
        return
    
    # Get the category
    category = ctx.guild.get_channel(bot_config["verification_category"])
    if not category:
        await ctx.send("Verification category not found. Please use `!setcategory` again.")
        return
    
    # List all channels in the category
    channels = category.channels
    if not channels:
        await ctx.send("No verification channels found.")
        return
    
    # Create an embed with the list of channels
    embed = discord.Embed(
        title="Verification Channels",
        description=f"Total: {len(channels)} channels",
        color=discord.Color.blue()
    )
    
    for channel in channels:
        # Get the user from the channel name
        username = channel.name.replace("verify-", "")
        embed.add_field(name=channel.name, value=f"Created: {channel.created_at.strftime('%Y-%m-%d %H:%M')}", inline=False)
    
    await ctx.send(embed=embed)

if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Set your token here
    TOKEN = os.environ.get("DISCORD_TOKEN")
    
    # Start the Discord bot
    bot.run(TOKEN)