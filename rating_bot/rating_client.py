import requests
import logging
from expiringdict import ExpiringDict
from prometheus_client import Histogram
from datetime import datetime, timedelta
from enum import IntEnum

from .exc import RatingBotError
from .data_types import Rating

log = logging.getLogger(__name__)
hist_fetch_rating = Histogram('rating_bot_fetch_rating_seconds',
                              'Time spent fetching data from the Rating website',
                              buckets=(1, 2, 4, 8, 16, 32, 64, float("inf")))

class TournamentStatus(IntEnum):
    NOT_STARTED = 1
    RUNNING = 2
    RESULTS_OPEN = 3
    CONTROVERSIALS_DONE = 4
    APPEALS_DONE = 5
    def __str__(self):
        options = {1: 'Турнир не начался',
                   2: 'Турнир идёт',
                   3: 'Результаты доступны',
                   4: 'Спорные рассмотрены',
                   5: 'Апелляции рассмотрены'}
        return options[self.value]

class RatingClient:
    BASE_URL = 'http://rating.chgk.info'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    MOSCOW_TIMEZONE = ''

    def __init__(self):
        self._cache = ExpiringDict(max_len=100, max_age_seconds=5*60)

    def team_info(self, team_id):
        try:
            log.info('Fetching team info for %d' % team_id)
            r = requests.get('%s/api/teams/%d.json' % (self.BASE_URL, team_id))
            r.raise_for_status()
            return r.json()[0]
        except Exception as ex:
            log.exception(ex)
            raise RatingBotError('Команда #%d не найдена: %s' % (team_id, ex))

    def get_rating(self, team_id):
        if team_id in self._cache:
            log.info('Rating for %d cached' % team_id)
            return self._cache[team_id]
        try:
            return self._fetch_rating(team_id)

        except Exception as ex:
            log.exception(ex)
            raise RatingBotError('Команда #%d не найдена: %s' % (team_id, ex))

    @hist_fetch_rating.time()
    def _fetch_rating(self, team_id):
        log.info('Fetching rating for %d' % team_id)
        r = requests.get('%s/api/teams/%d/rating.json' % (self.BASE_URL, team_id))
        r.raise_for_status()

        records = r.json()
        if not records:
            raise RatingBotError('Рейтинг для команды #%d не найден' % team_id)
        last_record = max(records, key=lambda d: int(d['idrelease']))
        rating = Rating.fromJSON(last_record)
        self._cache[team_id] = rating
        return rating

    def fetch_tournament(self, tournament_id):
        try:
            log.info('Fetching tournament %d' % tournament_id)

            r = requests.get('%s/api/tournaments/%d.json' % (self.BASE_URL, tournament_id))
            r.raise_for_status()
            log.info('json %s' % r.json())
            tournament_json = r.json()[0]
            name = tournament_json['name']

            start_date = datetime.strptime(tournament_json['date_start'] + self.MOSCOW_TIMEZONE, self.DATE_FORMAT)
            end_date = datetime.strptime(tournament_json['date_end'] + self.MOSCOW_TIMEZONE, self.DATE_FORMAT)
            today_date = datetime.today() + timedelta(hours=2)
            status = TournamentStatus.NOT_STARTED
            if start_date < today_date and today_date < end_date:
                status = TournamentStatus.RUNNING

            r = requests.get('%s/api/tournaments/%d/list.json' % (self.BASE_URL, tournament_id))
            r.raise_for_status()
            results_json = r.json()[0]
            if 'mask' in results_json:
                status = TournamentStatus.RESULTS_OPEN

            if today_date > end_date + timedelta(days=1):
                r = requests.get('%s/tournament/%d/controversials' % (self.BASE_URL, tournament_id))
                if r.text.find('Поданные спорные ответы') != -1 and r.text.find('Новый') == -1:
                    status = TournamentStatus.CONTROVERSIALS_DONE

            if today_date > end_date + timedelta(days=5):
                r = requests.get('%s/tournament/%d/appeals' % (self.BASE_URL, tournament_id))
                r.raise_for_status()
                if r.text.find('Поданные апелляции') != -1 and r.text.find('Апелляция не рассмотрена') == -1:
                    status = TournamentStatus.APPEALS_DONE
            return name, status
        except Exception as ex:
            log.exception(ex)
            return '', None

    def fetch_tournaments(self, team_id):
        try:
            r = requests.get('%s/api/teams/%d/tournaments/last.json' % (self.BASE_URL, team_id))
            r.raise_for_status()
            return r.json()['tournaments']
        except Exception as ex:
            log.exception(ex)
            return []
