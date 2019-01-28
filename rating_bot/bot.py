# -*- coding: utf-8 -*-
from prometheus_client import Histogram, Counter
from telegram.ext import Updater, CommandHandler
import logging
import re
import telegram
from datetime import datetime, timedelta

from .exc import RatingBotError
from .data_types import TournamentStatus


log = logging.getLogger(__name__)
hist_update = Histogram('rating_bot_update_batch_seconds',
                        'Time spent updating ratings',
                        buckets=(1, 2, 4, 8, 16, 32, 64, float("inf")))
counter_ping = Counter('rating_bot_pings', 'Ping messages received')


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
        self._city_tournaments = {}

    def run(self):
        log.info('Starting the telegram bot')
        interval_seconds = self._interval_minutes * 60
        log.info('Scheduling an update every %d seconds' % interval_seconds)
        first_delta = timedelta(minutes = 61 - datetime.today().minute)
        log.info('delta ' + str(first_delta))
        self._updater.job_queue.run_repeating(self._update_job, interval=self._interval_minutes * 60, first=first_delta)
        self._updater.start_polling()
        self._updater.idle()


    def handle_help(self, bot, update):
        update.message.reply_text('Доступные команды: ' +
                                  '/follow, /unfollow, /subscriptions, /update, /ping')

    def handle_ping(self, bot, update):
        counter_ping.inc()
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
        log.info('!!!!!!!!!!!!!!!!!!')
        msg = self._check_city(chat_id, 205, force_update = True)
        if msg:
            bot.send_message(chat_id=chat_id, text=msg)

        msg = self._check_city(chat_id, 31, force_update = True)
        if msg:
            bot.send_message(chat_id=chat_id, text=msg)

        msg = self._check_tournaments(chat_id, force_update = False)
        if msg:
            bot.send_message(chat_id=chat_id, text=msg)
        try:
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
            _, ratings = self._update(chat_id, force=True)
            self._send_update(bot, chat_id, ratings)
        except RatingBotError as ex:
            update.message.reply_text('Ошибка: %s' % ex)

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
            # Workaround for an API glitch.
            if new_rating.value == 0:
                new_rating.value = old_rating.value
            if new_rating.position == 0:
                new_rating.position = old_rating.position
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

    def _check_city(self, chat_id, city_id, force_update = False):
        city_tournaments = self._rating_client.fetch_tournaments_for_city(city_id)
        msg = ''
        if (not chat_id in self._city_tournaments):
            self._city_tournaments[chat_id] = {}
        if (not city_id in self._city_tournaments[chat_id]):
            self._city_tournaments[chat_id][city_id] = city_tournaments
            if not force_update:
                return msg

        if (force_update or len(city_tournaments[1]) > len(self._city_tournaments[chat_id][city_id][1])):
            msg = '%s:\n' % city_tournaments[0]
            for info in city_tournaments[1]:
                msg += '%s %s: Ведущий %s, представитель %s\n' % info[1:5]
                msg += 'Редакторы: ' + ', '.join(info[5:]) + '\n\n'
        self._city_tournaments[chat_id][city_id] = city_tournaments
        return msg

    def _check_tournaments(self, chat_id, force_update = False):
        log.info('111111111111111 ')
        teams = self._db.get_subscriptions(chat_id);
        if not teams:
            return '';
        msg = ''
        for team in teams:
            tournaments = self._rating_client.fetch_tournaments(team.id)
            for tournament_id in tournaments:
                saved_status = self._db.get_tournament_status(chat_id, int(tournament_id))
                if saved_status == TournamentStatus.LONG_GONE and not force_update:
                    continue
                tournament_info = self._rating_client.fetch_tournament(int(tournament_id))
                if tournament_info.time_delta > timedelta(days=21):
                    if not saved_status or (saved_status >= TournamentStatus.RESULTS_OPEN and tournament_info.isOchnik()) or (saved_status >= TournamentStatus.APPEALS_DONE and not tournament_info.isOchnik()):
                        tournament_info.status = TournamentStatus.LONG_GONE

                if not saved_status:
                    self._db.add_tournament_status(chat_id, int(tournament_id), tournament_info.status)
                elif saved_status < tournament_info.status:
                    self._db.update_tournament_status(chat_id, int(tournament_id), tournament_info.status)
                elif saved_status >= tournament_info.status and not force_update:
                    continue
                if tournament_info.status.isImportant() or force_update:
                    msg += ('%s: %s (%s)\n' % (tournament_info.name, tournament_info.status, self._rating_client.status_url(int(tournament_id), tournament_info.status)))
        return msg

    @hist_update.time()
    def _update_job(self, bot, job):
        chat_ids = self._db.get_chat_ids()
        log.info('Using %d chats' % len(chat_ids))
        for chat_id in chat_ids:
            log.info('!!!!!!!!!!!!!!!!!!')
            msg = self._check_city(chat_id, 205)
            if msg:
                bot.send_message(chat_id=chat_id, text=msg)

            msg = self._check_city(chat_id, 31)
            if msg:
                bot.send_message(chat_id=chat_id, text=msg)

            msg = self._check_tournaments(chat_id)
            if msg:
                bot.send_message(chat_id=chat_id, text=msg)
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
