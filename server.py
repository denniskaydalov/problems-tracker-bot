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
        print('getting_request codeforces')
        response = requests.get(url = URL, params = params, timeout=10)
        print('got request codeforces')

        recent_problem = response.json()['result'][0]
    
        return Problem(name = recent_problem['problem']['name'],
                      timestamp = recent_problem['creationTimeSeconds'],
                      ac = recent_problem['verdict'] == 'OK',
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

def rating_cf_to_lc(rating):
    print(rating)
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

def get_recent_problem_leetcode(handle):
    URL = f'https://leetcode-api-pied.vercel.app/user/{handle}/submissions'

    try:
        print('getting_request leetcode')
        response = requests.get(url = URL, params = {'limit': 1}, timeout=10).json()[0]
        print('got request leetcode')

        return Problem(name = response['title'],
                       timestamp = response['timestamp'],
                       ac = response['statusDisplay'] == 'Accepted',
                       grader='leetcode')
    except Exception as e:
        print(e)
        return None

def get_recent_problem(handle, grader):
    if grader == 'codeforces':
        return get_recent_problem_codeforces(handle)
    elif grader == 'leetcode':
        return get_recent_problem_leetcode(handle)

def recent_problem_update():
    updates = {  }

    for grader in saved_last_problems:
        updates[grader] = {  }

        for handle in saved_last_problems[grader]:
            last_problem = get_recent_problem(handle, grader)

            if last_problem and last_problem.timestamp != saved_last_problems[grader][handle].timestamp and last_problem.ac:
                saved_last_problems[grader] = saved_last_problems.get(grader, {})
                saved_last_problems[grader][handle] = last_problem
                updates[grader][handle] = last_problem


    save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)

    return updates

@tasks.loop(seconds=60)
async def read_last_problem_loop():
    recent_problems = recent_problem_update()
    for grader in recent_problems:
        for handle in recent_problems[grader]:
            problem = recent_problems[grader][handle]
            if get_clist_info(problem) and problem.rating and problem.url:
                lc_rating = rating_cf_to_lc(problem.rating)
                await send_message(f'<@{handle_to_user[grader][handle]}> solved [{problem.name} (difficulty: {problem.rating}/{lc_rating})]({problem.url}) on {grader}!')
            else:
                await send_message(f'<@{handle_to_user[grader][handle]}> solved {recent_problems[grader][handle].name} on {grader}!')

async def send_message(message, channel = None):
    global __message__

    if not __message__ and channel:
        __message__ = channel

    message_channel = channel or __message__ or None

    print('seindg', message, 'with', message_channel)
    if message_channel: 
        await message_channel.channel.send(message)

@client.event
async def on_message(message):
    global __message__ 

    if message.author == client.user:
        return

    if message.content.startswith(f'{command_prefix}trackerbotinit'):
        __message__ = message
        await send_message('Init successful in this channel', message)

    if message.content.startswith(f'{command_prefix}help'):
        await send_message('''
Commands:
```
!connect <platform> <username>              get notifications for problems you've solved
!unconnect <platform> <username>

only codeforces or leetcode graders are currently supported
```
                           ''', message)

    if message.content.startswith(f'{command_prefix}connect'):
        splits = message.content.split(' ')
        if len(splits) == 3:
            grader = splits[1]
            handle = splits[2]

            if grader == "codeforces" or grader == "leetcode":
                saved_last_problems[grader] = saved_last_problems.get(grader, {})
                saved_last_problems[grader][handle] = Problem("", -1, True, "")#get_recent_problem(handle, grader)

                handle_to_user[grader] = handle_to_user.get(grader, {})
                handle_to_user[grader][handle] = message.author.id

                save_pickle(saved_last_problems, SAVED_LAST_PROBLEMS_PATH)
                save_pickle(handle_to_user, HANDLE_TO_USER_PATH)
                await send_message(f'Connected {handle} on {grader}', message)
            else:
                await send_message(f'Must connect to codeforces or leetcode', message)
        else:
            await send_message(f'Format for connect is `connect <grader> <handle>`.', message)

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

                        await send_message(f'Unconnected {handle} on {grader}', message)
                    else:
                        await send_message(f'Erorr unconnecting {handle}, database may be in a bad state', message)
                else:
                    await send_message(f'{handle} does not exist in connections', message)
            else:
                await send_message(f'Must unconnect to codeforces or leetcode', message)
        else:
            await send_message(f'Format for unconnect is `unconnect <grader> <handle>`.', message)

    if message.content.startswith(f'{command_prefix}leaderboard') or message.content.startswith(f'{command_prefix}lb'):
        pass


SAVED_LAST_PROBLEMS_PATH = 'saved_last_problems.pkl'
HANDLE_TO_USER_PATH = 'handle_to_user.pkl'
saved_last_problems = load_pickle(SAVED_LAST_PROBLEMS_PATH, { })
handle_to_user = load_pickle(HANDLE_TO_USER_PATH, { })

__message__ = None
command_prefix = "!"

client.run(os.getenv('DISCORD_API_KEY'))

