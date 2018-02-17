# -*- coding: utf-8 -*-
import telegram
from telegram.ext import Updater, CommandHandler
import logging
import re
from .exc import RatingBotError


log = logging.getLogger(__name__)

UPDATE_SECONDS = 15 * 60


class Bot:
    INT_ARG_RE = re.compile(r'/\S+\s+(\d+)')

    def __init__(self, token, db, rating):
        self._updater = Updater(token)
        self._updater.dispatcher.add_handler(
            CommandHandler('start', self.handle_help))
        self._updater.dispatcher.add_handler(
            CommandHandler('help', self.handle_help))
        self._updater.dispatcher.add_handler(
            CommandHandler('ping', self.handle_ping))
        self._updater.dispatcher.add_handler(
            CommandHandler('follow', self.handle_follow))
        self._updater.dispatcher.add_handler(
            CommandHandler('unfollow', self.handle_unfollow))
        self._updater.dispatcher.add_handler(
            CommandHandler('subscriptions', self.handle_subscriptions))
        self._updater.dispatcher.add_handler(
            CommandHandler('update', self.handle_update))
        self._db = db
        self._rating = rating

    def run(self):
        log.info('Starting the telegram bot')
        self._updater.job_queue.run_repeating(self._update_job, UPDATE_SECONDS)
        self._updater.start_polling()
        self._updater.idle()

    def handle_help(self, bot, update):
        update.message.reply_text('Доступные команды: ' +
                                  '/follow, /unfollow, /subscriptions, /update, /ping')

    def handle_ping(self, bot, update):
        update.message.reply_text('PONG')

    def handle_follow(self, bot, update):
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
            update.message.reply_text('Вы подписались на обновления рейтинга команды %s (%d)' %
                                      (team_name, team_id))
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

    def handle_unfollow(self, bot, update):
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

    def handle_subscriptions(self, bot, update):
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
            _, ratings = self._update(chat_id)
            self._send_update(bot, chat_id, ratings)
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

    def _update(self, chat_id):
        log.info('Updating rating for chat %d' % chat_id)
        teams = self._db.get_subscriptions(chat_id)
        ratings = []
        changed = False
        if not teams:
            raise RatingBotError('Нет подписок')
        for team in teams:
            new_rating = self._rating.get_rating(team.id)
            old_rating = self._db.get_saved_reating(chat_id, team.id)
            if old_rating != new_rating:
                self._db.update_rating(chat_id, team.id, new_rating)
                changed = True
            ratings.append((team, new_rating - old_rating))
        return changed, ratings

    def _send_update(self, bot, chat_id, ratings):
        rating_lines = []
        for team, rating in sorted(ratings, key=lambda r: r[1].value, reverse=True):
            rating_lines.append('%s: %s' % (team.name, rating))
        bot.send_message(chat_id=chat_id, text=('Рейтинг обновлён:\n%s' % '\n'.join(rating_lines)))

    def _update_job(self, bot, job):
        chat_ids = self._db.get_chat_ids()
        for chat_id in chat_ids:
            changed, ratings = self._update(chat_id)
            if changed:
                self._send_update(bot, chat_id, ratings)
