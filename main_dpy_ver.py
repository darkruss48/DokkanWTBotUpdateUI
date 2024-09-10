from inspect import Attribute

from torch.nn.functional import embedding

import discord
from discord.ext import commands
import json
from render import render
import os 
from datetime import datetime, timezone, timedelta
from discord import app_commands
import typing # autocompletion
import asyncio

# Modules nécessaires : requests, matplotlib, discord.py,
# debug TOKEN_M = 'xxx' # perso
TOKEN = 'xxx' # doritos
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents = intents)

# Remove original help command
bot.remove_command('help')

output_dir = 'temp_top100_data'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def load_data():
    with open('data.json', 'r') as f:
        return json.load(f)

def load_discord_users():
    if not os.path.exists('discord_users.json'):
        with open('discord_users.json', 'w') as f:
            json.dump({}, f)
    with open('discord_users.json', 'r') as f:
        return json.load(f)

def save_discord_users(discord_users):
    with open('discord_users.json', 'w') as f:
        json.dump(discord_users, f, indent=5)

def latest_fetch():
    output_dir = "fetches"
    i = 0
    while True:
        filename = f"fetch{i}.json"
        if not os.path.exists(os.path.join(output_dir, filename)):
            break
        i += 1
    return f"{output_dir}/fetch{i-1}.json"

def time_data():
    latest_fetch_path = latest_fetch()

    if latest_fetch_path:
        with open(latest_fetch_path, 'r') as file:
            data = json.load(file)
            print(f"Data loaded from the latest fetch file: {latest_fetch_path}")
            update = datetime.utcfromtimestamp(data["userlist"]["updated_at"]).replace(tzinfo=timezone.utc)
            start = datetime.fromisoformat(data["start_at"]).astimezone(timezone.utc)
            end = datetime.fromisoformat(data["end_at"]).astimezone(timezone.utc)
            total = end - start
            left = end - update
            elapsed = update - start
            return data["userlist"]["updated_at"], start, end, total, left, elapsed
    else:
        print("No fetch files found in the directory.")
        return None, None, None, None, None, None
    #yeah it's fucking ugly but I might need them on multiple occasions so I'll just get everything to make it simplier
    #update, start, end, total, left, elapsed = time_data()



def find_gap(main_player, data):
    main_rank = main_player["ranks"][-1]
    top, bottom = None, None
    for player in data:
        if player["ranks"][-1] == (main_rank - 1):
            top = player
        if player["ranks"][-1] == (main_rank + 1): 
            bottom = player
    return top, bottom 

def find_player(data, identifier):
    for player in data:
        if player['name'] == str(identifier) or player['id'] == (int(identifier) if identifier.isdigit() == True else 0):
            return player
    return None

@bot.event
async def on_ready():
    # await bot.tree.sync(guild=discord.Object(id=1276254455926489232)) # 1276254455926489232))
    print(f'Logged in as {bot.user.name}')
    # print(bot.tree.get_commands()) # debug

""""@bot.hybrid_command(name='sync', description='Owner only')
async def sync(interaction: discord.Interaction):
    if interaction.author.id == 688774032136601601:
        await bot.tree.sync(guild=None)# interaction.channel.guild) #  discord.Object(id=1276254455926489232)
        print('Command tree synced.')
    else:
        await interaction.response.send_message('You must be the owner to use this command!')"""

# Autocompletion max
async def autocompletion_type_max(interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
    choices = [
        app_commands.Choice(name=a, value=a)
        for a in ["wins", "points"]
        ]
    return choices

@bot.tree.command(name="max", description="Show the maximum points or wins of a player.")
@app_commands.describe(type="The type of maximum you want to see. Either 'points' or 'wins'.", identifier="The identifier of the player you want to see the maximum of.")
@app_commands.autocomplete(type=autocompletion_type_max)
async def max_(ctx, type: str = "points", identifier: str = None):
    # check type
    if type not in ["wins", "points"]:
        await ctx.response.send_message("Please provide a valid type. Either 'points' or 'wins'.")
        return
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    maximum = player.get(f"max_{type}")
    if maximum:
        render([player], output_dir, f"max_{type}")
        current_max = maximum[-1] 
        image_path = os.path.join(output_dir, player["name"].replace('$$', '\$\$'), f'max_{type}.png')

        embed = discord.Embed(
            title=f"{player['name']}'s maximum {type} achieveable",
            description=f"Your current max is **{round(current_max, 0):,} {type}**.",
            color=discord.Color.green()
        )
        if os.path.exists(image_path):
            file = discord.File(image_path, filename=f"max_{type}.png")
            embed.set_image(url=f"attachment://max_{type}.png")
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(file=file, embed=embed)
        else:
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(embed=embed)
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
    else:
        await ctx.response.send_message(f"No data available for points. (either fetch failed and it's a huge skill issue or you're not in the top100 and that's a skill issue as well)")

@bot.tree.command(name="target", description="Show the pace needed to reach a goal.")
@app_commands.describe(goal="The goal you want to reach.", identifier="The identifier of the player you want to see the pace of.")
async def target(ctx, goal: str, identifier: str = None):
    # Test goal (500M --> 500000000)
    goal = goal.replace("M" if "M" in goal else "m", "000000").replace("k", "000")
    try:
        goal = int(goal)
    except ValueError: # l'argument fourni n'est pas un nombre
        await ctx.response.send_message("Please provide a valid number as a goal.", ephemeral=True)
        return
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    if identifier is None:
        # cette ligne va raise un AttributeError si l'author n'est pas register, on modifie donc
        try:
            user_id = str(ctx.user.id)
        except AttributeError as e:
            # raise e # debug
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link).")
            return
        # tout va bien si on arrive là, on continue
        identifier = discord_users.get(user_id)
        if identifier is None: # si c'est None pour une raison ou pour une autre, même tarif c'est qu'il n'est pas register
            await ctx.send("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link).")
            return
    if goal == -1 : # devrait être useless
        await ctx.send("Please provide a goal")
        return
    player = find_player(players, identifier)
    if player is None:
        await ctx.send(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    wins_points_ratio = player["points_wins"][-1]
    update, start, end, total, left, elapsed = time_data()
    req_pace = (goal - player["points"][-1]) / (left.days * 24 + left.seconds / 3600)
    req_wins_pace = req_pace / wins_points_ratio
    # Check si le nombre de points est plus petit que goal
    if player["points"][-1] >= goal: # plus grand, problème
        addtt = "**:warning: You already have more points than your goal, thus the pace needed is 0.**\n\n"
    else: # rien à signaler, circulez monsieur bonne journée 👮
        addtt = ""
    # await ctx.send(f"Based on your current points, your goal, the time left and your average points/wins ratio.\n You would need to have a pace of {req_wins_pace} wins/hour to be able to reach {goal} points")
    embed = discord.Embed(
        title=f"{player['name']}'s target pace",
        color=discord.Color.green(),
        description=f"{addtt}• You would need to have a pace of **{round(req_wins_pace, 2)}** wins/hour to be able to reach **{goal:,}** points.\n\n_Note : this is based on your current points, your goal, the time left and your average points/wins ratio._",
    )
    await ctx.response.send_message(embed=embed)

@bot.tree.command(name='highest', description="Show the highest pace of a person was.")#A command to show what the highest pace of a person was (it was in the TODO so I guess someone asked for it)
@app_commands.describe(identifier="The identifier of the player you want to see the highest pace of.")
async def highest(ctx, identifier: str = None):
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    paces = player.get("wins_pace")
    highest_pace = 0
    for i in paces:
        if i>highest_pace:
            highest_pace = i
    # await ctx.send(highest_pace)
    embed = discord.Embed(
            title=f"{player['name']}'s highest pace",
            description=f"The highest pace you've had was **{highest_pace}**.",
            color=discord.Color.green()
        )
    # embed.set_footer(text="Provided by DiscordHosting.com")
    await ctx.response.send_message(embed=embed)

# Autocompletion leaderboard
async def autocompletion_type_lb(interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
    choices = [
        app_commands.Choice(name=a, value=a)
        for a in ["wins_pace", "points_pace", "wins", "points"]
        ]
    return choices

@bot.tree.command(name="leaderboard", description="Show the top players leaderboard.")
@app_commands.autocomplete(type=autocompletion_type_lb)
@app_commands.describe(type="The type of leaderboard you want to see. Either 'wins', 'points', 'wins_pace' or 'points_pace'.", page="The page of the leaderboard you want to see.")
async def leaderboard(ctx, type: str = "wins_pace", page: int = 1):
    # vérifier si le type est valide
    if type not in ["wins_pace", "points_pace", "wins", "points"]:
        await ctx.response.send_message("Please provide a valid type. Either 'wins_pace', 'points_pace', 'wins' or 'points'.")
        return
    players = load_data()
    update, start, end, total, left, elapsed = time_data()
    
    lb = []
    for player in players:
        lb.append((player["name"], player[type][-1]))
    final_lb = sorted(lb, key=lambda x: x[1], reverse=True)
    
    players_per_page = 10
    total_pages = (len(final_lb) + players_per_page - 1) // players_per_page  # Ceiling division

    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    start_index = (page - 1) * players_per_page
    end_index = start_index + players_per_page
    
    embed = discord.Embed(
        title="🏆 Top Players Leaderboard 🏆",
        description=f"Here are the players ranked {start_index + 1} to {min(end_index, len(final_lb))} with the highest {type}.",
        color=discord.Color.gold()
    )
    
    for idx, (name, comp) in enumerate(final_lb[start_index:end_index], start=start_index + 1):
        if idx == 1:
            rank_emoji = "🥇"
        elif idx == 2:
            rank_emoji = "🥈"
        elif idx == 3:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"**#{idx}**"
        # majuscule
        type = type.capitalize()
        embed.add_field(
            name=f"{rank_emoji} {name}",
            value=f"{type}: **{comp:,}**",
            inline=False
        )
    
    embed.set_footer(text=f"Page {page} of {total_pages}")
    await ctx.response.send_message(embed=embed)


@bot.tree.command(name = "gap", description="Show the gap between the player and the player above and below (if any).")
@app_commands.describe(identifier="The identifier of the player you want to see the gap of.")
async def gap(ctx, identifier: str = None):
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    pro, noob = find_gap(player, players)
    embed = discord.Embed(
        title=f"{player['name']} - Points Gap",
        description=f"Points gap comparison for {player['name']}",
        color=0x00b0f4
    )
    pro_gap = abs(pro['points'][-1] - player['points'][-1]) if pro else 1e99 #SUPER UGLY FUCKING HELL PLEASE KILL ME 
    if pro:
        delta_pro = pro_gap - abs(pro['points'][-2] - player['points'][-2]) if len(player['points'])>=2 and len(pro['points'])>=2 else 0
    noob_gap = abs(noob['points'][-1] - player['points'][-1]) if noob else 1e99
    if noob:
        delta_noob = noob_gap - abs(noob['points'][-2] - player['points'][-2]) if len(player['points'])>=2 and len(noob['points'])>=2 else 0
    player_arrow = "↗" if pro_gap < noob_gap else "↘"
    if pro:
        pro_arrow = "⬆️"
        """embed.add_field(
            name=f"{pro_arrow} Nr.{pro['ranks'][-1]}: {pro['name']}",
            value=f"Points: **{pro['points'][-1]:,}**\n"
                f"Gap: **{abs(pro['points'][-1] - player['points'][-1]):,} ({'+' if delta_pro > 0 else ''}{delta_pro:,})**",
            inline=False
        )"""
        estimated_time_pro = round((pro_gap / ( delta_pro * 4))*60)
        enplus = ""
        if pro['points_pace'][1] > player['points_pace'][1] : # l'user est plus lent que le prochain
            enplus = f"*:warning: {pro['name']} is farming faster than you ! Skill issue, take this L *"
        else: # on est plus rapide !
            enplus = f"          |--> `around {estimated_time_pro} minutes needed` --> ( <t:{int(update + estimated_time_pro*60)}:R> )"
        embed.add_field(name=f" ⬆️ - {pro['ranks'][-1]} - {pro['name']}",
                        value=f"• Points : **{pro['points'][-1]:,}**\n•   Gap   :  **{abs(pro['points'][-1] - player['points'][-1]):,}** **({'+' if delta_pro > 0 else ''}{delta_pro:,})**\n{enplus}",
                        inline=False)
    embed.add_field(
        name=f" ▶️ - {player['ranks'][-1]} - {player['name']}",
        value=f"Points: **{player['points'][-1]:,}**",
        inline=False
    )
    if noob:
        noob_arrow = "⬇️"
        embed.add_field(
            name=f" ⬇️ - {noob['ranks'][-1]} - {noob['name']}",
            value=f"Points: **{noob['points'][-1]:,}**\n"
                f"Gap: **{abs(player['points'][-1] - noob['points'][-1]):,} ({'+' if delta_noob > 0 else ''}{delta_noob:,})**\n",
            inline=False
        )
    
    embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
    # embed.set_footer(text="Provided by DiscordHosting.com")
    await ctx.response.send_message(embed=embed)
                       
@bot.tree.command(name='seed', description="Show the seed performance of a player.")
@app_commands.describe(identifier="The identifier of the player you want to see the seed performance of.")
async def seed(ctx, identifier: str = None):
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    seed_data = player.get("points_wins")
    if seed_data:
        render([player], output_dir, "points_wins")
        current_seed = seed_data[-1]
        image_path = os.path.join(output_dir, player["name"].replace('$$', '\$\$'), 'points_wins.png')

        embed = discord.Embed(
            title=f"{player['name']}'s seed performance",
            description=f"Your seed's current points/win ratio is **{int(current_seed):,}**.",
            color=discord.Color.purple()
        )
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="points_wins.png")
            embed.set_image(url=f"attachment://points_wins.png")
            # embed.set_footer(text="Provided by DiscordHosting.com")
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            await ctx.response.send_message(file=file, embed=embed)
        else:
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(embed=embed)
    else:
        await ctx.response.send_message(f"No data available for points. (either fetch failed and it's a huge skill issue or you're not in the top100 and that's a skill issue as well)")

# Autocompletion compare
async def autocompletion_type_cmp(interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
    choices = [
        app_commands.Choice(name=a, value=a)
        for a in ["ranks", "wins", "points"]
        ]
    return choices

@bot.tree.command(name="compare", description="Compare multiple users.")
@app_commands.describe(type="The type of comparison you want to see. Either 'wins', 'points' or 'ranks'.", users="The users you want to compare (ex. /compare type:points users:Discord BabaYaga Lotad).")
@app_commands.autocomplete(type=autocompletion_type_cmp)
async def compare(ctx, type: str = None, users: str = None):
    # check type
    if type not in ["wins", "points", "ranks"]:
        await ctx.response.send_message("Please provide a valid type. Either 'wins', 'points' or 'ranks'.")
        return
    # print(users) # debug
    old_users = users
    users = users.split(" ")
    if len(users) < 2:
        await ctx.response.send_message("Please provide more than 2 users")
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    player_list = []
    player_not_found = []
    for user in users:
        player = find_player(players, user)
        if player is None:
            player_not_found.append(user)
            # await ctx.response.send_message(f'Player with name or ID "{user}" not found. (not in the top100 ???)') # hold up
            continue
            # return
        player_list.append(player)
    # test pseudos non trouvés
    for player_ in player_not_found:
        for player_2 in player_not_found:
            print(player_ + " " + player_2)
            if player_ + " " + player_2 in old_users: # existe mais avec un espace
                player_not_found.remove(player_)
                player_not_found.remove(player_2)
                # Ajouter à player_list
                player__ = find_player(players, player_ + " " + player_2)
                if player__ is None: # il n'existe pas
                    player_not_found.append(player_ + " " + player_2)
                    # await ctx.response.send_message(f'Player with name or ID "{user}" not found. (not in the top100 ???)') # hold up
                    continue
                    # return
                player_list.append(player__)
    # test si des pseudos encore pas trouvé
    if len(player_not_found) > 0:
        await ctx.response.send_message(f"Players with name or ID {', '.join(player_not_found)} not found. (not in the top100 ???)")
        return
    print(player_list)
    render(player_list, output_dir, type, multiple=True)
    image_path = os.path.join(output_dir,f"multiple{type}.png")
    embed = discord.Embed(
            title="Comparison",
            description=f"here's the graphics <:gigachad:932689547265990706>\n",
            color=discord.Color.blurple()
        )
    if os.path.exists(image_path):
        file = discord.File(image_path, filename="comp.png")
        embed.set_image(url=f"attachment://comp.png")
        embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
        # embed.set_footer(text="Provided by DiscordHosting.com")
        await ctx.response.send_message(file=file, embed=embed)
    else:
        embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
        # embed.set_footer(text="Provided by DiscordHosting.com")
        await ctx.response.send_message(embed=embed)


@bot.tree.command(name='ranking', description="Show the ranking of a player.")
@app_commands.describe(identifier="The identifier of the player you want to see the ranking of.")
async def ranking(ctx, identifier: str = None):
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    ranks_data = player.get("ranks")
    if ranks_data:
        render([player], output_dir, "ranks")
        current_rank = ranks_data[-1]
        image_path = os.path.join(output_dir, player["name"].replace('$$', '\$\$'), 'ranks.png')

        embed = discord.Embed(
            title=f"{player['name']}'s ranking",
            description=f"Your current ranking is **{current_rank:,}**.",
            color=discord.Color.green()
        )
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="ranks.png")
            embed.set_image(url=f"attachment://ranks.png")
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(file=file, embed=embed)
        else:
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(embed=embed)
    else:
        await ctx.response.send_message(f"No data available for points. (either fetch failed and it's a huge skill issue or you're not in the top100 and that's a skill issue as well)")


@bot.tree.command(name='points', description="Show the points of a player.")
@app_commands.describe(identifier="The identifier of the player you want to see the points of.")
async def points(ctx, identifier: str = None):
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    points_data = player.get("points")
    if points_data:
        render([player], output_dir, "points")
        current_points = points_data[-1]
        image_path = os.path.join(output_dir, player["name"], 'points.png')

        embed = discord.Embed(
            title=f"{player['name']}'s current points",
            description=f"The current points are **{current_points:,}**.",
            color=discord.Color.red()
        )
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="points.png")
            embed.set_image(url=f"attachment://points.png")
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(file=file, embed=embed)
        else:
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(embed=embed)
    else:
        await ctx.response.send_message(f"No data available for points. (either fetch failed and it's a huge skill issue or you're not in the top100 and that's a skill issue as well)")

@bot.tree.command(name='wins', description="Show the wins of a player.")
@app_commands.describe(identifier="The identifier of the player you want to see the wins of.")
async def wins(ctx, identifier: str = None):
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    player = find_player(players, identifier)
    if player is None:
        await ctx.response.send_messaged(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return
    wins_data = player.get("wins")
    if wins_data:
        render([player], output_dir, "wins")
        current_wins = wins_data[-1]
        image_path = os.path.join(output_dir, player["name"], 'wins.png')

        embed = discord.Embed(
            title=f"{player['name']}'s current wins",
            description=f"The current wins are **{current_wins}**.",
            color=discord.Color.brand_red()
        )
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="wins.png")
            embed.set_image(url=f"attachment://wins.png")
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(file=file, embed=embed)
        else:
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(embed=embed)
    else:
        await ctx.response.send_message(f"No data available for wins. (either fetch failed and it's a huge skill issue or you're not in the top100 and that's a skill issue as well)")


# Autocompletion pace
async def autocompletion_type_pace(interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
    choices = [
        app_commands.Choice(name=a, value=a)
        for a in ["wins", "points"]
        ]
    return choices

@bot.tree.command(name='pace', description="Show your current pace.")
@app_commands.describe(pace_type="The pace type you want to see. Either 'wins' or 'points'.", identifier="The identifier of the player you want to see the pace of.")
@app_commands.autocomplete(pace_type=autocompletion_type_pace)
async def pace(ctx, pace_type: str = "wins", identifier: str = None):
    # vérifier si le type est valide
    if type not in ["wins", "points"]:
        await ctx.response.send_message("Please provide a valid type. Either 'wins' or 'points'.")
        return
    players = load_data()
    discord_users = load_discord_users()
    update, start, end, total, left, elapsed = time_data()
    
    if identifier is None:
        user_id = str(ctx.user.id)
        identifier = discord_users.get(user_id)
        if identifier is None:
            await ctx.response.send_message("You did not provide a Dokkan name/ID and your Discord account isn't linked to any please provide an identifier or link your Discord account (/link)")
            return
    
    player = find_player(players, identifier)
    
    if player is None:
        await ctx.response.send_message(f'Player with name or ID "{identifier}" not found. (not in the top100 ???)')
        return

    pace_type = pace_type + "_pace"
    if pace_type not in ['wins_pace', 'points_pace']:
        await ctx.response.send_message(f'Invalid pace type "{pace_type}". Use "wins" or "points" ex:`!pace wins Lotad`.')
        return

    pace_data = player.get(pace_type)
    if pace_data:
        render([player], output_dir, pace_type)
        latest_pace = pace_data[-1]
        image_path = os.path.join(output_dir, player["name"], f'{pace_type}.png')

        embed = discord.Embed(
            title=f"{player['name']}'s current {pace_type.replace('_', ' ')}",
            description=f"Your current {pace_type.replace('_', ' ')} is **{latest_pace}**.",
            color=discord.Color.blue()
        )
        if os.path.exists(image_path):
            file = discord.File(image_path, filename=f"{pace_type}.png")
            embed.set_image(url=f"attachment://{pace_type}.png")
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(file=file, embed=embed)
        else:
            embed.add_field(name="Updated at",value=f"<t:{update}:f>    (<t:{update}:R>)", inline=False)
            # embed.set_footer(text="Provided by DiscordHosting.com")
            await ctx.response.send_message(embed=embed)
    else:
        await ctx.response.send_message(f"No data available for {pace_type}. (either fetch failed and it's a huge skill issue or you're not in the top100 and that's a skill issue as well)")

@bot.tree.command(name='link', description="Link your Discord account to your Dokkan ig name/ID.")
@app_commands.describe(identifier="The identifier you want to link your Discord account to.")
async def link(ctx, identifier: str):
    exist = False
    discord_users = load_discord_users()
    user_id = str(ctx.user.id)

    async def callback_yesconf(interaction: discord.Interaction):
        ##########
        if int(ctx.user.id) != int(interaction.user.id):
            return await interaction.response.send_message(embed=discord.Embed(
                description=f"❌ {interaction.user.mention}, - you can't do that !"),
                ephemeral=True)
        # Remplacer l'identifiant
        discord_users[user_id] = identifier
        save_discord_users(discord_users)
        # Dire que l'identifiant a été remplacé
        await ctx.channel.send(embed=discord.Embed
        (
            description=f'**✅♻ - Your Discord ID has refreshed and is now linked to player "{identifier}**".',
            color=discord.Color.blue()
        ))
        await interaction.message.delete()

    async def callback_noconf(interaction: discord.Interaction):
        if int(ctx.user.id) != int(interaction.user.id):
            return await interaction.response.send_message(embed=discord.Embed(
                description=f"❌ {interaction.user.mention}, - you can't do that !"),
                ephemeral=True)
        await interaction.message.delete()

    view = discord.ui.View()
    button_validate = discord.ui.Button(style=discord.ButtonStyle.green, emoji="✅", label="Oui")
    button_cancel = discord.ui.Button(style=discord.ButtonStyle.red, emoji="❌", label="Non")
    button_validate.callback = callback_yesconf
    button_cancel.callback = callback_noconf
    view.add_item(button_validate)
    view.add_item(button_cancel)
    ######
    
    # await ctx.send(f'Your Discord ID has been successfully linked to player "{identifier}".'))

    # Check si l'utilisateur existe
    try:
        if type(discord_users[user_id]) is int:
            pass
        exist = True
    except KeyError: # Existe pas, car erreur
        exist = False

    # Si l'utilisateur existe pas
    print(
        exist
    )
    if exist:
        # Demander si il veut remplacer son identifiant
        await ctx.response.send_message(f"Would you like to replace ``{discord_users[str(ctx.user.id)]}`` by ``{identifier}`` ?", view=view, ephemeral=False)
    else:
        # Existe pas
        discord_users[user_id] = identifier
        save_discord_users(discord_users)
        await ctx.send(embed=discord.Embed
        (
            description=f'**✅ - Your Discord ID has been successfully linked to player "{identifier}**".',
            color=discord.Color.blue()
        ))



# Ajout des extensions des commandes avec bouttons, etc.

# Ajout commande /help
asyncio.run(bot.load_extension(r"cogs.help"))

bot.run(TOKEN)

