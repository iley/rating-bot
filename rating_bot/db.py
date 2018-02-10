# -*- coding: utf-8 -*-
import sqlite3
import os.path
import logging
from .exc import RatingBotError
from .model import Team, RatingRecord


log = logging.getLogger(__name__)


SCHEMA = '''
CREATE TABLE rating (
    team_id INTEGER,
    release_id INTEGER,
    rating_value REAL,
    rating_position REAL,
    PRIMARY KEY(team_id)
);

CREATE TABLE subscriptions (
    chat_id INTEGER,
    team_id INTEGER,
    team_name TEXT,
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
                conn.execute('INSERT INTO subscriptions (chat_id, team_id, team_name) VALUES (?, ?, ?)',
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

    def get_saved_reating(self, team_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT release_id, rating_value, rating_position FROM rating WHERE team_id=? ORDER BY release_id DESC LIMIT 1',
                      (team_id,))
            row = c.fetchone()
            if not row:
                return None
            return RatingRecord(*row)

    def update_rating(self, team_id, rating):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('DELETE FROM rating WHERE team_id=?', (team_id,))
            c.execute('INSERT INTO rating (team_id, release_id, rating_value, rating_position) VALUES (?, ?, ?, ?)',
                      (team_id, rating.release, rating.value, rating.position))

    def get_chat_ids(self):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT DISTINCT chat_id FROM subscriptions')
            rows = c.fetchall()
        return [r[0] for r in rows]
