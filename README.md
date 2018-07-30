## Purpose

Simple script to create transactions in YNAB from a SEB SAS Eurobonus credit card statement

## Usage

Export the .xls on the SAS Eurobonus website
In Excel, save the file as `CSV UTF-8`

* Install the dependencies using `pip install -r requirements.txt`
* Call export_to_ynab.py  with your ynab_token followed by the path of csv file path


`python export_to_ynab.py <Ynab Access Token Here> <File Path Here>`
