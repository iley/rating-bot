import sqlite3
import os.path
import logging
from exc import RatingBotError


log = logging.getLogger(__name__)


SCHEMA = '''
CREATE TABLE rating (
    team_id INTEGER,
    release_id INTEGER,
    rating_value REAL,
    rating_position REAL,
    date TEXT,
    formula TEXT,
    PRIMARY KEY(team_id, release_id)
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
            raise RatingBotError('Subscription already exists') from ex

    def remove_subscription(self, chat_id, team_id):
        try:
            conn = self._connect()
            with conn:
                conn.execute('DELETE FROM subscriptions WHERE chat_id=? AND team_ID=?',
                            (chat_id, team_id))
        except sqlite3.IntegrityError as ex:
            raise RatingBotError('Subscription already exists') from ex

    def get_subscriptions(self, chat_id):
        conn = self._connect()
        with conn:
            c = conn.cursor()
            c.execute('SELECT team_id, team_name FROM subscriptions WHERE chat_id=?', (chat_id,))
            rows = c.fetchall()
        return [Team(*row) for row in rows]


class Team:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        return '%s (%d)' % (self.name, self.id)
