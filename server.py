import discord
import time
import os
from dotenv import load_dotenv
from discord.ext import tasks, commands
from api import update_recent_problems, get_profile_url
import datetime
import sqlite3
import bar
import pytz

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


@bot.command()
async def weekly(
    ctx, 
    offset: int = 0, 
    user: discord.Member = commands.parameter(
        description="Get weekly problems overview of another user", 
        default=None
    )
):
    '''
    Get weekly problems solved overview
    Use `!weekly 0` for this week (default), `!weekly 1` for last week, etc.
    '''

    if user is None:
        user = ctx.author

    tz = pytz.timezone("US/Eastern")
    now = datetime.datetime.now(tz)

    offset = max(offset, 0)

    monday = now - datetime.timedelta(days=now.weekday(), weeks=offset)
    monday = datetime.datetime.combine(monday.date(), datetime.time(0, 0))
    monday = tz.localize(monday)

    week_end = monday + datetime.timedelta(days=7)

    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    data = []

    for i in range(7):
        start_dt = monday + datetime.timedelta(days=i)
        end_dt = start_dt + datetime.timedelta(days=1)

        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        count = cur.execute("""
            SELECT count(*) FROM problems 
            JOIN users ON problems.user_id = users.user_id
            WHERE discord_id = ? AND timestamp >= ? AND timestamp < ?
        """, (user.id, start_ts, end_ts)).fetchone()[0]

        data.append((days[i], count))

    ago_text = "(this week)" if offset == 0 else f"({offset} week{'s' if offset > 1 else ''} ago)"

    await ctx.send(
        f'```        Weekly Overview {ago_text}\n{"―"*30}\n{bar.draw(data)}\n```'
    )


@tasks.loop(seconds=10)
async def read_last_problem_loop():
    try:
        if not bot.queries:
            bot.queries = cur.execute('SELECT handle, grader FROM users').fetchall()

        handle, grader = bot.queries.pop()

        problems = update_recent_problems(handle, grader, 10, cur, get_clist=True)

        # if len(problems) > 4:
            # await bot.admin_user.send(str(e)) # :(
            # return

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
                problem_text = f'[{problem_text}](<{problem.url}>)'

            handle_text = f'[{handle}]({handle_url})' if (handle_url := get_profile_url(grader, handle)) else handle

            user_id = cur.execute(f"SELECT discord_id FROM users WHERE handle='{handle}' AND grader='{grader}'").fetchone()[0]

            await bot.icpc_bot_channel.send(f'<@{user_id}> ({handle_text}) solved {problem_text} on {grader}!')
    except Exception as e:
        await bot.admin_user.send(str(e)) # :(

bot.run(os.getenv('DISCORD_API_KEY'))
