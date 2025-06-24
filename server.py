import discord
import time
import os
from dotenv import load_dotenv
from discord.ext import tasks, commands
from api import get_recent_problem_codeforces, get_recent_problem_leetcode, get_clist_info
import sqlite3

load_dotenv()

bot = commands.Bot(command_prefix='!', 
                   intents=discord.Intents.all(), 
                   help_command=commands.DefaultHelpCommand(no_category = 'Commands'))

con = sqlite3.connect("data.sqlite3", autocommit=True)
cur = con.cursor()

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

    bot.admin_user = await bot.fetch_user(os.getenv('ADMIN_USER'))
    bot.icpc_bot_channel = await bot.fetch_channel(os.getenv('ICPC_BOT_CHANNEL'))

    read_last_problem_loop.start()

@bot.command()
async def connect(ctx,
                  grader : str = commands.parameter(description="One of supported graders, codeforces or leetcode"),
                  handle : str = commands.parameter(description="Handle/username on grader")):
    '''
    Connect handle from grader to get solved problem notifications
    '''

    if grader == "codeforces" or grader == "leetcode":
        await ctx.send(f'Must connect to codeforces or leetcode')
        return

    if ' ' in handle:
        await ctx.send(f'Handle cannot have spaces')
        return

    existing_users = cur.execute(f"SELECT * FROM users WHERE grader='{grader}' AND handle='{handle}'")

    if exisitng_users.fetchone() is not None:
        await ctx.send(f'User with handle {handle} on {grader} already exists.')

    update_recent_problems(handle, grader, 20)

    cur.execute(f"INSERT INTO users (handle, grader, discord_id) VALUES ('{handle}', '{grader}', {ctx.author.id})")

    await ctx.send(f'Connected {handle} on {grader}')

@bot.command()
async def disconnect(ctx,
                     grader : str = commands.parameter(description="One of supported graders, codeforces or leetcode"),
                     handle : str = commands.parameter(description="Handle/username on grader")):
    '''
    Disconnect handle from grader from solved problem notifications
    '''

    if grader == "codeforces" or grader == "leetcode":
        await ctx.send(f'Must disconnect from a valid grader')
        return

    existing_users = cur.execute(f"SELECT * FROM users WHERE grader='{grader}' AND handle='{handle}'")

    if exisitng_users.fetchone() is None:
        await ctx.send(f'User with handle {handle} on {grader} does not exist.')

    cur.execute(f"""DELETE FROM users
                    WHERE grader='{grader}' AND
                    handle='{handle}'""")

    await ctx.send(f'Disconnected {handle} on {grader}')

@bot.command(hidden=True)
async def sendstate(ctx):
    await bot.admin_user.send('handle_to_user: ' + str(handle_to_user) + '\n' + 
                              'saved_last_problems: ' + str(saved_last_problems) + '\n' + 
                              'available_graders: ' + str(available_graders) + '\n' + 
                              'available_handles: ' + str(available_handles))

@tasks.loop(seconds=10)
async def read_last_problem_loop():
    try:
        if not bot.queries:
            bot.queries = cur.execute('SELECT handle, grader FROM users').fetchall()

        handle, grader = bot.queries.pop()

        problems = update_recent_problems(handle, grader, 10)

        for problem in problems:
            problem_text = problem.name

            if problem.rating:
                lc_rating = rating_cf_to_lc(problem.rating)
                problem_text = f'{problem_text} (difficulty: {problem.rating}/{lc_rating})'
            if problem.url:
                problem_text = f'[{problem_text}]({problem.url})'

            await bot.icpc_bot_channel.send(f'<@{handle_to_user[grader][handle]}> solved {problem_text} on {grader}!')
    except Exception as e:
        await bot.admin_user.send(str(e)) # :(

def get_recent_problems(handle, grader, count):
    if grader == 'codeforces':
        return get_recent_problem_codeforces(handle, count)
    elif grader == 'leetcode':
        return get_recent_problem_leetcode(handle, count)

def update_recent_problems(handle, grader, count):
    problems = get_recent_problems(handle, grader, count)

    new_problems = []

    for problem in problems:
        existing_problem = cur.execute(f"""SELECT * FROM problems 
                                           JOIN users ON users.user_id=problems.user_id
                                           WHERE handle='{handle}' AND
                                           name='{problem.name}' AND
                                           grader='{grader}'""")

        if existing_problem.fetchone() is None:
            get_clist_info(problem)

            user_id = cur.execute(f"SELECT * FROM users WHERE handle='{handle}' AND grader='{grader}'").fetchone()[0]

            cur.execute(f"""INSERT INTO problems (user_id, name, timestamp)
                          VALUES ({user_id}, '{problem.name}', {problem.timestamp})""")

            if problem.rating:
                cur.execute(f"""UPDATE problems 
                                SET rating={problem.rating}
                                WHERE user_id={user_id} AND
                                name='{problem.name}'""")

            if problem.url:
                cur.execute(f"""UPDATE problems 
                                SET url={problem.url}
                                WHERE user_id={user_id} AND
                                name='{problem.name}'""")

            new_problems.append(problem)

    return new_problems

bot.run(os.getenv('DISCORD_API_KEY'))
