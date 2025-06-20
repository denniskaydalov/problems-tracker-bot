# setup

`.env` needs to have the following fields:

```
DISCORD_API_KEY='...'
CLIST_API_KEY='...'
CLIST_USERNAME='...'
ICPC_BOT_CHANNEL='...' # channel id for problem updates 
ADMIN_USER='...' # admin id to DM incase of uncaught error
```

# dev

## sample responses

PII is hidden

sample response from leetcode `response.json()[0]`

```
{
    "title": "Partition Array Such That Maximum Difference Is K",
    "titleSlug": "partition-array-such-that-maximum-difference-is-k",
    "timestamp": "<int>",
    "statusDisplay": "Accepted",
    "lang": "python3",
    "url": "/submissions/detail/<int>/"
}
```

sample respones from codeforces `response.json()['result'][0]`

```
{
    "id": <int>,
    "contestId": 2121,
    "creationTimeSeconds": <int>,
    "relativeTimeSeconds": <int>,
    "problem": {
        "contestId": 2121,
        "index": "B",
        "name": "Above the Clouds",
        "type": "PROGRAMMING",
        "tags": [
            "constructive algorithms",
            "greedy",
            "strings"
        ]
    },
    "author": {
        "contestId": 2121,
        "participantId": <int>,
        "members": [
            {
                "handle": "<str>"
            }
        ],
        "participantType": "PRACTICE",
        "ghost": False,
        "startTimeSeconds": <int>
    },
    "programmingLanguage": "PyPy 3-64",
    "verdict": "OK",
    "testset": "TESTS",
    "passedTestCount": <int>,
    "timeConsumedMillis": <int>,
    "memoryConsumedBytes": <int>
}
```
