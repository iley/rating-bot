# -*- coding: utf-8 -*-
import sqlite3
import os.path
import logging
from .exc import RatingBotError
from .data_types import Team, Rating


log = logging.getLogger(__name__)


SCHEMA = '''
CREATE TABLE subscriptions (
    chat_id INTEGER,
    team_id INTEGER,
    team_name TEXT,
    rating REAL,
    position REAL,
    PRIMARY KEY(chat_id, team_id)
);
'''


class Database:
    def __init__(self, path):
        self._path = path
        new_file = not os.path.isfile(path)
        if new_file:
            log.info('Initializing database %s' % path)
            self.create_schema()

    def _connect(self):
        return sqlite3.connect(self._path)

    def create_schema(self):
        conn = self._connect()
        with conn:
            conn.executescript(SCHEMA)

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
        try:
            conn = self._connect()
            with conn:
                conn.execute('DELETE FROM subscriptions WHERE chat_id=? AND team_ID=?',
                            (chat_id, team_id))
        except sqlite3.IntegrityError as ex:
            raise RatingBotError('Вы не подписаны на обновления команды %s (%d)' %
                                 (team_name, team_id)) from ex

    def get_subscriptions(self, chat_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT team_id, team_name FROM subscriptions WHERE chat_id=?', (chat_id,))
            rows = c.fetchall()
        return [Team(*row) for row in rows]

    def get_saved_reating(self, chat_id, team_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT rating, position FROM subscriptions WHERE chat_id=? AND team_id=?',
                      (chat_id, team_id))
            row = c.fetchone()
            if not row:
                return None
            return Rating(*row)

    def update_rating(self, chat_id, team_id, rating):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('UPDATE subscriptions SET rating=?, position=? WHERE chat_id=? AND team_id=?',
                      (rating.value, rating.position, chat_id, team_id))

    def get_chat_ids(self):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT DISTINCT chat_id FROM subscriptions')
            rows = c.fetchall()
        return [r[0] for r in rows]
