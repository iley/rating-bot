# -*- coding: utf-8 -*-
import sqlite3
import os.path
import logging
from prometheus_client import Gauge

from .exc import RatingBotError
from .data_types import Team, Rating


log = logging.getLogger(__name__)
gauge_subscriptions = Gauge('rating_bot_subscriptions', 'Total number of subscriptions')
gauge_chats = Gauge('rating_bot_chats', 'Number of chats which have subscriptions')


SCHEMA = '''
CREATE TABLE IF NOT EXISTS subscriptions (
    chat_id INTEGER,
    team_id INTEGER,
    team_name TEXT,
    rating REAL,
    position REAL,
    release INTEGER,
    PRIMARY KEY(chat_id, team_id)
);

CREATE TABLE IF NOT EXISTS city_subscriptions (
    chat_id INTEGER,
    city_id INTEGER,
    city_name  TEXT,
    PRIMARY KEY(chat_id, city_id)
);

CREATE TABLE IF NOT EXISTS tournaments (
    chat_id INTEGER,
    tournament_id INTEGER,
    status INTEGER,
    PRIMARY KEY(chat_id, tournament_id)
);
'''


class Database:
    def __init__(self, path):
        self._path = path
        new_file = not os.path.isfile(path)
        log.info('Initializing database %s' % path)
        self.create_schema()
        gauge_subscriptions.set_function(self.get_total_subscriptions)

    def _connect(self):
        return sqlite3.connect(self._path)

    def create_schema(self):
        conn = self._connect()
        with conn:
            conn.executescript(SCHEMA)

    def get_tournament_status(self, chat_id, tournament_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT status FROM tournaments '+
                      'WHERE chat_id=? AND tournament_id=?',
                      (chat_id, tournament_id))
            row = c.fetchone()
            if not row:
                return None
            return row[0]

    def add_tournament_status(self, chat_id, tournament_id, status):
        try:
            conn = self._connect()
            with conn:
                conn.execute('INSERT INTO tournaments ' +
                             '(chat_id, tournament_id, status) ' +
                             'VALUES (?, ?, ?) ',
                             (chat_id, tournament_id, int(status)))
        except Exception as ex:
            log.exception(ex)

    def update_tournament_status(self, chat_id, tournament_id, status):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('UPDATE tournaments SET status=? '+
                      'WHERE chat_id=? AND tournament_id=?',
                      (int(status), chat_id, tournament_id))

    def add_city_subscription(self, chat_id, city_id, city_name):
        try:
            conn = self._connect()
            with conn:
                conn.execute('INSERT INTO city_subscriptions ' +
                             '(chat_id, city_id, city_name) ' +
                             'VALUES (?, ?, ?)',
                             (chat_id, city_id, city_name))
        except sqlite3.IntegrityError as ex:
            raise RatingBotError('Вы уже подписаны на синхроны города %s (%d)' %
                                 (city_name, city_id)) from ex

    def remove_city_subscription(self, chat_id, city_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('DELETE FROM city_subscriptions WHERE chat_id=? AND city_id=?',
                      (chat_id, city_id))
            c.execute('SELECT changes()')
            if c.fetchone()[0] == 0:
                raise RatingBotError('Вы не подписаны на обновления города #%d' % team_id)

    def add_subscription(self, chat_id, team_id, team_name):
        try:
            conn = self._connect()
            with conn:
                conn.execute('INSERT INTO subscriptions ' +
                             '(chat_id, team_id, team_name, rating, position) ' +
                             'VALUES (?, ?, ?, 0, 0)',
                             (chat_id, team_id, team_name))
        except sqlite3.IntegrityError as ex:
            raise RatingBotError('Вы уже подписаны на обновления команды %s (%d)' %
                                 (team_name, team_id)) from ex

    def remove_subscription(self, chat_id, team_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('DELETE FROM subscriptions WHERE chat_id=? AND team_ID=?',
                      (chat_id, team_id))
            c.execute('SELECT changes()')
            if c.fetchone()[0] == 0:
                raise RatingBotError('Вы не подписаны на обновления команды #%d' % team_id)

    def get_subscriptions(self, chat_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT team_id, team_name FROM subscriptions ' +
                      'WHERE chat_id=?', (chat_id,))
            rows = c.fetchall()
        return [Team(*row) for row in rows]

    def get_city_subscriptions(self, chat_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT city_id FROM city_subscriptions ' +
                      'WHERE chat_id=?', (chat_id,))
            rows = c.fetchall()
        return [row[0] for row in rows]

    def get_saved_rating(self, chat_id, team_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT rating, position, release FROM subscriptions '+
                      'WHERE chat_id=? AND team_id=?',
                      (chat_id, team_id))
            row = c.fetchone()
            if not row:
                return None
            return Rating(value=row[0],
                          position=row[1],
                          release=row[2])

    def update_rating(self, chat_id, team_id, rating):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('UPDATE subscriptions SET rating=?, position=?, release=? '+
                      'WHERE chat_id=? AND team_id=?',
                      (rating.value, rating.position, rating.release, chat_id, team_id))

    def get_chat_ids(self):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT DISTINCT chat_id FROM subscriptions')
            rows = c.fetchall()
        res = [r[0] for r in rows]
        gauge_chats.set(len(res))
        return res

    def get_total_subscriptions(self):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT count(*) FROM subscriptions ')
            row = c.fetchone()
        return row[0]
