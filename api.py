from dataclasses import dataclass
import requests
import os

@dataclass
class Problem:
    name : str
    timestamp : int
    ac : bool
    grader : str
    url : str = None
    rating : int = None

def get_recent_problem_codeforces(handle):
    URL = 'https://codeforces.com/api/user.status'
    params = { 'handle':handle,
               'from':1,
               'count':1 }
    try:
        print('getting_request codeforces', handle)
        response = requests.get(url = URL, params = params, timeout=10)
        print('got request codeforces', handle, response.json())

        recent_problem = response.json()['result']

        if not recent_problem:
            return None
        
        recent_problem = recent_problem[0]
    
        if 'contestId' in recent_problem['problem']:
            contest_id = recent_problem['problem']['contestId']
            if contest_id >= 100000:  # gym problem
                problem_url = f"https://codeforces.com/gym/{recent_problem['problem']['contestId']}/problem/{recent_problem['problem']['index']}"
            else:
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

        response = response.json()['objects']
        
        if not response:
            return None

        response = response[0]

        if grader not in response['url']:
            return None

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
        response = requests.get(url = URL, params = {'limit': 1}, timeout=10).json()
        print('got request leetcode', handle, response)

        if not response:
            return None

        response = response[0]

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
