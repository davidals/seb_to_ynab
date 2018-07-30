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

    def add_transactions(self, budget_id, account_id, card_txs):
        transactions_payload = []
        for tx in card_txs:
            transactions_payload.append({
                "account_id": account_id,
                "date": tx["Datum"],
                "amount": int(float(tx["Belopp"]) * -1 * 1000),  # *-1 since it's an expense, *1000 to put in correct unit
                "payee_id": None,
                "payee_name": None,
                "category_id": None,
                "memo": tx["Specifikation"],
                "cleared": "cleared" if tx["Bokfört"] != "Reserverat" else "uncleared",
                "approved": False,
                "flag_color": None,
                "import_id": None
            })
        payload = {"transactions": transactions_payload}
        url = url = self.ynab_base_url + "budgets/%s/transactions/bulk" % budget_id
        r = requests.post(url, json=payload, headers=self.headers)
        return r.json()


def read_and_clean_file():
    tx_rows = []
    header = ""

    rows = []
    with open(sys.argv[2], 'rU') as csvFile:
        csvreader = csv.reader(csvFile, delimiter=';', dialect=csv.excel_tab)
        rows = [r for r in csvreader]

    for row in rows:
        if "Datum" in row:
            header = row
        try:
            datetime.strptime(row[0], '%m-%d')
            tx_rows.append(row)
        except ValueError:
            # Not a date, so ignore row
            continue

    yield "\t".join(header)
    for row in tx_rows:
        row[0] = '%s-%s' % (datetime.now().year, row[0])
        row[6] = row[6].replace(',','.').replace('\xc2\xa0', '') # First replace to dots then replace the unicode space chars
        yield "\t".join(row)


def get_txs_from_file():
    tx_rows = []
    csvreader = csv.DictReader(read_and_clean_file(), delimiter="\t", dialect=csv.excel_tab)
    for row in csvreader:
        tx_rows.append(row)
    return sorted(tx_rows, key=lambda r : r["Datum"])


def get_transactions_to_add_to_ynab(txs, ynab_txs):
    return [tx for tx in txs if not is_in_ynab(tx, ynab_txs)]

    
def is_in_ynab(tx, ynab_txs):
    for ynab_tx in ynab_txs:        
        same_date = datetime.strptime(tx["Datum"], "%Y-%m-%d") == datetime.strptime(ynab_tx["date"], "%Y-%m-%d")
        same_value = -1 * float(tx["Belopp"]) == float(ynab_tx["amount"])/1000
        if (same_date and same_value):
            return True
    return False 


if __name__ == "__main__":
    ynab_token = sys.argv[1]
    client = YnabClient(ynab_token)

    print "Reading transactions from CSV"
    txs = get_txs_from_file()

    budget_id = client.get_budgets_ids()[1]
    earliest_date = datetime.strptime(txs[0]["Datum"], "%Y-%m-%d") - timedelta(days=1)

    print "Getting transactions from YNAB"
    ynab_txs = client.get_transactions(budget_id, since_date=earliest_date)
    ynab_txs = filter(lambda x: x["account_name"] == "Eurobonus", ynab_txs)

    print "Creating new transactions in Ynab"
    new_txs = get_transactions_to_add_to_ynab(txs, ynab_txs)
    client.add_transactions(budget_id, ynab_txs[0]["account_id"], new_txs)

    print "Created %s transactions to YNAB" % len(new_txs)

