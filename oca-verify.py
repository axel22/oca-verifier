import github3, ConfigParser
from itertools import chain
import csv
import argparse

#
# OCA verifier
# Checks github pullrequest whether an author has signed the OCA
#   if not it sends a comment to github which instructs the author to do so
#   if all are clear to merge, the labels are applied
#
# Installation:
# Create config files and database csv as in the sample
# install github3.py with pip:
#    pip install git+git://github.com/sigmavirus24/github3.py
# 
# Run the script in a cronjob: 
#    python oca-verifier.py -c oca-check.prop -d ./oca-list.csv
# 
# CSV database format, separator char=',':
#   Column 1: E-Mail address
#   Column 2: Assigned label
# 
# Configfile:
#  [GitHub]
#  username=sanzinger
#  password=lohokla2806
#  repositories=sanzinger/testrepo,graalvm/graal-core
#



def debug(msg):
    print "DEBUG: " + str(msg)

def info(msg):
    print "INFO: " + str(msg)

def readOcaList(fileName):
    ':type fileName: str'
    ':rtype dict(str, dict(str, str))'
    
    result = {}
    with open(fileName, 'rb') as csvFile:
        rd = csv.reader(csvFile, delimiter=',')
        for row in rd:
            email = canonicalizeEmail(row[0])
            assert email not in result, "File {0} contains {1} more than once.".format(csvFile, email) 
            result[row[0]] = {'label': row[1]}
    return result

def hasLabel(pr, labelNames):
    ':type pr: PullRequest'
    ':type labelNames: iterable(str)'
    ':rtype bool'
    labels = pr.issue().labels()
    labelsMatch = [l.name for l in labels if l.name in labelNames]
    return len(labelsMatch) > 0

def getAuthors(commits):
    ':type commits: iterable(RepoCommit)'
    ':rtype iterable(dict)'
    result = []
    emails = []
    for c in commits:
        author = c.commit.author
        email = canonicalizeEmail(author["email"])
        if email not in emails:
            result.append(author)
            emails.append(email)
    return result

def canonicalizeEmail(email):
    return email.lower()

def urgeMessage(author):
    return "User {0} with email address {1} has not signed Oracle OCA".format(author["name"], author["email"])

def findCommentContainsMessage(pr, message):
    ':type pr: PullRequest'
    ':type message: str'
    ':rtype IssueComment'
    issue = pr.issue()
    for c in issue.comments(): #: :type c: IssueComment'
        if message in c.body:
            return c
    return None

def urgeClearMessage(author):
    return "User {0} with email address {1} is clear for merging this pull request".format(author["name"], author["email"])

def remainingUrgesMessage(authors):
    return "Following email(s) have not yet signed OCA: {0}".format(", ".join([i["email"] for i in authors]))

def urgeOca(pr, author):
    ':type pr: PullRequest'
    ':type author: dict'
    message = urgeMessage(author)
    issue = pr.issue() #: :type issue: Issue
    issue.create_comment(message)

def processEmpty(pr, oca):
    ':type pr: PullRequest'
    prNumber = pr.number
    authors = getAuthors(pr.commits())
    debug("PullRequest {0} has authors: {1}".format(prNumber, ", ".join([a["email"] for a in authors])))
    labels = set()
    allAuthorsOk = True
    prMessages = []
    openUrges = []
    oneHasChanged = False
    for a in authors:
        email = canonicalizeEmail(a["email"])
        msgUrge = urgeMessage(a)
        hasUrged = findCommentContainsMessage(pr, msgUrge) is not None
        if email not in oca:
            allAuthorsOk = False
            if not hasUrged:
                debug("Urging OCA for author {0}".format(email))
                prMessages.append(msgUrge)
            else:
                debug("OCA for author {0} on PR {1} is still pending".format(email, prNumber))
                openUrges.append(a)
        else:
            if hasUrged:
                debug("OCA for author {0} has been signed".format(email))
                msgClear = urgeClearMessage(a)
                if findCommentContainsMessage(pr, msgClear) is None:
                    prMessages.append(msgClear)
                oneHasChanged = True
            labels.add(oca[email]['label'])
    if allAuthorsOk:
        info("All authors on PR {0} are ok, applying labels {1}".format(prNumber, ", ".join(labels)))
        for l in labels:
            issue = pr.issue() #: :type issue: Issue
            issue.add_labels(l)
    elif oneHasChanged and len(openUrges) > 0:
        info("OCA for authors {0} on PR {1} is pending".format(", ".join([a["email"] for a in openUrges]), prNumber))
        prMessages.append(remainingUrgesMessage(openUrges))

    if len(prMessages):
        comment = " * " + "\n *  ".join(prMessages)
        debug("Creating comment " + comment)
        pr.issue().create_comment(comment)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Checks all authors in pull request has signed the OCA")
    p.add_argument('-c', dest='conf', required=True, help="Configuration for log into GitHub and select watched repositories")
    p.add_argument('-d', dest='db'  , required=True, help="CSV file, which contains pairs of email label to assign in GitHub pullrequest")
    args = p.parse_args()
    
    config = ConfigParser.RawConfigParser()
    config.read(args.conf)
    
    repos =  [i.strip().split('/') for i in config.get('GitHub', 'repositories').split(',')]
    ocaList = readOcaList(args.db)
    requiredLabels = set([ocaList[i]["label"] for i in ocaList])
    
    gh = github3.login(token=config.get('GitHub', 'token'))
    
    pullRequests = chain.from_iterable([gh.repository(i[0], i[1]).pull_requests() for i in repos])
    withoutLabel = filter(lambda pr: not hasLabel(pr, requiredLabels), pullRequests)
    for pr in withoutLabel:
        processEmpty(pr, ocaList)