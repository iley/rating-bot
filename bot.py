#!/usr/bin/env python
import argparse
from telegram.ext import Updater, CommandHandler


def main():
    parser = argparse.ArgumentParser(description='Chgk Rating Telegram bot')
    parser.add_argument('--token', type=str, required=True, help='Telegram API token')
    args = parser.parse_args()
    run_bot(args.token)


def run_bot(token):
    updater = Updater(token)
    updater.dispatcher.add_handler(CommandHandler('ping', ping))
    updater.dispatcher.add_handler(CommandHandler('watch', watch))
    updater.start_polling()
    updater.idle()


def ping(bot, update):
    update.message.reply_text('PONG')


def watch(bot, update):
    update.message.reply_text('NOT IMPLEMENTED')


if __name__ == '__main__':
    main()
