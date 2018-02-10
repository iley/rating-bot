import requests
import logging
from exc import RatingBotError


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
            raise RatingBotError('Team %d not found: %s' % (team_id, ex))
