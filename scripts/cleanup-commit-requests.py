import sys

import github


def main():
    # Token needs:
    # * members:read
    # * issues:read/write
    token = sys.argv[1]

    gh = github.Github(login_or_token=token)
    repo = gh.get_repo('llvm/llvm-project')
    org = gh.get_organization('llvm')
    team = org.get_team_by_slug('llvm-committers')

    for issue in repo.get_issues(state = 'open', labels = ['infra:commit-access-request']):
        print(issue.html_url)
        print(issue.user.login)
        comment_text = f'''@{issue.user.login}, you have been granted commit access.  Please review the project's [code review policy](https://llvm.org/docs/CodeReview.html) before submitting a patch.'''
        try:
            membership = team.get_team_membership(issue.user.login)
            print(membership.role, membership.state)
            if membership.role == 'member' and membership.state == 'active':
                print("Close issue")
                issue.create_comment(comment_text)
                issue.edit(state = 'closed')
        except github.GithubException:
            print("No invitation")
        

if __name__ == "__main__":
    main()
