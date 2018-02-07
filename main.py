#!/usr/bin/env python
import argparse
import logging

from bot import Bot
from db import Database


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Chgk Rating Telegram bot')
    parser.add_argument('--token', type=str, required=True, help='Telegram API token')
    parser.add_argument('--db', type=str, default='rating.db', help='Telegram API token')
    args = parser.parse_args()

    database = Database(args.db)
    bot = Bot(args.token, database)
    bot.run()


if __name__ == '__main__':
    main()
