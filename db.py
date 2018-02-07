import sqlite3
import os.path
import logging


log = logging.getLogger(__name__)


SCHEMA = '''
CREATE TABLE rating (
    team_id integer,
    release_id integer,
    rating_value real,
    rating_position real,
    date text,
    formula text,
    primary key(team_id, release_id)
);
'''


class Database:
    def __init__(self, path):
        new_file = False
        if os.path.isfile(path):
            new_file = True
        self.conn = sqlite3.connect(path)
        if new_file:
            log.info('Initializing database %s' % path)
            self.create_schema()

    def create_schema(self):
        self.conn.executescript(SCHEMA)
