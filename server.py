import discord
import time
import os
import pickle
from dotenv import load_dotenv
from discord.ext import tasks, commands
from api import get_recent_problem_codeforces, get_recent_problem_leetcode, get_clist_info, Problem

load_dotenv()

bot = commands.Bot(command_prefix='!', 
                   intents=discord.Intents.all(), 
                   help_command=commands.DefaultHelpCommand(no_category = 'Commands'))

def save_pickle(obj, filepath):
    with open(filepath, 'wb') as f:
        pickle.dump(obj, f)

def load_pickle(filepath, object_default):
    if not os.path.exists(filepath):
        with open(filepath, 'wb') as f:
            pickle.dump(object_default, f)
        return object_default
    with open(filepath, 'rb') as f:
        obj = pickle.load(f)
    return obj

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
        if ' ' in handle:
            await ctx.send(f'Handle cannot have spaces')
            return
            
        saved_last_problems[grader] = saved_last_problems.get(grader, {})
        saved_last_problems[grader][handle] = get_recent_problem(handle, grader)

        handle_to_user[grader] = handle_to_user.get(grader, {})
        handle_to_user[grader][handle] = message.author.id

        available_handles.append(handle)

        save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)
        save_pickle(handle_to_user, HANDLE_TO_USER_PATH)

        await ctx.send(f'Connected {handle} on {grader}')
    else:
        await ctx.send(f'Must connect to codeforces or leetcode')

@bot.command()
async def disconnect(ctx,
                     grader : str = commands.parameter(description="One of supported graders, codeforces or leetcode"),
                     handle : str = commands.parameter(description="Handle/username on grader")):
    '''
    Disconnect handle from grader from solved problem notifications
    '''

    if grader == "codeforces" or grader == "leetcode":
        if saved_last_problems[grader].pop(handle, None):
            if handle_to_user[grader].pop(handle, None):
                save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)
                save_pickle(handle_to_user, HANDLE_TO_USER_PATH)

                await ctx.send(f'Unconnected {handle} on {grader}')
            else:
                await ctx.send(f'Erorr disconnecting {handle}, database may be in a bad state')
        else:
            await ctx.send(f'{handle} is not connected to {grader}')
    else:
        await ctx.send(f'Must disconnect from a valid grader')

@bot.command(hidden=True)
async def sendstate(ctx):
    await bot.admin_user.send('handle_to_user: ' + str(handle_to_user) + '\n' + 
                              'saved_last_problems: ' + str(saved_last_problems) + '\n' + 
                              'available_graders: ' + str(available_graders) + '\n' + 
                              'available_handles: ' + str(available_handles))

def get_recent_problem(handle, grader):
    if grader == 'codeforces':
        return get_recent_problem_codeforces(handle)
    elif grader == 'leetcode':
        return get_recent_problem_leetcode(handle)

def recent_problem_update(handle, grader):
    update = None

    last_problem = get_recent_problem(handle, grader)

    if last_problem and last_problem.name != saved_last_problems[grader][handle].name and last_problem.ac:
        saved_last_problems[grader] = saved_last_problems.get(grader, {})
        saved_last_problems[grader][handle] = last_problem
        update = last_problem
        save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)

    return update

@tasks.loop(seconds=10)
async def read_last_problem_loop():
    global available_handles
    global available_graders

    try:
        # cycle slowly through graders and handles
        if available_handles:
            if not available_graders:
                handle = available_handles.pop(0)
                if not available_handles:
                    available_handles = []
                    for grader in saved_last_problems:
                        available_handles += saved_last_problems[grader]
                    available_handles = list(set(available_handles))
                handle = available_handles[0]

                available_graders = [grader for grader in saved_last_problems if handle in saved_last_problems[grader]]

            handle = available_handles[0]
            grader = available_graders[0]
            available_graders.pop(0)

            problem = recent_problem_update(handle, grader)

            if problem:
                if not problem.rating or not problem.url:
                    get_clist_info(problem)
                problem_text = problem.name
                if problem.rating:
                    lc_rating = rating_cf_to_lc(problem.rating)
                    problem_text = f'{problem_text} (difficulty: {problem.rating}/{lc_rating})'
                if problem.url:
                    problem_text = f'[{problem_text}]({problem.url})'

                await bot.icpc_bot_channel.send(f'<@{handle_to_user[grader][handle]}> solved {problem_text} on {grader}!')
    except Exception as e:
        await bot.admin_user.send(str(e)) # :(

SAVED_LAST_PROBLEMS_PATH = 'saved_last_problems.pkl'
HANDLE_TO_USER_PATH = 'handle_to_user.pkl'
saved_last_problems = load_pickle(SAVED_LAST_PROBLEMS_PATH, { })
handle_to_user = load_pickle(HANDLE_TO_USER_PATH, { })

available_handles = []
for grader in saved_last_problems:
    available_handles += saved_last_problems[grader]
available_handles = list(set(available_handles))
available_graders = [grader for grader in saved_last_problems if available_handles[0] in saved_last_problems[grader]]

bot.run(os.getenv('DISCORD_API_KEY'))
