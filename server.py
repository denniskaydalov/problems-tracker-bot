import discord
import time
import os
from dotenv import load_dotenv
from discord.ext import tasks, commands
from api import update_recent_problems
import sqlite3

load_dotenv()

bot = commands.Bot(command_prefix='!', 
                   intents=discord.Intents.all(), 
                   help_command=commands.DefaultHelpCommand(no_category = 'Commands'))

con = sqlite3.connect("data.sqlite3", isolation_level=None)
cur = con.cursor()

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

    bot.admin_user = await bot.fetch_user(os.getenv('ADMIN_USER'))
    bot.icpc_bot_channel = await bot.fetch_channel(os.getenv('ICPC_BOT_CHANNEL'))
    bot.queries = cur.execute('SELECT handle, grader FROM users').fetchall()

    read_last_problem_loop.start()

@bot.command()
async def connect(ctx,
                  grader : str = commands.parameter(description="One of supported graders, codeforces or leetcode"),
                  handle : str = commands.parameter(description="Handle/username on grader")):
    '''
    Connect handle from grader to get solved problem notifications
    '''

    if grader != "codeforces" and grader != "leetcode":
        await ctx.send(f'Must connect to codeforces or leetcode')
        return

    if ' ' in handle:
        await ctx.send(f'Handle cannot have spaces')
        return

    existing_users = cur.execute(f"SELECT * FROM users WHERE grader='{grader}' AND handle='{handle}'")

    if existing_users.fetchone() is not None:
        await ctx.send(f'User with handle {handle} on {grader} already exists.')
        return 

    cur.execute(f"INSERT INTO users (handle, grader, discord_id) VALUES ('{handle}', '{grader}', {ctx.author.id})")

    update_recent_problems(handle, grader, 20, cur)


    await ctx.send(f'Connected {handle} on {grader}')

@bot.command()
async def disconnect(ctx,
                     grader : str = commands.parameter(description="One of supported graders, codeforces or leetcode"),
                     handle : str = commands.parameter(description="Handle/username on grader")):
    '''
    Disconnect handle from grader from solved problem notifications
    '''

    if grader != "codeforces" and grader != "leetcode":
        await ctx.send(f'Must disconnect from a valid grader')
        return

    existing_users = cur.execute(f"SELECT * FROM users WHERE grader='{grader}' AND handle='{handle}'")

    if existing_users.fetchone() is None:
        await ctx.send(f'User with handle {handle} on {grader} does not exist.')
        return

    cur.execute(f"""DELETE FROM users
                    WHERE grader='{grader}' AND
                    handle='{handle}'""")

    bot.queries = cur.execute('SELECT handle, grader FROM users').fetchall()

    await ctx.send(f'Disconnected {handle} on {grader}')

@tasks.loop(seconds=10)
async def read_last_problem_loop():
    try:
        if not bot.queries:
            bot.queries = cur.execute('SELECT handle, grader FROM users').fetchall()

        handle, grader = bot.queries.pop()

        problems = update_recent_problems(handle, grader, 10, cur, get_clist=True)

        for problem in problems:
            problem_text = problem.name
            difficulty = None

            if problem.rating_grader and problem.rating_clist:
                difficulty = f'dificulty: {problem.rating_grader}/clist: {problem.rating_clist}'
            else:
                difficulty = f'difficulty: {problem.rating_grader}' or f'clist difficulty: {problem.rating_clist}'

            if difficulty:
                problem_text = f'{problem_text} ({difficulty})'

            if problem.url:
                problem_text = f'[{problem_text}]({problem.url})'

            user_id = cur.execute(f"SELECT discord_id FROM users WHERE handle='{handle}' AND grader='{grader}'").fetchone()[0]

            await bot.icpc_bot_channel.send(f'<@{user_id}> solved {problem_text} on {grader}!')
    except Exception as e:
        await bot.admin_user.send(str(e)) # :(

bot.run(os.getenv('DISCORD_API_KEY'))
