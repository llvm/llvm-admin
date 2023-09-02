# Some (well, honestly most) credit belongs to http://blog.rambabusaravanan.com/send-smtp-email-using-aws-lambda/

import json
import os
import smtplib
import requests
import github
import re
from email.message import EmailMessage

# Define some constants
CFE_COMMITS_ADDRESS = "cfe-commits@lists.llvm.org"
FLANG_COMMITS_ADDRESS = "flang-commits@lists.llvm.org"
LIBC_COMMITS_ADDRESS = "libc-commits@lists.llvm.org"
LIBCXX_COMMITS_ADDRESS = "libcxx-commits@lists.llvm.org"
LLD_COMMITS_ADDRESS = "llvm-commits@lists.llvm.org"
LLDB_COMMITS_ADDRESS = "lldb-commits@lists.llvm.org"
LLVM_BRANCH_COMMITS_ADDRESS = "llvm-branch-commits@lists.llvm.org"
LLVM_COMMITS_ADDRESS = "llvm-commits@lists.llvm.org"
OPENMP_COMMITS_ADDRESS = "openmp-commits@lists.llvm.org"
PARALLEL_LIBS_COMMITS_ADDRESS = "parallel_libs-commits@lists.llvm.org"
MLIR_COMMITS_ADDRESS = "mlir-commits@lists.llvm.org"


def create_project_list(file_list, projects):
    # Iterate through each list to find the root path of each file.
    # Add the list of files to a set to get a uniquie list of project names.
    path_list = [i.split('/')[0] for i in file_list]
    path_temp_set = set()
    for p in path_list:
        if p in projects:
            path_temp_set.add(p)
            continue
        path_temp_set.add('llvm')

    # Finally return a list of unique project names
    return list(set(list(path_temp_set)))


def format_diff(diff_url):
    # Get the diff from GitHub
    response = requests.get(diff_url)

    return response.text


def get_reply_to(patch):
    m = re.findall(r'From: (.+)', patch)
    return m


# See: https://docs.python.org/3/library/email.examples.html#email-examples
def send_email(host, port, username, password, subject, body, mail_to, mail_from=None, reply_to=None):
    if mail_from is None: mail_from = username
    if reply_to is None: reply_to = mail_to

    try:
        email = EmailMessage()
        email.set_content(body)
        email['Subject'] = subject
        email['From'] = mail_from
        email['To'] = mail_to
        email['Reply-To'] = reply_to
        print(email)

        server = smtplib.SMTP(host, port)
        server.ehlo()
        server.starttls()
        server.login(username, password)
        server.send_message(email)
        server.close()
        return True
    except Exception as ex:
        print(ex)
        return False

def event_get_pr_html_url(event):
    if 'pull_request' in event:
        return event['pull_request']['html_url']

    return event_get_pr_html_url(event['issue'])

def event_get_pr_number(event):
    if 'pull_request' in event:
        return event['pull_request']['number']
    return event['issue']['number']

def event_get_pr_title(event):
    if 'pull_request' in event:
        return event['pull_request']['title']
    return event['issue']['title']

def event_get_pr_patch_url(event):
    if 'pull_request' in event:
        return event['pull_request']['patch_url']
    return event_get_pr_patch_url(event['issue'])

def get_synchronize_email_body(event, patch):

    user = event['sender']['login']
    pr_html = event_get_pr_html_url(event)
    pr_number = event_get_pr_number(event)

    return f"""
https://github.com/{user} updated {pr_html}:

{patch}
"""

def get_open_email_body(event, patch):
    user = event['sender']['login']
    pr_html = event_get_pr_html_url(event)
    pr_body = event['pull_request']['body']

    return f"""
https://github.com/{user} created {pr_html}:

{pr_body}

{patch}
"""

def get_review_comment_email_body(event):
    diff_hunk = event['comment']['diff_hunk']
    body = event['comment']['body']
    user = event['sender']['login']
    pr_html = event_get_pr_html_url(event)

    return f"""
================
{diff_hunk}
----------------
{user} wrote:

{body}

{pr_html}
"""

def get_issue_comment_created_email_body(event):
    body = event['comment']['body']
    user = event['sender']['login']
    pr_html = event_get_pr_html_url(event)

    return f"""
{user} wrote:

{body}

{pr_html}
"""

def get_issue_comment_edited_email_body(event):
    body = event['comment']['body']
    user = event['sender']['login']
    pr_html = event_get_pr_html_url(event)

    return f"""
{user} edited a comment:

{body}

{pr_html}
"""

def get_pull_request_assigned_email_body(event):
    user = event['sender']['login']
    assignee = event['assignee']['login']
    pr_html = get_pr_html_url(event)

    return f"""
{user} assigned {pr_html} to {assignee}.
"""

def get_pull_request_review_submitted_email_body(event):
    user = event['sender']['login']
    user_html_url = event['sender']['html_url']
    body = event['review']['body']
    state = event['review']['state']
    pr_html = event_get_pr_html_url(event)
    action = state

    if state == 'changes_requested':
        action_string = f"{user_html_url} requested changes to this pull request.\n\n"
    elif state == 'commented':
        action_string = f'{user_html_url} commented:\n\n'
    else:
        # state == 'approved' or any new states that are added.
        action_string = f'{user_html_url} {state} this pull request.\n\n'

    comment_string = ''
    if body:
        comment_string = f"{body}\n"

    return f"""
{action_string}{comment_string}
{pr_html}
"""


def get_generic_email_body(event, patch):
    user = event['sender']['login']
    pr_html = event_get_pr_html_url(event)
    action = event['action']
    return f"""
https://github.com/{user} {action} {pr_html}
"""

def TODO(event, patch):
    return get_generic_email_body(event, patch)

def get_event_kind(event):
    if 'issue' in event:
        return 'issue_comment'
    if 'comment' in event:
        return 'pull_request_review_comment'
    if 'thread' in event:
        return 'pull_request_review_thread'
    if 'review' in event:
        return 'pull_request_review'
    return 'pull_request'


def is_main_branch_event(event, gh_pr):
    if 'pull_request' in event:
        return event['pull_request']['base']['ref'] == "main"

    return gh_pr.base.ref == 'main'


def get_skip_response(message):
    return {
        'statusCode' : 200,
        'body' : f'{{"status" : "true", "message" : "{message}"}}'
    }


def lambda_handler(event, context):

    # Define project path dict
    project_path_email = {
        'cfe-branch': LLVM_BRANCH_COMMITS_ADDRESS,
        'clang-tools-extra': CFE_COMMITS_ADDRESS,
        'clang': CFE_COMMITS_ADDRESS,
        'compiler-rt': LLVM_COMMITS_ADDRESS,
        'compiler-rt-tag': LLVM_BRANCH_COMMITS_ADDRESS,
        'debuginfo-tests': LLVM_COMMITS_ADDRESS,
        'flang': FLANG_COMMITS_ADDRESS,
        'libc': LIBC_COMMITS_ADDRESS,
        'libclc': CFE_COMMITS_ADDRESS,
        'libcxx': LIBCXX_COMMITS_ADDRESS,
        'libcxxabi': LIBCXX_COMMITS_ADDRESS,
        'libunwind': CFE_COMMITS_ADDRESS,
        'lld': LLD_COMMITS_ADDRESS,
        'lldb': LLDB_COMMITS_ADDRESS,
        'llvm': LLVM_COMMITS_ADDRESS,
        'mlir' : MLIR_COMMITS_ADDRESS,
        'openmp': OPENMP_COMMITS_ADDRESS,
        'parallel-libs': PARALLEL_LIBS_COMMITS_ADDRESS,
        'polly': LLVM_COMMITS_ADDRESS,
        'pstl': LIBCXX_COMMITS_ADDRESS,
        'zorg': LLVM_COMMITS_ADDRESS
    }

    # Handle no-op events earlier to reduce processing time
    event_kind = get_event_kind(event)
    if event_kind == 'issue_comment':
        if 'pull_request' not in event['issue']:
            return get_skip_response("Ignored issue comment")
    elif event_kind == 'pull_request_review':
        if event['review']['state'] == 'commented' and not event['review']['body']:
            return get_skip_response("pull_request_review has no body message")


    gh_token = os.environ.get('GH_TOKEN')
    gh = github.Github(login_or_token=gh_token)
    pr_number = event_get_pr_number(event)
    pr_title = event_get_pr_title(event)
    user = gh.get_user(event['sender']['login'])
    patch_url = event_get_pr_patch_url(event)
    patch = requests.get(patch_url).text

    host = os.environ.get('SMTPHOST')
    port = os.environ.get('SMTPPORT')
    mail_from = "{name}".format(name=user.name)
    origin = os.environ.get('ORIGIN')
    origin_req = ""
    password = os.environ.get('SMTP_PASSWORD')
    reply_to = ','.join(get_reply_to(patch))
    username = os.environ.get('SMTP_USERNAME')

    # Webhook Events:
    # issue_comment
    # pull_request
    # pull_request_review_comment
    # pull_request_review
    # pull_request_review_thread


    action = event['action']
    body = ""

    if event_kind == 'issue_comment':
        if action == 'created':
            body = get_issue_comment_created_email_body(event)
        elif action == 'deleted':
            return get_skip_response("Ignored deleted comment")
        elif action == 'edited':
            body = get_issue_comment_edited_email_body(event, patch)
        else:
            TODO(event, patch)
    elif event_kind == 'pull_request':
        if action == 'assigned':
            body = get_pull_request_assigned_email_body(event, patch)
        elif action == 'auto_merge_disabled':
            body = TODO(event, patch)
        elif action == 'auto_merge_enabled':
            body = TODO(event, patch)
        elif action == 'closed':
            body = TODO(event, patch)
        elif action == 'converted_to_draft':
            body = TODO(event, patch)
        elif action == 'demilestoned':
            body = TODO(event, patch)
        elif action == 'dequeued':
            body = TODO(event, patch)
        elif action == 'edited':
            body = TODO(event, patch)
        elif action == 'enqueued':
            body = TODO(event, patch)
        elif action == 'labeled':
            body = TODO(event, patch)
        elif action == 'locked':
            body = TODO(event, patch)
        elif action == 'milestoned':
            body = TODO(event, patch)
        elif action == "opened":
            body = get_open_email_body(event, patch)
        elif action == 'ready_for_review':
            body = TODO(event, patch)
        elif action == 'reopened':
            body = TODO(event, patch)
        elif action == 'review_request_removed':
            body = TODO(event, patch)
        elif action == 'review_requested':
            body = TODO(event, patch)
        elif action == "synchronize":
            body = get_synchronize_email_body(event, patch)
        elif action == 'unassigned':
            body = TODO(event, patch)
        elif action == 'unlabled':
            body = TODO(event, patch)
        elif action == 'unlocked':
            body = TODO(event, patch)
        else:
            body = get_generic_email_body(event, patch)
    elif event_kind == 'pull_request_review_comment':
        if action == 'created':
            body = get_review_comment_email_body(event)
        elif action == 'deleted':
            body = TODO(event, patch)
        elif action == 'edited':
            body = TODO(event, patch)
        else:
            body = get_generic_email_body(event, patch)
    elif event_kind == 'pull_request_review_thread':
        if action == 'resolved':
            body = TODO(event, patch)
        elif action == 'unresolved':
            body = TODO(event, patch)
        else:
            body = get_generic_email_body(event, patch)
    elif event_kind == 'pull_request_review':
        if action == 'dismissed':
            body = TODO(event, patch)
        elif action == 'edited':
            body = TODO(event, patch)
        elif action == 'submitted':
            body = get_pull_request_review_submitted_email_body(event)
        else:
            body = get_generic_email_body(event, patch)
    else:
        body = get_generic_email_body(event, patch)


    print(body)
    # Get the project lists
    project_list = set()
    gh_pr = gh.get_repo('llvm/llvm-project').get_issue(pr_number).as_pull_request()
    for commit in gh_pr.get_commits():
        project_list.update(create_project_list([f.filename for f in commit.files], project_path_email))
    # Track the email address last sent to
    last_mail_to = ""

    # Iterate through the list of projects and cross-post if necessary
    #print(project_list)
    #print(body)
    for project in project_list:
        # setup the MailTO
        # separate multiple recipient by comma. eg: "abc@gmail.com, xyz@gmail.com"
        # mail_to = os.environ['MAIL_TO']
        mail_to = project_path_email[project]

        if not is_main_branch_event(event, gh_pr):
            mail_to = LLVM_BRANCH_COMMITS_ADDRESS

        # If we're sending an additional email to the same address, break instead
        if mail_to == last_mail_to:
            break

        if 'MAIL_TO' in os.environ:
            mail_to = os.environ.get('MAIL_TO')
        # Setup the mail Subject
        subject = f"[{project}] {pr_title} (PR #{pr_number})"

        # validate cors access
        cors = ''
        if not origin:
            cors = '*'
        elif origin_req in [o.strip() for o in origin.split(',')]:
            cors = origin_req

        # send mail
        success = False
        if cors:
            success = send_email(host, port, username, password, subject, body, mail_to, mail_from, reply_to)
            last_mail_to = mail_to
        else:
            print('mail_to: ', mail_to)
            print('mail_from: ', mail_from)
            print('reply_to: ', reply_to)
            print(subject)
            print(body)


    # prepare response
    response = {
        "isBase64Encoded": False,
        "headers": {"Access-Control-Allow-Origin": cors}
    }
    if success:
        response["statusCode"] = 200
        response["body"] = '{"status":true}'
    elif not cors:
        response["statusCode"] = 403
        response["body"] = '{"status":false}'
    else:
        response["statusCode"] = 400
        response["body"] = '{"status":false}'

    return {
        'statusCode': response["statusCode"],
        'body': response["body"]
    }
