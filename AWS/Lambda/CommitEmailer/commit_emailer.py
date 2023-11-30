# Some (well, honestly most) credit belongs to http://blog.rambabusaravanan.com/send-smtp-email-using-aws-lambda/

import json
import os
import smtplib
import requests
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


def create_project_list(add_list, modify_list, remove_list):
    # Iterate through each list to find the root path of each file.
    # Add the list of files to a set to get a uniquie list of project names.
    add_path_list = [i.split('/')[0] for i in add_list]
    add_temp_set = set(add_path_list)
    mod_path_list = [i.split('/')[0] for i in modify_list]
    mod_temp_set = set(mod_path_list)
    rem_path_list = [i.split('/')[0] for i in remove_list]
    rem_temp_set = set(rem_path_list)

    # Finally return a list of unique project names
    return list(set(list(add_temp_set) + list(mod_temp_set) + list(rem_temp_set)))


def format_diff(diff_url):
    # Setup a constant needed for creating a header.
    REPEAT_VALUE = 80

    # Get the diff from GitHub
    response = requests.get(diff_url)

    # Format the diff and return it.
    diff_header = "#" * REPEAT_VALUE
    formatted_diff = diff_header + '\ndiff '.join(response.text.split('diff'))
    return formatted_diff


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
    # Loop through the commits
    for commit in event['commits']:
        # initialize variables
        author_username = commit['author'].get('name')
        commit_datetime = commit['timestamp']
        commit_hash = commit['id']
        commit_hash_short = commit_hash[:7]
        commit_url = commit['url']
        commit_message = commit['message']
        committer_email = commit['committer'].get('email')
        committer_name = commit['committer'].get('name')
        diff_url = "{}.diff".format(commit_url)
        diff = format_diff(diff_url)
        file_added_list = commit['added']
        files_added_prinatble = '\n    '.join(file_added_list)
        files_modified_list = commit['modified']
        files_modified_prinatble = '\n    '.join(files_modified_list)
        files_removed_list = commit['removed']
        files_removed_printable = '\n    '.join(files_removed_list)
        host = os.environ['SMTPHOST']
        port = os.environ['SMTPPORT']
        mail_from = "{name}".format(name=committer_name)
        origin = os.environ.get('ORIGIN')
        origin_req = ""
        password = os.environ['SMTP_PASSWORD']
        reply_to = "{name} <{email}>".format(name=committer_name,
                                             email=committer_email)
        username = os.environ['SMTP_USERNAME']

        # Setup the body of the message
        body = """
Author: {author_username}
Date: {commit_datetime}
New Revision: {commit_hash}

URL: {commit_url}
DIFF: {diff_url}

LOG: {commit_message}

Added: 
    {files_added}

Modified: 
    {files_modified}

Removed: 
    {files_removed}


{diff}

        """.format(
            author_username=author_username,
            commit_datetime=commit_datetime,
            commit_hash=commit_hash,
            commit_url=commit_url,
            commit_message=commit_message,
            diff_url=diff_url,
            files_added=files_added_prinatble,
            files_modified=files_modified_prinatble,
            files_removed=files_removed_printable,
            diff=diff)

        # Determine project set
        project_list = create_project_list(file_added_list, files_modified_list, files_removed_list)

        # Track the email address last sent to
        last_mail_to = ""

        # Iterate through the list of projects and cross-post if necessary
        for project in project_list:
            # setup the MailTO
            # separate multiple recipient by comma. eg: "abc@gmail.com, xyz@gmail.com"
            # mail_to = os.environ['MAIL_TO']
            mail_to = project_path_email[project]

            # Never send mail about personal branches
            if event['ref'].startswith('refs/heads/users/'):
                break

            # Everything else on a non-trunk branch should be re-directed to the *branch* commits list
            trunk_branches = ['refs/heads/main', 'refs/heads/master']
            if not event['ref'] in trunk_branches:
                mail_to = LLVM_BRANCH_COMMITS_ADDRESS

            # If we're sending an additional email to the same address, break instead
            if mail_to == last_mail_to:
                break

            # Setup the mail Subject
            subject = "[{project}] {short_hash} - {message}".format(message=commit['message'].split('\n')[0],
                                                                    project=project,
                                                                    short_hash=commit_hash_short)

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


