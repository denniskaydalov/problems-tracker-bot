import discord
import requests
import os
from dotenv import load_dotenv
from discord.ext import tasks
import codeforces_api
import leetcode
from dataclasses import dataclass

leetcode_session = os.getenv('LEETCODE_SESSION')
csrf_token = os.getenv('CSRF_TOKEN')

configuration = leetcode.Configuration()

configuration.api_key["x-csrftoken"] = csrf_token
configuration.api_key["csrftoken"] = csrf_token
configuration.api_key["LEETCODE_SESSION"] = leetcode_session
configuration.api_key["Referer"] = "https://leetcode.com"
configuration.debug = False

api_instance = leetcode.DefaultApi(leetcode.ApiClient(configuration))

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

cf = codeforces_api.CodeforcesApi()

saved_last_problems = { }
handle_to_user = {  }

__message__ = None
command_prefix = "$"

@dataclass
class Problem:
    name : str
    timestamp : int
    ac : bool
    grader : str

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    read_last_problem_loop.start()


def get_recent_problem_codeforces(handle):
    recent_problem = cf.user_status(handle=handle, start=1, count=1)[0]

    return Problem(name = recent_problem.problem.name,
                   timestamp = recent_problem.creation_time_seconds,
                   ac = recent_problem.verdict == 'OK',
                   grader='codeforces')

def get_recent_problem_leetcode(handle):
    gql_query = leetcode.GraphqlQuery(
        query="""
            query getRecentSubmissions() {
            recentSubmissionList(username: handle, limit: 1) {
                title
                titleSlug
                timestamp
                statusDisplay
                lang
            }
            }
        """.replace("handle", handle),
        variables=leetcode.GraphqlQueryVariables(),
        operation_name="getRecentSubmissions")

    response = api_instance.graphql_post(body=gql_query)
    print(response)

def recent_problem_update():
    updates = {  }

    for grader in saved_last_problems:
        for handle in saved_last_problems[grader]:
            last_problem = get_recent_problem_codeforces(handle)
            # if saved_last_problems.get(handle, None) == None:
                # saved_last_problems[handle] = last_problem
                # return False

            if last_problem != saved_last_problems[grader][handle] and last_problem.ac:
                update_last_problem(handle, last_problem)
                updates[handle] = last_problem

    return updates

@tasks.loop(seconds=10)
async def read_last_problem_loop():
    recent_problems = recent_problem_update()
    for handle in recent_problems:
        await send_message(f'<@{handle_to_user[handle]}> solved {recent_problems[handle].name}')

async def send_message(message, channel = None):
    global __message__

    if not __message__ and channel:
        __message__ = channel

    message_channel = channel or __message__ or None

    if message_channel: 
        await message_channel.channel.send(message)

def update_last_problem(handle, problem):
    saved_last_problems[problem.grader] = saved_last_problems.get(problem.grader, {})
    saved_last_problems[problem.grader][handle] = problem

def update_handle_to_user(handle, grader):
    handle_to_user

@client.event
async def on_message(message):
    global __message__ 

    if message.author == client.user:
        return

    if message.content.startswith(f'{command_prefix}trackerbotinit'):
        __message__ = message
        await send_message('Init successful in this channel', message)

    if message.content.startswith(f'{command_prefix}hello'):
        await send_message('Hello!', message)
        get_recent_problem_leetcode('dennis458')

    if message.content.startswith(f'{command_prefix}connect'):
        splits = message.content.split(' ')
        if len(splits) > 2:
            grader = splits[1]
            handle = splits[2]
            update_last_problem(handle, get_recent_problem_codeforces(handle))
            handle_to_user[handle] = message.author.id
            await send_message(f'Connected {handle}', message)
        else:
            await send_message(f'Format for connect is `connect <grader> <handle>`.', message)

    if message.content.startswith(f'{command_prefix}unconnect'):
        splits = message.content.split(' ')
        if len(splits) > 2:
            grader = splits[1]
            handle = splits[2]
            if saved_last_problems.pop(handle, None):
                if handle_to_user.pop(handle, None):
                    await send_message(f'Unconnected {handle}', message)
                else:
                    await send_message(f'Erorr unconnecting {handle}, database may be in a bad state', message)
            else:
                await send_message(f'{handle} does not exist in connections', message)
        else:
            await send_message(f'Format for unconnect is `unconnect <grader> <handle>`.', message)

    if message.content.startswith(f'{command_prefix}leaderboard') or message.content.startswith(f'{command_prefix}lb'):
        pass


client.run(os.getenv('DISCORD_API_KEY'))

