#!/usr/bin/python
import sys
import os
import glob
import csv
import getopt
import ImportRule

def usage():
    print """
Usage: bank-csv-to-ledger [-r <rules.txt>] [-h] csv-file account-string

  -r <rules.txt> - specify the file to use for determining the list of rules.
  -h             - print out these rules.
"""
    exit(0)

optlist, args = getopt.getopt(sys.argv[1:], 'r:h')

rules_file = os.path.expanduser("~/.bank-csv-to-ledger/rules.txt")

for o, a in optlist:
    if o == "-r":
        rules_file = a
    elif o == "-h":
        usage()

if len(args) != 2:
    usage();

filename = args[0]
account = args[1]

if not os.path.isfile(rules_file):
    print "ERROR: the rules file %s doesn't exist" % (rules_file, )
    usage()

if not os.path.isfile(filename):
    print "ERROR: the csv file %s doesn't exist" % (filename, )
    usage()

transactions = {}

class Tran:
    def __init__(self, account, date, desc, amount):
        self.account = account
        self.date = date
        self.desc = desc
        self.amount = float(amount)


    def __str__(self):
        s = ("%s\t%s\n" % (self.date, self.desc))
        s += ("\t%s\t%0.2f\n" % (self.account, self.amount))

        return s


def format_date(dt):
    (dd, mm, yy) = dt.split('/')
    return yy + '-' + mm + '-' + dd

def native_date(dt):
    (yy, mm, dd) = dt.split('-')
    return dd + '/' + mm + '/' + yy


file = open(filename, 'r')
reader = csv.reader(file, dialect = 'excel')

for fields in reader:
    if len(fields) == 3:
        (date, desc, amount) = fields
        date = format_date(date)
        if not transactions.has_key(date):
            transactions[date] = list()
        transactions[date].append(Tran(account, date, desc, amount))

file.close()

rules = ImportRule.parse_rule_file(rules_file)

dates = transactions.keys()
dates.sort()
for dt in dates:
    txl = transactions[dt]
    for tran in txl:
        rule_triggered = False
        for rule in rules:
            if rule.matches(tran.account, tran.date, tran.desc, tran.amount):
                print rule.getLedgerString(tran.account, tran.date, tran.desc, tran.amount)
                rule_triggered = True
                break

        if rule_triggered == False:
            print tran

