import argparse
import sys
import requests
import datetime
import time

def run_graphql_query(query: str, variables: dict, token: str, retry: bool = True) -> dict:
    """
    This function submits a graphql query and returns the results as a
    dictionary.
    """
    s = requests.Session()
    retries = requests.adapters.Retry(total = 8, backoff_factor = 2, status_forcelist = [504])
    s.mount('https://', requests.adapters.HTTPAdapter(max_retries = retries))

    headers = {
        'Authorization' : 'bearer {}'.format(token),
        # See
        # https://github.blog/2021-11-16-graphql-global-id-migration-update/
        'X-Github-Next-Global-ID': '1'
    }
    request = s.post(
        url = 'https://api.github.com/graphql',
        json = {"query" : query, "variables" : variables },
        headers = headers)

    rate_limit = request.headers.get('X-RateLimit-Remaining')
    if rate_limit and int(rate_limit) < 10:
        reset_time = int(request.headers['X-RateLimit-Reset'])
        while reset_time - int(time.time()) > 0:
            time.sleep(60)
            print("Waiting until rate limit reset", reset_time - int(time.time()), 'seconds remaining')

    if request.status_code == 200:
        if 'data' not in request.json():
            print(request.json())
            sys.exit(1)
        return request.json()['data']
    elif retry:
        return run_graphql_query(query, variables, token, False)
    else:
        raise Exception(
            "Failed to run graphql query\nquery: {}\nerror: {}".format(query, request.json()))

def format_date(date):
    return date.strftime("%Y-%m-%dT%H:%M:%S")


def get_user_issue_comments(user, token, start_date, end_date):

    issue_query = """
        query ($query: String!, $after: String ) {
          search (query: $query, type: ISSUE, first: 100, after: $after) {
            issueCount
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              ... on Issue {
                id
                url
                comments (first: 100) {
                  totalCount
                  nodes {
                    url
                    author {
                      login
                    }
                  }
                }
              }
            }
          }
        }
    """

    formatted_start_date = format_date(start_date)
    formatted_end_date = format_date(end_date)
    variables = {
      "query" : f"type:issue org:llvm commenter:{user} created:{formatted_start_date}..{formatted_end_date}"
    }

    issues = []
    has_next_page = True
    while has_next_page:
        data = run_graphql_query(issue_query, variables, token)

        if data['search']['issueCount'] > 1000:
            print("Error: too many commented issues.  Please specify a shorter time-period.")
            sys.exit(1)

        for issue in data['search']['nodes']:
            if issue['comments']['totalCount'] > 100:
                issues.append(issue['url'])
            else:
                for c in issue['comments']['nodes']:
                    if c['author']['login'] != user:
                        continue
                    issues.append(c['url'])
        has_next_page = data['search']['pageInfo']['hasNextPage']
        if has_next_page:
            variables['after'] = data['search']['pageInfo']['endCursor']
    
    return issues

def get_user_commits(user, token, start_date, end_date):
    variables = {
        "owner" : 'llvm',
        'user' : user,
        'start_date' : format_date(start_date),
        'end_date' : format_date(end_date)
    }

    user_query = """
        query ($user: String!) {
          user(login: $user) {
            id
          }
        }
    """

    data = run_graphql_query(user_query, variables, token)
    variables['user_id'] = data['user']['id']

    query = """
        query ($owner: String!, $user_id: ID!, $start_date: GitTimestamp!, $end_date: GitTimestamp!){
          organization(login: $owner) {
            repositories (first: 100){
              nodes {
                ref(qualifiedName: "main") {
                  target {
                    ... on Commit {
                      history(since: $start_date, until: $end_date, author: {id: $user_id }) {
                        totalCount
                        nodes {
                          url
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
     """
    
    data = run_graphql_query(query, variables, token)
    commits = []
    for repo in data['organization']['repositories']['nodes']:
        if not repo['ref']:
            continue
        if repo['ref']['target']['history']['totalCount'] > 1000:
            print("Error: too many commits.  Please specify a shorter time-period.")
        for commit in repo['ref']['target']['history']['nodes']:
            commits.append(commit['url'])
    return commits


def get_user_activity(user, token, start_date, end_date):
    user_query = """
        query {
          organization(login: "llvm") {
            id
          }
        }
    """

    data = run_graphql_query(user_query, {}, token)
    variables = {
        "org" : data['organization']['id'],
        "user" : user,
        "start_date" : format_date(start_date),
        "end_date" : format_date(end_date)
    }
    query = """
        query ($user: String!, $org:ID!, $start_date: DateTime!, $end_date: DateTime!){
          user(login: $user) {
            contributionsCollection(organizationID:$org, from:$start_date, to:$end_date) {
              issueContributions(first: 100) {
                totalCount
                nodes {
                  issue {
                    url
                  }
                }
              }
              pullRequestContributions(first: 100) {
                totalCount
                nodes {
                  pullRequest {
                    url
                  }
                }
              }
            }
          }
        }
    """

    results = {
        'issues': [],
        'prs' : [],
        'commits' : []
    }

    data = run_graphql_query(query, variables, token)
    for issue in data['user']['contributionsCollection']['issueContributions']['nodes']:
        results['issues'].append(issue['issue']['url'])

    for pr in data['user']['contributionsCollection']['pullRequestContributions']['nodes']:
        results['prs'].append(pr['pullRequest']['url'])

    return results

parser = argparse.ArgumentParser()
parser.add_argument('user')
parser.add_argument('--token')
parser.add_argument('--start-date', type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S'))
parser.add_argument('--end-date', type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S'))

#  --start-date 2024-04-02T17:00:00 --end-date 2024-04-03T14:00:00
args = parser.parse_args()
token = args.token

end_date = args.end_date if args.end_date else datetime.datetime.now()
start_date = args.start_date if args.start_date else end_date - datetime.timedelta(days = 365)
user = args.user

activity = get_user_activity(user, token, start_date, end_date)
print ("Created Issues:")
for i in activity['issues']:
    print(i)
print ("Issue Comments:")
for i in get_user_issue_comments(user, token, start_date, end_date):
    print(i)
print ("Created Pull Requests:")
for p in activity['prs']:
    print(p)
print ("Commits:")
for c in get_user_commits(user, token, start_date, end_date):
    print(c)

