# -*- coding: utf-8 -*-
from prometheus_client import Histogram, Counter
from telegram.ext import Updater, CommandHandler
import logging
import re
import telegram
from datetime import datetime, timedelta
from expiringdict import ExpiringDict

from .exc import RatingBotError
from .data_types import TournamentStatus


log = logging.getLogger(__name__)
hist_update = Histogram('rating_bot_update_batch_seconds',
                        'Time spent updating ratings',
                        buckets=(1, 2, 4, 8, 16, 32, 64, float("inf")))
counter_ping = Counter('rating_bot_pings', 'Ping messages received')


class Bot:
    INT_ARG_RE = re.compile(r'/\S+\s+(\d+)')
    MY_CHAT_ID = 141728270

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
            CommandHandler('follow_city', self.handle_follow_city))
        self._updater.dispatcher.add_handler(
            CommandHandler('unfollow_city', self.handle_unfollow_city))
        self._updater.dispatcher.add_handler(
            CommandHandler('subscriptions', self.handle_subscriptions))
        self._updater.dispatcher.add_handler(
            CommandHandler('update', self.handle_update))
        self._db = db
        self._rating_client = rating_client
        self._min_rating_diff = min_rating_diff
        self._interval_minutes = interval_minutes
        self._city_tournaments = {}
        self._cache = ExpiringDict(max_len=100, max_age_seconds=5*60)
        self._last_rating_update = ExpiringDict(max_len=100, max_age_seconds=24*60*60)

    def run(self):
        log.info('Starting the telegram bot')
        interval_seconds = self._interval_minutes * 60
        log.info('Scheduling an update every %d seconds' % interval_seconds)
        first_delta = timedelta(minutes = self._interval_minutes + 1 - datetime.today().minute%self._interval_minutes)
        log.info('delta ' + str(first_delta))
        self._updater.job_queue.run_once(self._startup_job, when=1)
        self._updater.job_queue.run_repeating(self._update_job, interval=self._interval_minutes * 60, first=first_delta)
        self._updater.start_polling()
        self._updater.idle()

    def handle_help(self, bot, update):
        update.message.reply_text(
            'Бот следит за рейтингом на rating.chgk.info.\n' +
            'Доступные команды: /follow, /unfollow, /subscriptions, /update, /ping, /follow_city, /unfollow_city\n' +
            'Исходники: github.com/iley/rating-bot')

    def handle_ping(self, bot, update):
        counter_ping.inc()
        update.message.reply_text('PONG')

    def handle_follow_city(self, bot, update):
        chat_id = update.message.chat.id
        msg_text = update.message.text
        log.info('Received follow message: "%s"', msg_text)
        match = self.INT_ARG_RE.match(msg_text)
        if not match:
            update.message.reply_text('Неверный формат сообщения. Должно быть: /follow_city CITY_ID')
            return
        city_id = int(match.group(1))
        try:
            city_name = self._rating_client.fetch_tournaments_for_city(city_id)[0]
            self._db.add_city_subscription(chat_id, city_id, city_name)
            update.message.reply_text('Вы подписались на синхроны города %s (%d)' %
                                      (city_name, city_id))
        except RatingBotError as ex:
            update.message.reply_text('Ошибка: %s' % ex)

    def handle_unfollow_city(self, bot, update):
        chat_id = update.message.chat.id
        msg_text = update.message.text
        log.info('Received unfollow message: "%s"', msg_text)
        match = self.INT_ARG_RE.match(msg_text)
        if not match:
            update.message.reply_text('Неверный формат сообщения. Должно быть: /unfollow_city CITY_ID')
            return
        city_id = int(match.group(1))
        try:
            self._db.remove_city_subscription(chat_id, city_id)
            update.message.reply_text('Вы отменили подписку на город #%d' % city_id)
        except RatingBotError as ex:
            update.message.reply_text('Ошбика: %s' % ex)

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
        self._update_cities(bot, chat_id=chat_id, force_update = True)

        msg = self._check_tournaments(chat_id, force_update = True)
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
            if old_rating.release > new_rating.release:
              new_rating = old_rating;
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

    def _check_city(self, city_id, force_update = False):
        city_tournaments = self._rating_client.fetch_tournaments_for_city(city_id)
        msgs = []
        if (not city_id in self._city_tournaments):
            self._city_tournaments[city_id] = city_tournaments[1]
            if not force_update:
                return msgs

        for tournament_id, sync_apps in city_tournaments[1].items():
            if (not force_update and tournament_id in self._city_tournaments[city_id] and len(sync_apps) <= len(self._city_tournaments[city_id][tournament_id])):
                continue
            msg = ''
            if len(msgs) == 0:
                msg = '%s:\n' % city_tournaments[0]
            msg += sync_apps[0]._tournament_name + '\n'
            for sync_app in sync_apps:
                msg += '%s: Ведущий %s, представитель %s\n' % (sync_app._time, sync_app._leader_name, sync_app._delegate_name)
            msgs.append(msg)
        self._city_tournaments[city_id] = city_tournaments[1]
        return msgs

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
                if tournament_info.time_delta > timedelta(days=10):
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

    def _startup_job(self, bot, job):
        log.info('_startup_job')
        chat_ids = self._db.get_chat_ids()
        for chat_id in chat_ids:
            #log.info('chat_id ' + str(chat_id))
            if chat_id == self.MY_CHAT_ID:
                try:
                    bot.send_message(chat_id=chat_id, text='Preved')
                except:
                    log.error('%s is blocked' % chat_id)

    def _update_cities(self, bot, chat_id, force_update = False):
        cities = self._db.get_city_subscriptions(chat_id)
        for city in cities:
            log.info('city ' + str(city))
            if not city in self._cache or force_update:
                self._cache[city] = self._check_city(city, force_update);
            for msg in self._cache[city]:
                bot.send_message(chat_id=chat_id, text=msg)

    @hist_update.time()
    def _update_job(self, bot, job):
        chat_ids = self._db.get_chat_ids()
        log.info('Using %d chats' % len(chat_ids))
        for chat_id in chat_ids:
            try:
                self._update_cities(bot, chat_id=chat_id)

                msg = self._check_tournaments(chat_id)
                if msg:
                    bot.send_message(chat_id=chat_id, text=msg)

                if chat_id in self._last_rating_update:
                    continue
                changed, ratings = self._update(chat_id)
                if changed:
                    log.info('Rating changed, sending a notification')
                    self._send_update(bot, chat_id, ratings)
                    self._last_rating_update[chat_id] = chat_id
                else:
                    log.info('Rating not changed')
            except:
                #TODO remove chat_id from db in case it's blocked
                log.error('error')

    def _differs_significantly(self, old, new):
        if abs(new.value - old.value) > self._min_rating_diff:
            return True
        if old.release is not None and new.release != old.release:
            return True
        return False
