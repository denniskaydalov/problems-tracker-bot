import discord
import requests
import time
import os
import pickle
from dotenv import load_dotenv
from discord.ext import tasks
from dataclasses import dataclass

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

ICPC_BOT_CHANNEL = client.get_channel(os.getenv('ICPC_BOT_CHANNEL'))
ADMIN_USER = client.get_user(os.getenv('ADMIN_USER'))

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


@dataclass
class Problem:
    name : str
    timestamp : int
    ac : bool
    grader : str
    url : str = None
    rating : int = None

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    read_last_problem_loop.start()

def get_recent_problem_codeforces(handle):
    URL = 'https://codeforces.com/api/user.status'
    params = { 'handle':handle,
               'from':1,
               'count':1 }
    try:
        print('getting_request codeforces', handle)
        response = requests.get(url = URL, params = params, timeout=10)
        print('got request codeforces', handle, response.json())

        recent_problem = response.json()['result'][0]
    
        if 'contestId' in recent_problem['problem']:
            problem_url = f"https://codeforces.com/contest/{recent_problem['problem']['contestId']}/problem/{recent_problem['problem']['index']}"
        elif 'problemsetName' in recent_problem['problem']:
            problem_url = f"https://codeforces.com/problemsets/{recent_problem['problem']['problemsetName']}/problem/99999/{recent_problem['problem']['index']}"
        else:
            problem_url = None

        return Problem(name = recent_problem['problem']['name'],
                      timestamp = recent_problem['creationTimeSeconds'],
                      ac = recent_problem['verdict'] == 'OK',
                      url = problem_url,
                      grader='codeforces')
    except Exception as e:
        print(e)
        return None

def get_clist_info(problem):
    URL = 'https://clist.by:443/api/v4/problem'
    params = {'username': os.getenv('CLIST_USERNAME'),
              'api_key': os.getenv('CLIST_API_KEY'),
              'name': problem.name,
              'url_regex': f'^.*{problem.grader}.*$'}

    try:
        print('getting_request clist')
        response = requests.get(url = URL, params = params, timeout=10)
        print('got request clist', response)

        response = response.json()['objects'][0]

        problem.url = response['archive_url'] or response['url']
        problem.rating = response['rating']

        return problem
    except Exception as e:
        print(e)

        return None

def get_recent_problem_leetcode(handle):
    URL = f'https://leetcode-api-pied.vercel.app/user/{handle}/submissions'

    try:
        print('getting_request leetcode', handle)
        response = requests.get(url = URL, params = {'limit': 1}, timeout=10).json()[0]
        print('got request leetcode', handle, response)

        return Problem(name = response['title'],
                       timestamp = response['timestamp'],
                       ac = response['statusDisplay'] == 'Accepted',
                       url = f"https://leetcode.com/problems/{response['titleSlug']}/",
                       grader='leetcode')
    except Exception as e:
        print(e)
        return None

def rating_cf_to_lc(rating):
    return (   'Easy' if rating <= 1200 else
        'Medium' if rating <= 1700 else
        'Hard' if rating <= 2000 else
        'Hard' + '+' * ((rating - 2000) // 200 + 1))

def rating_lc_to_cf(rating):
    return (800 if rating == 'Easy' else
            1200 if rating == 'Medium' else
            1700 if rating == 'Hard' else
            2000 if rating == 'Hard+' else
            2000 + (200 * rating.count('+')) - 200)

def get_recent_problem(handle, grader):
    if grader == 'codeforces':
        return get_recent_problem_codeforces(handle)
    elif grader == 'leetcode':
        return get_recent_problem_leetcode(handle)

def recent_problem_update(handle, grader):
    update = None

    last_problem = get_recent_problem(handle, grader)

    if last_problem and last_problem.timestamp != saved_last_problems[grader][handle].timestamp and last_problem.ac:
        saved_last_problems[grader] = saved_last_problems.get(grader, {})
        saved_last_problems[grader][handle] = last_problem
        update = last_problem
        save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)

    return update

@tasks.loop(seconds=10)
async def read_last_problem_loop():
    global ADMIN_USER
    global ICPC_BOT_CHANNEL
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
                if not ICPC_BOT_CHANNEL:
                    ICPC_BOT_CHANNEL = await client.fetch_channel(os.getenv('ICPC_BOT_CHANNEL'))

                if ICPC_BOT_CHANNEL:
                    if not problem.rating or not problem.url:
                        get_clist_info(problem)
                    problem_text = problem.name
                    if problem.rating:
                        lc_rating = rating_cf_to_lc(problem.rating)
                        problem_text = f'{problem_text} (difficulty: {problem.rating}/{lc_rating})'
                    if problem.url:
                        problem_text = f'[{problem_text}]({problem.url})'
                    await ICPC_BOT_CHANNEL.send(f'<@{handle_to_user[grader][handle]}> solved {problem_text} on {grader}!')
    except Exception as e:
        if not ADMIN_USER:
            ADMIN_USER = await client.fetch_user(os.getenv('ADMIN_USER'))

        if ADMIN_USER:
            await ADMIN_USER.send(str(e)) # :(

@client.event
async def on_message(message):
    global ADMIN_USER

    if message.author == client.user:
        return

    if message.content.startswith(f'{command_prefix}sendstate'):
        if not ADMIN_USER:
            ADMIN_USER = await client.fetch_user(os.getenv('ADMIN_USER'))

        if ADMIN_USER:
            await ADMIN_USER.send('ADMIN_USER: ' + str(ADMIN_USER) + '\n' +
                                  'ICPC_BOT_CHANNEL: ' + str(ICPC_BOT_CHANNEL) + '\n' + 
                                  'handle_to_user: ' + str(handle_to_user) + '\n' + 
                                  'saved_last_problems: ' + str(saved_last_problems) + '\n' + 
                                  'available_graders: ' + str(available_graders) + '\n' + 
                                  'available_handles: ' + str(available_handles))

    if message.content.startswith(f'{command_prefix}help'):
        await message.channel.send('''
Commands:
```
!connect <platform> <username>              get notifications for problems you've solved
!unconnect <platform> <username>

only codeforces or leetcode graders are currently supported
```
                           ''')

    if message.content.startswith(f'{command_prefix}connect'):
        splits = message.content.split(' ')
        if len(splits) == 3:
            grader = splits[1]
            handle = splits[2]

            if grader == "codeforces" or grader == "leetcode":
                saved_last_problems[grader] = saved_last_problems.get(grader, {})
                saved_last_problems[grader][handle] = get_recent_problem(handle, grader)

                handle_to_user[grader] = handle_to_user.get(grader, {})
                handle_to_user[grader][handle] = message.author.id

                available_handles.append(handle)

                save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)
                save_pickle(handle_to_user, HANDLE_TO_USER_PATH)
                await message.channel.send(f'Connected {handle} on {grader}')
            else:
                await message.channel.send(f'Must connect to codeforces or leetcode')
        else:
            await message.channel.send(f'Format for connect is `connect <grader> <handle>`.')

    if message.content.startswith(f'{command_prefix}unconnect'):
        splits = message.content.split(' ')
        if len(splits) == 3:
            grader = splits[1]
            handle = splits[2]

            if grader == "codeforces" or grader == "leetcode":
                if saved_last_problems[grader].pop(handle, None):
                    if handle_to_user[grader].pop(handle, None):
                        save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)
                        save_pickle(handle_to_user, HANDLE_TO_USER_PATH)

                        await message.channel.send(f'Unconnected {handle} on {grader}')
                    else:
                        await message.channel.send(f'Erorr unconnecting {handle}, database may be in a bad state')
                else:
                    await message.channel.send(f'{handle} does not exist in connections')
            else:
                await message.channel.send(f'Must unconnect to codeforces or leetcode')
        else:
            await message.channel.send(f'Format for unconnect is `unconnect <grader> <handle>`.')

    if message.content.startswith(f'{command_prefix}leaderboard') or message.content.startswith(f'{command_prefix}lb'):
        pass


SAVED_LAST_PROBLEMS_PATH = 'saved_last_problems.pkl'
HANDLE_TO_USER_PATH = 'handle_to_user.pkl'
saved_last_problems = load_pickle(SAVED_LAST_PROBLEMS_PATH, { })
handle_to_user = load_pickle(HANDLE_TO_USER_PATH, { })

available_handles = []
for grader in saved_last_problems:
    available_handles += saved_last_problems[grader]
available_handles = list(set(available_handles))
available_graders = [grader for grader in saved_last_problems if available_handles[0] in saved_last_problems[grader]]

__message__ = None
command_prefix = "!"

client.run(os.getenv('DISCORD_API_KEY'))

