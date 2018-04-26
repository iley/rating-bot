import requests
import logging
from expiringdict import ExpiringDict
from prometheus_client import Histogram

from .exc import RatingBotError
from .data_types import Rating


log = logging.getLogger(__name__)
hist_fetch_rating = Histogram('rating_bot_fetch_rating_seconds',
                              'Time spent fetching data from the Rating website',
                              buckets=(1, 2, 4, 8, 16, 32, 64, float("inf")))


class RatingClient:
    BASE_URL = 'http://rating.chgk.info'

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
