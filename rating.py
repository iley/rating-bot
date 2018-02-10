import requests
import logging
from exc import RatingBotError
from model import RatingRecord


log = logging.getLogger(__name__)


class RatingClient:
    BASE_URL = 'http://rating.chgk.info'

    def __init__(self):
        pass

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
        try:
            log.info('Fetching rating for %d' % team_id)
            r = requests.get('%s/api/teams/%d/rating.json' % (self.BASE_URL, team_id))
            r.raise_for_status()
            records = [RatingRecord.fromJSON(d) for d in r.json()]
            if not records:
                raise RatingBotError('Рейтинг для команды #%d не найден' % team_id)
            last_record = records[0]
            for record in records[1:]:
                if record.release > last_record.release:
                    last_record = record
            return last_record

        except Exception as ex:
            log.exception(ex)
            raise RatingBotError('Команда #%d не найдена: %s' % (team_id, ex))
