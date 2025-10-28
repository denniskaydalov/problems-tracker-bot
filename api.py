from dataclasses import dataclass
import requests
import os
import typing

@dataclass
class Problem:
    name : str
    timestamp : int
    ac : bool
    grader : str
    url : str = None
    rating_grader : str = None
    rating_clist : int = None

def get_recent_problem_codeforces(handle, count):
    URL = 'https://codeforces.com/api/user.status'
    params = { 'handle':handle,
               'from':1,
               'count':count }
    try:
        print('getting_request codeforces', handle)
        response = requests.get(url = URL, params = params, timeout=10)
        print('got request codeforces', handle, response.json())

        recent_problems = response.json()['result']

        if not recent_problems:
            return None
        
        problems = []
        for problem in recent_problems:
            if 'contestId' in problem['problem']:
                contest_id = problem['problem']['contestId']
                if contest_id >= 100000:  # gym problem
                    problem_url = f"https://codeforces.com/gym/{problem['problem']['contestId']}/problem/{problem['problem']['index']}"
                else:
                    problem_url = f"https://codeforces.com/contest/{problem['problem']['contestId']}/problem/{problem['problem']['index']}"
            elif 'problemsetName' in problem['problem']:
                problem_url = f"https://codeforces.com/problemsets/{problem['problem']['problemsetName']}/problem/99999/{problem['problem']['index']}"
            else:
                problem_url = None

            if problem['verdict'] == 'OK':
                problems.append(Problem(name = problem['problem']['name'],
                              timestamp = problem['creationTimeSeconds'],
                              ac = problem['verdict'] == 'OK',
                              url = problem_url,
                              grader='codeforces',
                              rating_grader=(problem['problem'].get('points', None) or problem['problem'].get('rating', None))))

        return problems
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
        print('got request clist', response.json())

        response = response.json()['objects']
        
        if not response:
            return None

        response = response[0]

        if (response['url'] and problem.grader not in response['url']) or (response['archive_url'] and problem.grader not in response['archive_url']):
            return None

        problem.url = response['archive_url'] or response['url']
        problem.rating_clist = response['rating']

        return problem
    except Exception as e:
        print(e)

        return None

def get_profile_url(grader: typing.Literal['codeforces', 'leetcode'], handle: str) -> str:
    if handle is None or handle == '':
        return ''

    match grader:
        case 'codeforces':
            return f'https://codeforces.com/profile/{handle}'
        case 'leetcode':
            return f'https://leetcode.com/u/{handle}/'
        case _:
            return ''

def get_problem_info_leetcode(title_slug):
    URL="https://leetcode.com/graphql"
    QUERY="""
        {{
          question(titleSlug: "{0}") {{
              difficulty
              topicTags {{
                name
                slug
                translatedName
            }}
          }}
        }}
    """.format(title_slug)

    try:
        print('getting request for leetcode info')
        response = requests.get(url = URL, json={"query": QUERY}, timeout=10).json()['data']['question']
        print('got request for leetcode info', response)

        return response
    except Exception as e:
        print(e)
        return None

def get_recent_problem_leetcode(handle, count):
    URL="https://leetcode.com/graphql"
    QUERY="""
        {{
          recentAcSubmissionList(username: "{0}", limit: {1}) {{
            title
            titleSlug
            timestamp
            statusDisplay
            lang
          }}
        }}
    """.format(handle, count)

    try:
        print('getting_request leetcode', handle)
        responses = requests.get(url = URL, json={"query": QUERY}, timeout=10).json()['data']['recentAcSubmissionList']
        print('got request leetcode', handle, responses)

        if not responses:
            return None

        problems = []

        for problem in responses:
            problem_info = get_problem_info_leetcode(problem['titleSlug'])

            problems.append(Problem(name = problem['title'],
                            timestamp = problem['timestamp'],
                            ac = problem['statusDisplay'] == 'Accepted',
                            url = f"https://leetcode.com/problems/{problem['titleSlug']}/",
                            grader = 'leetcode',
                            rating_grader = None or (problem_info and problem_info['difficulty'])))

        return problems
    except Exception as e:
        print(e)
        return None

def get_recent_problems(handle, grader, count):
    if grader == 'codeforces':
        return get_recent_problem_codeforces(handle, count)
    elif grader == 'leetcode':
        return get_recent_problem_leetcode(handle, count)

def update_recent_problems(handle, grader, count, cur, get_clist = False):
    problems = get_recent_problems(handle, grader, count)

    new_problems = []

    if not problems:
        return []

    for problem in problems:
        existing_problem = cur.execute(""" SELECT * FROM problems 
                                           JOIN users ON users.user_id=problems.user_id
                                           WHERE handle=? AND name=? AND grader=?
                                        """, (handle, problem.name, grader))

        if existing_problem.fetchone() is None:
            if get_clist:
                get_clist_info(problem)

            user_id = cur.execute(f"SELECT * FROM users WHERE handle='{handle}' AND grader='{grader}'").fetchone()[0]

            cur.execute("""INSERT INTO problems (user_id, name, timestamp)
                           VALUES (?, ?, ?)""", (user_id, problem.name, problem.timestamp))

            if problem.rating_grader:
                cur.execute("""
                    UPDATE problems 
                    SET rating_grader=?
                    WHERE user_id=? AND name=?
                """, (problem.rating_grader, user_id, problem.name))

            if problem.rating_clist:
                cur.execute("""
                    UPDATE problems 
                    SET rating_clist=?
                    WHERE user_id=? AND name=?
                """, (problem.rating_clist, user_id, problem.name))

            if problem.url:
                cur.execute(""" UPDATE problems 
                                SET url=?
                                WHERE user_id=? AND name=?
                            """, (problem.url, user_id, problem.name))

            new_problems.append(problem)

    return new_problems
