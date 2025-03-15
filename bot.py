# NEW COMMAND: Remove a user from verification list
@bot.command()
async def removeverify(ctx, member: discord.Member = None):
    """Removes a user from the verification list and deletes their channel. Usage: !removeverify @user"""
    # Check if user has permission
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You need 'Manage Roles' permission to remove users from verification.")
        return
    
    if not member:
        await ctx.send("Please mention a user to remove. Usage: `!removeverify @user`")
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
    
    # Find the user's verification channel
    channel_name = f"verify-{member.name.lower()}"
    channel = discord.utils.get(category.channels, name=channel_name)
    
    # Remove from temporary access if present
    removed_temp = False
    if str(member.id) in temp_access:
        del temp_access[str(member.id)]
        removed_temp = True
    
    # Remove from verification codes if present
    removed_code = False
    for username, code in list(verification_codes.items()):
        if username.lower() == member.name.lower() or (
            '#' in username and username.split('#')[0].lower() == member.name.lower()
        ):
            verification_codes.pop(username)
            removed_code = True
    
    # Delete the channel if it exists
    if channel:
        try:
            await channel.delete()
            await ctx.send(f"Deleted verification channel for {member.mention}")
        except Exception as e:
            await ctx.send(f"Error deleting channel: {str(e)}")
    
    # Send summary
    status_message = []
    if removed_temp:
        status_message.append("Removed temporary access")
    if removed_code:
        status_message.append("Removed verification code")
    if not channel and not removed_temp and not removed_code:
        await ctx.send(f"No verification data found for {member.mention}")
    else:
        status = ", ".join(status_message)
        await ctx.send(f"Removed {member.mention} from verification. {status if status else ''}")

# NEW COMMAND: Clear all verification channels
@bot.command()
async def clearverify(ctx):
    """Clears all verification channels and data. Usage: !clearverify"""
    # Check if user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need administrator permissions to clear all verification data.")
        return
    
    # Ask for confirmation
    confirm_msg = await ctx.send("⚠️ This will delete ALL verification channels and data. Type `confirm` to proceed.")
    
    def check(m):
        return m.author == ctx.author and m.content.lower() == "confirm" and m.channel == ctx.channel
    
    try:
        # Wait for confirmation
        await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await confirm_msg.edit(content="Operation cancelled: No confirmation received within 30 seconds.")
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
    
    # Delete all channels in the category
    deleted_count = 0
    for channel in category.channels:
        try:
            await channel.delete()
            deleted_count += 1
        except Exception as e:
            await ctx.send(f"Error deleting channel {channel.name}: {str(e)}")
    
    # Clear all verification codes and temporary access
    verification_codes.clear()
    temp_access.clear()
    
    await ctx.send(f"Verification data cleared. Deleted {deleted_count} channels.")