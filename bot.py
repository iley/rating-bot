from telegram.ext import Updater, CommandHandler
import logging
import re
from exc import RatingBotError


log = logging.getLogger(__name__)


class Bot:
    INT_ARG_RE = re.compile(r'/\w+\s+(\d+)')

    def __init__(self, token, db):
        self.updater = Updater(token)
        self.updater.dispatcher.add_handler(CommandHandler('start', self.start))
        self.updater.dispatcher.add_handler(CommandHandler('ping', self.ping))
        self.updater.dispatcher.add_handler(CommandHandler('follow', self.follow))
        self.updater.dispatcher.add_handler(CommandHandler('unfollow', self.unfollow))
        self.updater.dispatcher.add_handler(CommandHandler('subscriptions', self.subscriptions))
        self.db = db

    def run(self):
        log.info('Starting the telegram bot')
        self.updater.start_polling()
        self.updater.idle()

    def start(self, bot, update):
        update.message.reply_text('Welcome!')

    def ping(self, bot, update):
        update.message.reply_text('PONG')

    def follow(self, bot, update):
        chat_id = update.message.chat.id
        msg_text = update.message.text
        log.info('Received follow message: "%s"', msg_text)
        match = self.INT_ARG_RE.match(msg_text)
        if not match:
            update.message.reply_text('Usage: /follow TEAM_ID')
            return
        team_id = int(match.group(1))
        try:
            self.db.add_subscription(chat_id, team_id)
            update.message.reply_text('Subscribed to team %d' % team_id)
        except RatingBotError as ex:
            update.message.reply_text('Error: %s' % ex)

    def unfollow(self, bot, update):
        chat_id = update.message.chat.id
        msg_text = update.message.text
        log.info('Received unfollow message: "%s"', msg_text)
        match = self.INT_ARG_RE.match(msg_text)
        if not match:
            update.message.reply_text('Usage: /unfollow TEAM_ID')
            return
        team_id = int(match.group(1))
        try:
            self.db.remove_subscription(chat_id, team_id)
            update.message.reply_text('Unsubscribed from team %d' % team_id)
        except RatingBotError as ex:
            update.message.reply_text('Error: %s' % ex)

    def subscriptions(self, bot, update):
        chat_id = update.message.chat.id
        team_ids = self.db.get_subscriptions(chat_id)
        if not team_ids:
            update.message.reply_text('No subscriptions found')
        else:
            team_list = ', '.join(str(id) for id in team_ids)
            update.message.reply_text('Current subscriptions: %s' % team_list)
