README File regarding channel_to_csv.py

How to Use: First Steps
1. download packages from requirements.txt (recommended: in virtualenv)
    pip install -r requirements.txt
2. fill out config.ini file with credentials for the Telegram API

When running the script
1. Login with the same account as set in config.ini
2. Enter code send to your account
3. You will be asked which channel to scrape (Enter "" for laut_gedacht)
4. Decide wether or not to download files; specify path or default (default = '/downloads/')
5. When not all messages are fetched, change int-variable 'r' in line 196
