#!/usr/bin/python
import sys
import os
import glob
import csv
import getopt
import shlex

class RuleCondition:
    # what
    PAYEE = 1
    DESC = 2
    AMOUNT = 3
    DATE = 4

    # pred
    CONTAINS = 1
    STARTS_WITH = 2
    ENDS_WITH = 3

    EQUALS = 4
    # applies to both amounts and dates
    GT = 5
    GE = 6
    LT = 7
    LE = 8

    STRING_TEST = 1
    NUMBER_TEST = 2

    def __init__(self, what, pred, value):
        self.what = what
        self.pred = pred
        self.value = value

    def matches(self, account, date, desc, amount):
        test_type = RuleCondition.STRING_TEST
        test_str = ''
        
        if self.what == RuleCondition.PAYEE:
            test_str = account
        elif self.what == RuleCondition.DESC:
            test_str = desc
        elif self.what == RuleCondition.DATE:
            test_str = date
        elif self.what == RuleCondition.AMOUNT:
            test_type = RuleCondition.NUMBER_TEST

        if test_type == RuleCondition.NUMBER_TEST and self.pred < RuleCondition.EQUALS:
            raise Exception("Can't have a predicate of %s when testing the amount" % (str(self.pred), ))

        if self.pred == RuleCondition.EQUALS:
            if test_type == RuleCondition.NUMBER_TEST:
                return amount == float(self.value)
            else:
                return test_str == self.value
        elif self.pred == RuleCondition.CONTAINS:
            return test_str.find(self.value) >= 0
        elif self.pred == RuleCondition.STARTS_WITH:
            return test_str.startswith(self.value)
        elif self.pred == RuleCondition.ENDS_WITH:
            return test_str.endswith(self.value)
        elif self.pred == RuleCondition.GT:
            if test_type == RuleCondition.NUMBER_TEST:
                return amount > float(self.value)
            else:
                return test_str > self.value
        elif self.pred == RuleCondition.GE:
            if test_type == RuleCondition.NUMBER_TEST:
                return amount >= float(self.value)
            else:
                return test_str >= self.value
        elif self.pred == RuleCondition.LT:
            if test_type == RuleCondition.NUMBER_TEST:
                return amount < float(self.value)
            else:
                return test_str < self.value
        elif self.pred == RuleCondition.LE:
            if test_type == RuleCondition.NUMBER_TEST:
                return amount <= float(self.value)
            else:
                return test_str <= self.value
        return False


class Allocation:
    def __init__(self, is_percent, account, amount, tax_is_percent, tax_account, tax_rate):
        self.is_percent = is_percent
        self.account = account
        self.amount = amount
        self.tax_is_percent = tax_is_percent
        self.tax_account = tax_account
        self.tax_rate = tax_rate

    def getLedgerString(self, amount):
        tax = 0.0
        remainder = 0.0
        if self.is_percent:
            amount_to_use = amount * self.amount
            if self.tax_account is not None:
                if self.tax_is_percent:
                    tax = amount_to_use / (1.0 + self.tax_rate)
                else:
                    tax = self.tax_rate
            remainder = amount - tax
        else:
            amount_to_use = -self.amount

            if self.tax_account is not None:
                if self.tax_is_percent:
                    tax = amount_to_use * self.tax_rate
                else:
                    tax = self.tax_rate

            remainder = amount_to_use

        s = ("\t%s\t%.2f\n" % (self.account, -remainder))
        if tax != 0.0 and self.tax_account is not None and len(self.tax_account) > 0:
            s += ("\t%s\t%.2f\n" % (self.tax_account, -tax))
        return s

class ImportRule:
    ALL = 1
    ANY = 2

    def __init__(self):
        self.name = None
        self.matches_all_or_any = ImportRule.ALL
        self.conditions = []
        self.allocations = []
        self.ignore = False

    def matches(self, account, date, desc, amount):
        if self.matches_all_or_any == ImportRule.ALL:
            for condition in self.conditions:
                if not condition.matches(account, date, desc, amount):
                    return False
            return True
        else:
            for condition in self.conditions:
                if condition.matches(account, date, desc, amount):
                    return True
            return False

    def getLedgerString(self, account, date, desc, amount):
        s = ("%s\t%s\n" % (date, desc))
        s += ("\t%s\t%0.2f\n" % (account, amount))
        for allocation in self.allocations:
            s += allocation.getLedgerString(amount)
        return s

def parse_rule_file(filename):
    IN_IDLE = 0
    IN_RULE = 1
    IN_CONDITIONS = 2
    IN_ALLOCATION = 3

    rules = []
    rules_by_name = {}

    cur_rule = None
    state = IN_IDLE
    file = open(filename, 'r')
    for line in file:
        line = line.strip()
        # Don't process the line if it starts with a comment char
        if not line.startswith(';') and not line.startswith('#'):
            if line.startswith('Rule:'):
                # we are in a new rule.
                # if we have finished with the previous rule, add it to our list.
                if cur_rule is not None:
                    if cur_rule.name is None:
                        raise Exception("The current rule does not have a name!")

                    if rules_by_name.has_key(cur_rule.name):
                        raise Exception("A rule named '%s' already exists in our rule list" % (cur_rule.name, ))
                    rules.append(cur_rule)
                    rules_by_name[cur_rule.name] = cur_rule
                cur_rule = ImportRule()
                state = IN_RULE

            if state == IN_RULE or state == IN_CONDITIONS or state == IN_ALLOCATION:
                if line.startswith('Name:'):
                    cur_rule.name = line[5:].strip()
                if line.startswith('Ignore:'):
                    cur_rule.ignore = True
                elif line.startswith('Conditions:'):
                    state = IN_CONDITIONS
                elif line.startswith('Allocations:'):
                    state = IN_ALLOCATION
                elif state == IN_CONDITIONS:
                    fields = shlex.split(line)
                    if len(fields) == 3:
                        what_str = fields[0]
                        pred_str = fields[1]
                        value_str = fields[2]
                        what = None
                        pred = None
                        if what_str == 'PAYEE':
                            what = RuleCondition.PAYEE
                        elif what_str == 'AMOUNT':
                            what = RuleCondition.AMOUNT
                        elif what_str == 'DESC':
                            what = RuleCondition.DESC
                        elif what_str == 'AMOUNT':
                            what = RuleCondition.AMOUNT
                        elif what_str == 'DATE':
                            what = RuleCondition.DATE
                        else:
                            raise Exception("Unknown 'what' field '%s' in Condition list." % (what_str, ))

                        if pred_str == 'EQUALS' or pred_str == '==' or pred_str == 'EQ':
                            pred = RuleCondition.EQUALS
                        elif pred_str == 'CONTAINS':
                            pred = RuleCondition.CONTAINS
                        elif pred_str == 'STARTS_WITH':
                            pred = RuleCondition.STARTS_WITH
                        elif pred_str == 'ENDS_WITH':
                            pred = RuleCondition.ENDS_WITH
                        elif pred_str == 'GT' or pred_str == '>':
                            pred = RuleCondition.GT
                        elif pred_str == 'GE' or pred_str == '>=':
                            pred = RuleCondition.GE
                        elif pred_str == 'LT' or pred_str == '<':
                            pred = RuleCondition.LT
                        elif pred_str == 'LE' or pred_str == '<=':
                            pred = RuleCondition.LE
                        else:
                            raise Exception("Unknown Condition predicate '%s'" % (pred_str, ))

                        rule_condition = RuleCondition(what, pred, value_str)
                        cur_rule.conditions.append(rule_condition)

                elif state == IN_ALLOCATION:
                    fields = shlex.split(line)
                    if len(fields) == 2 or len(fields) == 4:
                        account_str = fields[0]
                        amount_str = fields[1]
                        tax_account_str = None
                        tax_str = None
                        if len(fields) == 4:
                            tax_account_str = fields[2]
                            tax_str = fields[3]

                        is_percent = False

                        tax_is_percent = False
                        tax = 0.0
                        if tax_str is not None:
                            if tax_str.endswith('%'):
                                tax = float(tax_str[:-1]) / 100.0
                                tax_is_percent = True
                            else:
                                tax = float(tax_str)

                        amount = 0.0
                        if amount_str.endswith('%'):
                            amount = float(amount_str[:-1]) / 100.0
                            is_percent = True
                        else:
                            amount = float(amount_str)

                        allocation = Allocation(is_percent, account_str, amount, tax_is_percent, tax_account_str, tax)
                        cur_rule.allocations.append(allocation)

    file.close()

    if cur_rule is not None:
        if cur_rule.name is None:
            raise Exception("The current rule does not have a name!")

        if rules_by_name.has_key(cur_rule.name):
            raise Exception("A rule named '%s' already exists in our rule list" % (cur_rule.name, ))
        rules.append(cur_rule)
        rules_by_name[cur_rule.name] = cur_rule

    return rules

def usage():
    print """
Usage: bank-csv-to-ledger [-r <rules.txt>] [-h] csv-file account-string

  -r <rules.txt>  - specify the file to use for determining the list of rules.
  -D <dateFormat> - specify the date format [Y-M-D/D M Y/etc] (default D/M/Y)
  -u              - print unmatched transactions only.
  -U              - print unmatched in rule format.
  -I              - ignore first line
  -h              - print out these rules.
"""
    exit(0)

date_format = 'D/M/Y'
ignore_first_line = False
optlist, args = getopt.getopt(sys.argv[1:], 'r:D:huUI')

rules_file = os.path.expanduser("~/.bank-csv-to-ledger/rules.txt")
print_unmatched_only = False
print_unmatched_as_rules = False

for o, a in optlist:
    if o == "-r":
        rules_file = a
    elif o == "-h":
        usage()
    elif o == "-u":
        print_unmatched_only = True
    elif o == "-U":
        print_unmatched_as_rules = True
    elif o == "-D":
        date_format = a
    elif o == '-I':
        ignore_first_line = True

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
        s = ("%s,%s,%.2f" % (self.date, self.desc, self.amount))
        return s

    def getLedgerString(self):
        s = ("%s\t%s\n" % (self.date, self.desc))
        s += ("\t%s\t%0.2f\n" % (self.account, self.amount))
        return s

def monthstr_to_month(ms):
    monthstrings = [ 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec', ]

    ms = ms.lower()
    for i in xrange(0, len(monthstrings)):
        if monthstrings[i] == ms:
            return "%02d" % (i + 1, )
    raise Exception("Invalid month '%s'" % (ms, ))
    
def format_date(date_format, dt):
    delimiter = '/'
    if date_format.find(' '):
        delimiter = ' '
    elif date_format.find('-'):
        delimiter = '-'
    parts = date_format.split(delimiter)
    if len(parts) != 3:
        raise Exception("Invalid date format '%s'" % (date_format, ))
    day_offset, month_offset, year_offset = -1, -1, -1
    for i in xrange(0, len(parts)):
        if parts[i].startswith('D'):
            day_offset = i
        elif parts[i].startswith('M'):
            month_offset = i
        elif parts[i].startswith('Y'):
            year_offset = i
        else:
            raise Exception("Invalid date format '%s'" % (date_format, ))

    if day_offset == -1 or month_offset == -1 or year_offset == -1:
        raise Exception("Invalid date format '%s'" % (date_format, ))
        
    fields = dt.split(delimiter)
    if len(fields) != 3:
        raise Exception("Date '%s' doesn't match date format '%s'" % (dt, date_format))

    dd = fields[day_offset]
    mm = fields[month_offset]
    yy = fields[year_offset]

    if len(mm) == 3:
        mm = monthstr_to_month(mm)
    if len(yy) == 2:
        if int(yy) > 70:
            yy = '19' + yy
        else:
            yy = '20' + yy

    return "%d-%02d-%02d" % (int(yy), int(mm), int(dd), )

def native_date(dt):
    (yy, mm, dd) = dt.split('-')
    return dd + '/' + mm + '/' + yy


file = open(filename, 'r')
reader = csv.reader(file, dialect = 'excel')

for fields in reader:
    if len(fields) == 3 and ignore_first_line == False:
        (date, desc, amount) = fields
        date = format_date(date_format, date)
        if not transactions.has_key(date):
            transactions[date] = list()
        transactions[date].append(Tran(account, date, desc, amount))
    if ignore_first_line == True:
        ignore_first_line = False

file.close()

unmatched_rules = {}

rules = parse_rule_file(rules_file)

dates = transactions.keys()
dates.sort()
for dt in dates:
    txl = transactions[dt]
    for tran in txl:
        rule_triggered = False
        for rule in rules:
            if rule.matches(tran.account, tran.date, tran.desc, tran.amount):
                if print_unmatched_only == False and print_unmatched_as_rules == False and not rule.ignore:
                    print rule.getLedgerString(tran.account, tran.date, tran.desc, tran.amount)
                rule_triggered = True
                break

        if rule_triggered == False:
            if print_unmatched_only:
                print tran
            elif print_unmatched_as_rules:
                if not unmatched_rules.has_key(tran.desc):
                    unmatched_rules[tran.desc] = tran
            else:
                print tran.getLedgerString()

if print_unmatched_as_rules:
    desclist = unmatched_rules.keys()
    desclist.sort()
    for desc in desclist:
        print("Rule:")
        print("  Name: %s" % (desc,) )
        print("  Conditions:")
        print("    DESC EQUALS \"%s\"" % (desc,) )
        print("  Allocations:")
        print("    \"UNKNOWN:Unknown\" 100%")
        print
