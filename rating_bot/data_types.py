from datetime import timedelta
from enum import IntEnum

class Team:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        return '%s (#%d)' % (self.name, self.id)

class TournamentStatus(IntEnum):
    NOT_STARTED = 1
    RUNNING = 2
    RESULTS_OPEN = 3
    CONTROVERSIALS_DONE = 4
    APPEALS_DONE = 5
    LONG_GONE = 6
    def __str__(self):
        options = {1: 'Турнир не начался',
                   2: 'Турнир идёт',
                   3: 'Результаты доступны',
                   4: 'Спорные рассмотрены',
                   5: 'Апелляции рассмотрены',
                   6: 'Давно кончился'}
        return options[self.value]
    def isImportant(self):
        return self.value in [TournamentStatus.RESULTS_OPEN, TournamentStatus.CONTROVERSIALS_DONE, TournamentStatus.APPEALS_DONE]

class TournamentInfo:
    def __init__(self):
        self.name = ''
        self.status = TournamentStatus.NOT_STARTED
        self.type = ''
        self.time_delta = timedelta(0)

    def isOchnik(self):
        return self.type == 'Обычный'

class SyncApplications:
    def __init__(self):
        self._tournament_id = -1
        self._tournament_name = ''
        self._delegate_name = ''
        self._leader_name = ''
        self._time = ''

class Rating:
    def __init__(self, value, position, value_diff=None, position_diff=None, release=None):
        self.value = value or 0
        self.position = position or 0
        self.value_diff = value_diff
        self.position_diff = position_diff
        self.release = release or 0

    def __str__(self):
        value_str = str(self.value)
        if self.value_diff:
            sign = '+' if self.value_diff > 0 else ''
            value_str += ' (%s%d)' % (sign, self.value_diff)

        position_str = format_float(self.position)
        if self.position_diff:
            sign = '▲' if self.position_diff > 0 else '▼'
            position_str += ' (%s%s)' % (sign, format_float(abs(self.position_diff)))
        return '%s, место %s' % (value_str, position_str)

    def __eq__(self, other):
        if not isinstance(other, Rating):
            return False
        return (self.value, self.position) == (other.value, other.position)

    def __sub__(self, other):
        return Rating(self.value,
                      self.position,
                      self.value - other.value,
                      other.position - self.position,
                      self.release)

    @classmethod
    def fromJSON(self, json):
        return Rating(value=int(json['rating']),
                      position=float(json['rating_position']),
                      value_diff=0,
                      position_diff=0,
                      release=int(json['idrelease']))


def format_float(x):
    return ('%f' % x).rstrip('0').rstrip('.')
