# -*- coding: utf-8 -*-
import telegram
from telegram.ext import Updater, CommandHandler
import logging
import re
from .exc import RatingBotError


log = logging.getLogger(__name__)


class Bot:
    INT_ARG_RE = re.compile(r'/\S+\s+(\d+)')

    def __init__(self, token, db, rating_client, min_rating_diff, interval_minutes):
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
        self._rating_client = rating_client
        self._min_rating_diff = min_rating_diff
        self._interval_minutes = interval_minutes

    def run(self):
        log.info('Starting the telegram bot')
        interval_seconds = self._interval_minutes * 60
        log.info('Scheduling an update every %d seconds' % interval_seconds)
        self._updater.job_queue.run_repeating(self._update_job, self._interval_minutes * 60)
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
        bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
        try:
            team_info = self._rating_client.team_info(team_id)
            team_name = team_info['name']
            self._db.add_subscription(chat_id, team_id, team_name)
            update.message.reply_text('Вы подписались на обновления рейтинга команды %s (%d)' %
                                      (team_name, team_id))
            _, ratings = self._update(chat_id, force=True)
            self._send_update(bot, chat_id, ratings)
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
            _, ratings = self._update(chat_id, force=True)
            self._send_update(bot, chat_id, ratings)
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

    def _update(self, chat_id, force=False):
        log.info('Updating rating for chat %d' % chat_id)
        teams = self._db.get_subscriptions(chat_id)
        ratings = []
        changed = force
        if not teams:
            raise RatingBotError('Нет подписок')
        for team in teams:
            old_rating = self._db.get_saved_rating(chat_id, team.id)
            new_rating = self._rating_client.get_rating(team.id)
            if self._differs_significantly(old_rating, new_rating):
                changed = True
            ratings.append((team, new_rating - old_rating))
        if changed:
            for team, rating in ratings:
                self._db.update_rating(chat_id, team.id, rating)
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
                log.info('Rating changed, sending a notification')
                self._send_update(bot, chat_id, ratings)
            else:
                log.info('Rating not changed')

    def _differs_significantly(self, old, new):
        if abs(new.value - old.value) > self._min_rating_diff:
            return True
        if old.release is not None and new.release != old.release:
            return True
        return False
