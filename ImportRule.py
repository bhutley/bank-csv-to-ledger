#!/usr/bin/python
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
                    tax = amount_to_use * self.tax_rate
                else:
                    tax = self.tax_rate
            remainder = amount_to_use - tax
        else:
            amount_to_use = self.amount

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
                    if what_str == 'AMOUNT':
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
        
#rules = parse_rule_file('samples/rules.txt')
#for rule in rules:
#    if rule.matches("An Account", "2011-06-20", "some other stuff", -10000.0):
#        print rule.getLedgerString("An Account", "2011-06-20", "some other stuff", -10000.0)
