import json
import os
import smtplib
import requests
from email.message import EmailMessage

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
    action = event['action']
    issue = event['issue']


    if action != 'opened' and action != 'closed' and action != 'reopened':
        response["statusCode"] = 200
        response["body"] = '{"status":true}'
        return {
            'statusCode': response["statusCode"],
            'body': response["body"]
        }

    email_subject = '[Issue {issue_number}] {issue_tile}'.format(issue_number = issue['number'],
                                                                 issue_tile = issue['title'])

    email_body="""
{issue_url}

Title: {issue_title}
Reporter: {issue_reporter}
State: {issue_state}

""".format(issue_url = issue['html_url'], issue_title = issue['title'],
           issue_reporter = issue['user']['login'], issue_state = issue['state'])
    if action == 'opened':
        email_body += """
{issue_body}
""".format(issue_body = issue['body'])

    host = os.environ['SMTPHOST']
    port = os.environ['SMTPPORT']
    username = os.environ['SMTP_USERNAME']
    password = os.environ['SMTP_PASSWORD']
    mail_to = 'tstellar@llvm.org'
    mail_from = 'llvm-bugs@lists.llvm.org'
    reply_to = mail_from

    origin = os.environ.get('ORIGIN')
    origin_req = ""
    if not origin:
        cors = '*'
    elif origin_req in [o.strip() for o in origin.split(',')]:
        cors = origin_req

    success = False
    if cors:
        success = send_email(host, port, username, password, email_subject, email_body, mail_to, mail_from, reply_to)

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
