# coding: utf8
import csv
import sys
import requests

from datetime import datetime, timedelta


class YnabClient():
    ynab_base_url = "https://api.youneedabudget.com/v1/"
    headers = {}

    def __init__(self, access_token):
        self.headers["Authorization"] = "Bearer " + access_token

    def get_budgets(self):
        url = self.ynab_base_url + "budgets/"

        r = requests.get(url, headers=self.headers)
        return r.json()["data"]["budgets"]

    def get_budgets_ids(self):
        return [b["id"] for b in self.get_budgets()]

    def get_transactions(self, budget_id, since_date=None):
        url = self.ynab_base_url + "budgets/%s/transactions/" % budget_id

        if since_date:
            url += "?since_date=%s" % since_date.strftime("%y-%m-%d")

        r = requests.get(url, headers=self.headers)
        return r.json()["data"]["transactions"]

    def add_transactions(self, budget_id, account_id, card_transactions):
        transactions_payload = []
        for transaction in card_transactions:
            transactions_payload.append({
                "account_id": account_id,
                "date": transaction["Datum"],
                # *-1 since it's an expense, *1000 to put in correct unit
                "amount": int(float(transaction["Belopp"]) * -1 * 1000),
                "payee_id": None,
                "payee_name": transaction["Specifikation"],
                "category_id": None,
                "memo": None,
                "cleared": "cleared" if transaction["Bokfört"] != "Reserverat" else "uncleared",
                "approved": False,
                "flag_color": None,
                "import_id": None
            })
        payload = {"transactions": transactions_payload}
        url = self.ynab_base_url + "budgets/%s/transactions/bulk" % budget_id
        r = requests.post(url, json=payload, headers=self.headers)
        return r.json()

    def update_transaction(self, budget_id, transaction_id, transaction):
        payload = {"transaction": transaction}
        url = self.ynab_base_url + "budgets/%s/transactions/%s" % (budget_id, transaction_id)

        r = requests.put(url, json=payload, headers=self.headers)
        return r.json()


def read_and_clean_file():
    transaction_rows = []
    header = ""

    with open(sys.argv[2], 'rU') as csvFile:
        csvreader = csv.reader(csvFile, delimiter=';', dialect=csv.excel_tab)
        rows = [r for r in csvreader]

    for row in rows:
        if "Datum" in row:
            header = row
        try:
            datetime.strptime(row[0], '%m-%d')
            transaction_rows.append(row)
        except ValueError:
            # Not a date, so ignore row
            continue

    yield "\t".join(header)
    for row in transaction_rows:
        row[0] = '%s-%s' % (datetime.now().year, row[0])
        # First replace to dots then replace the unicode space chars
        row[6] = row[6].replace(',', '.').replace('\xc2\xa0','')
        yield "\t".join(row)


def get_transactions_from_file():
    transaction_rows = []
    csvreader = csv.DictReader(read_and_clean_file(), delimiter="\t", dialect=csv.excel_tab)
    for row in csvreader:
        transaction_rows.append(row)
    return sorted(transaction_rows, key=lambda r: r["Datum"])


def get_transactions_to_add_to_ynab(transactions, ynab_transactions):
    return [transaction for transaction in transactions if
            not is_in_ynab(transaction, ynab_transactions)]


def is_in_ynab(transaction, ynab_transactions):
    for ynab_transaction in ynab_transactions:
        same_date = datetime.strptime(transaction["Datum"], "%Y-%m-%d") == datetime.strptime(
            ynab_transaction["date"], "%Y-%m-%d")
        same_value = -1 * float(transaction["Belopp"]) == float(ynab_transaction["amount"]) / 1000
        transaction_payee = unicode(transaction["Specifikation"], encoding='UTF-8')
        same_name = transaction_payee == ynab_transaction["payee_name"] and \
                    not ynab_transaction["payee_name"].startswith(u"Transfer")
        if (same_date and same_value and same_name):
            return True
    return False


if __name__ == "__main__":
    ynab_token = sys.argv[1]
    client = YnabClient(ynab_token)

    print "Reading transactions from CSV"
    transactions = get_transactions_from_file()

    budget_id = client.get_budgets_ids()[1]
    earliest_date = datetime.strptime(transactions[0]["Datum"], "%Y-%m-%d") - timedelta(days=1)

    print "Getting transactions from YNAB"
    ynab_transactions = client.get_transactions(budget_id, since_date=earliest_date)
    ynab_transactions = filter(lambda x: x["account_name"] == "Eurobonus", ynab_transactions)

    print "Creating new transactions in Ynab"
    new_transactions = get_transactions_to_add_to_ynab(transactions, ynab_transactions)
    client.add_transactions(budget_id, ynab_transactions[0]["account_id"], new_transactions)

    print "Created %s transactions to YNAB" % len(new_transactions)
