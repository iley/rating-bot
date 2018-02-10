#!/usr/bin/env python
import argparse
import logging

from bot import Bot
from db import Database
from rating import RatingClient


def main():
    parser = argparse.ArgumentParser(description='Chgk Rating Telegram bot')
    parser.add_argument('--token', type=str, required=True, help='Telegram API token')
    parser.add_argument('--db', type=str, default='rating.db', help='Telegram API token')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose > 0 else logging.INFO
    logging.basicConfig(level=loglevel)

    database = Database(args.db)
    rating = RatingClient()
    bot = Bot(args.token, database, rating)
    bot.run()


if __name__ == '__main__':
    main()
