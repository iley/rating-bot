# -*- coding: utf-8 -*-
import telegram
from telegram.ext import Updater, CommandHandler
import logging
import re
from exc import RatingBotError
from model import rating_diff


log = logging.getLogger(__name__)


class Bot:
    INT_ARG_RE = re.compile(r'/\w+\s+(\d+)')

    def __init__(self, token, db, rating):
        self._updater = Updater(token)
        self._updater.dispatcher.add_handler(CommandHandler('ping', self.ping))
        self._updater.dispatcher.add_handler(CommandHandler('follow', self.follow))
        self._updater.dispatcher.add_handler(CommandHandler('unfollow', self.unfollow))
        self._updater.dispatcher.add_handler(CommandHandler('subscriptions', self.subscriptions))
        self._updater.dispatcher.add_handler(CommandHandler('update', self.handle_update))
        self._db = db
        self._rating = rating

    def run(self):
        log.info('Starting the telegram bot')
        self._updater.start_polling()
        self._updater.idle()

    def ping(self, bot, update):
        update.message.reply_text('PONG')

    def follow(self, bot, update):
        chat_id = update.message.chat.id
        msg_text = update.message.text
        log.info('Received follow message: "%s"', msg_text)
        match = self.INT_ARG_RE.match(msg_text)
        if not match:
            update.message.reply_text('Неверный формат сообщения. Должно быть: /follow TEAM_ID')
            return
        team_id = int(match.group(1))
        try:
            team_info = self._rating.team_info(team_id)
            team_name = team_info['name']
            self._db.add_subscription(chat_id, team_id, team_name)
            update.message.reply_text('Вы подписались на обновления команды %s (%d)' %
                                      (team_name, team_id))
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

    def unfollow(self, bot, update):
        chat_id = update.message.chat.id
        msg_text = update.message.text
        log.info('Received unfollow message: "%s"', msg_text)
        match = self.INT_ARG_RE.match(msg_text)
        if not match:
            update.message.reply_text('Неверный формат сообщения. Должно быть: /unfollow TEAM_ID')
            return
        team_id = int(match.group(1))
        try:
            self._db.remove_subscription(chat_id, team_id)
            update.message.reply_text('Вы отменили подписку на команду #%d' % team_id)
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

    def subscriptions(self, bot, update):
        chat_id = update.message.chat.id
        teams = self._db.get_subscriptions(chat_id)
        if not teams:
            update.message.reply_text('Нет подписок')
        elif len(teams) == 1:
            update.message.reply_text('Вы подписаны на обновления команды %s' % str(teams[0]))
        else:
            team_list = '\n'.join(str(team) for team in teams)
            update.message.reply_text('Вы подписаны на обновления команд:\n%s' %
                                      team_list)

    def handle_update(self, bot, update):
        chat_id = update.message.chat.id
        try:
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
            rating_lines = []
            for team, old_rating, new_rating in self._update(chat_id):
                rating_lines.append('%s: %s' % (team.name, rating_diff(old_rating, new_rating)))
            update.message.reply_text('Рейтинг обновлён:\n%s' % '\n'.join(rating_lines))
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

    def _update(self, chat_id):
        teams = self._db.get_subscriptions(chat_id)
        ratings = []
        if not teams:
            raise RatingBotError('Нет подписок')
        for team in teams:
            new_rating = self._rating.get_rating(team.id)
            old_rating = self._db.get_saved_reating(team.id)
            if old_rating != new_rating:
                self._db.update_rating(team.id, new_rating)
            ratings.append((team, old_rating, new_rating))
        return ratings
