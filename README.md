# CHGK rating bot for Telegram

## Development

1. Create a virtualenv using Python 3
```bash
python3 -m venv ~/venv
source ~/venv/bin/activate
```

2. Install dependencies
```bash
pip3 install -r requirements.txt
```

3. Register a Telegram bot for testing using [BotFather](https://telegram.me/botfather).
See [Creating a new bot](https://core.telegram.org/bots#creating-a-new-bot) section in the Telegram documentation.
Make note of the API token.

4. Run the bot locally
```bash
python3 -m rating_bot -v --token YOUR-TOKEN-HERE
```
