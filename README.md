# OCA Verification Bot

Checks github pullrequest whether all commiting authors in a pull request have signed the OCA
 * if not it sends a comment to github which instructs the author to do so
 * if all are clear to merge, the labels are applied

## Installation

install github3.py with pip:
 
    pip install git+git://github.com/sigmavirus24/github3.py
 
Create config files and database csv as in the sample:

CSV database format, separator char=',':
 * Column 1: E-Mail address
 * Column 2: Assigned label
 
Configfile:

    [GitHub]
    token=<accesstoken>
    repositories=sanzinger/testrepo,graalvm/graal-core

Run the script as a cronjob: 

    python oca-verify.py -c oca-verify.properties -d ./oca-list.csv