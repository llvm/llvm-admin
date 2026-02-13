import argparse
import datetime
import github
import sys
import re


def get_triagers_from_comment(comment):
    if comment.body.find('https://llvm.org/docs/DeveloperPolicy.html#obtaining-commit-access') == -1:
        return []

    triagers = [user[1:].rstrip() for user in re.findall('@[^ ,\n]+', comment.body)]
    return triagers


parser = argparse.ArgumentParser()
parser.add_argument("--show-stats", action="store_true")
# For showing stats you need:
# read:members for organization
# read:issues for repositories
#
# For moving to triagers:
# write:members
# write:issue
#
#
parser.add_argument("--token", required=True)
args = parser.parse_args()
token = args.token
gh = github.Github(login_or_token=token)
repo = gh.get_repo('llvm/llvm-project')
org = gh.get_organization('llvm')
committer_team = org.get_team_by_slug('llvm-committers')
triage_team = org.get_team_by_slug('llvm-triagers')

total_yes = 0
total_no = 0
total_none = 0
total = 0

for issue in repo.get_issues(labels=['infra:commit-access'], state='all'):

    if not args.show_stats and issue.state == 'closed':
        continue

    age = (datetime.datetime.now(datetime.timezone.utc) - issue.created_at).days
    print('****', issue.html_url, issue.state, issue.created_at, age)
    users = [user[1:].rstrip() for user in re.findall('@[^ ,\n]+', issue.body)]
    if issue.state != 'closed':
        print('Affected Users: ')
        print(users)
    triagers = []
    issue_total = len(users)

    for c in issue.get_comments():
        #print(c.user.login)
        if c.user.login in users:
            users.remove(c.user.login)
        if not len(triagers) and issue.state == 'closed':
            triagers = get_triagers_from_comment(c)

    for r in issue.get_reactions():
        if r.user.login in users:
            users.remove(r.user.login)
    if issue.state != 'closed':
        print(users)
        print("Current Traigers:")
        print("@" + " @".join(users))
        if age >= 28 and not args.show_stats:
            for u in users:
            # Move users to the triage team
                name = u.rstrip()
                user = gh.get_user(name)
                if not org.has_in_members(user):
                    continue
                print("Moving ", user)
                committer_team.remove_from_members(user)
                triage_team.add_to_members(user)
                print("Done")
            user_list=" ".join([f"@{name}" for name in users])
            issue.create_comment(f"{user_list} moved to the LLVM Triagers team. If you need write access again, please follow these instructions: https://llvm.org/docs/DeveloperPolicy.html#obtaining-commit-access")
            issue.edit(state="closed")
            
            

    if issue.state == 'closed':
        issue_none = len(users)
        issue_no = len(set(triagers) - set(users))
        issue_yes = issue_total - issue_none - issue_no
        print("Users added to LLVM Triagers: {}".format(" ".join(triagers)))
        print(f"Stats total: {issue_total} yes: {issue_yes} no: {issue_no} none: {issue_none}")

        total_yes += issue_yes
        total_no += issue_no
        total_none += issue_none
        total += issue_total


if args.show_stats:
    print("Full stats: ")
    print("** Total:", total)
    print("** Yes:  ", total_yes, (total_yes / total))
    print("** No:   ", total_no, (total_no / total))
    print("** None: ", total_none, (total_none / total))
