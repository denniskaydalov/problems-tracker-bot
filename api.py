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

            problems.append(Problem(name = problem['problem']['name'],
                          timestamp = problem['creationTimeSeconds'],
                          ac = problem['verdict'] == 'OK',
                          url = problem_url,
                          grader='codeforces'))

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

def get_recent_problem_leetcode(handle, count):
    URL="https://leetcode.com/graphql"
    QUERY="""
        {
          recentAcSubmissionList(username: "{0}", limit: {1}) {
            title
            titleSlug
            timestamp
            statusDisplay
            lang
          }
        }
    """.format(handle, count)

    try:
        print('getting_request leetcode', handle)
        responses = requests.get(url = URL, json={"query": QUERY}, timeout=10).json()['data']['recentAcSubmissionList']
        print('got request leetcode', handle, responses)

        if not responses:
            return None

        problems = []

        for problem in responses:
            problems.append(Problem(name = problem['title'],
                           timestamp = problem['timestamp'],
                           ac = problem['statusDisplay'] == 'Accepted',
                           url = f"https://leetcode.com/problems/{problem['titleSlug']}/",
                           grader='leetcode'))

        return problems
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
