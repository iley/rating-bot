import requests
import logging
from expiringdict import ExpiringDict
from prometheus_client import Histogram
from datetime import datetime, timedelta

from .exc import RatingBotError
from .data_types import Rating, TournamentStatus, TournamentInfo, SyncApplications
from html.parser import HTMLParser

log = logging.getLogger(__name__)
hist_fetch_rating = Histogram('rating_bot_fetch_rating_seconds',
                              'Time spent fetching data from the Rating website',
                              buckets=(1, 2, 4, 8, 16, 32, 64, float("inf")))
class CityHtmlParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._city_name = ''
        self._track_tournamets = False
        self._tournament_id = -1
        self._tournament_name = ''
        self._tournaments = []
        self._sync_app = SyncApplications()
        self._sync_apps = []
        self._counter = 0

    def get_name(self):
        return self._city_name

    def get_tournaments(self):
        return self._tournaments

    def get_apps(self):
        return self._sync_apps
        #res = []
        #was = set()
        #for sync_app in self._sync_apps:
            #if sync_app._tournament_id in was:
                #continue
            #was.add(sync_app._tournament_id)
            #for it in self._sync_apps:
                #if it._tournament_id == sync_app._tournament_id:
                    #res.append(it)
        #return res

    def handle_starttag(self, tag, attrs):
        if not self._track_tournamets:
            return
        my_dict = dict(attrs)
        if 'href' in my_dict and my_dict['href'].startswith('/tournament/'):
            self._tournament_id = int(my_dict['href'].split('/')[2])
            self._sync_app._tournament_id = int(my_dict['href'].split('/')[2])
            self._counter = 11

    def handle_data(self, data):
        if data.startswith('Синхроны в городе'):
            self._city_name = data.split()[3]
        elif data.startswith('Время'):
            self._track_tournamets = True
        elif self._counter > 0:
            self._counter = self._counter - 1
            if self._counter == 10:
                self._tournament_name = data.strip()
                self._sync_app._tournament_name = data.strip()
            elif self._counter == 3:
                self._sync_app._delegate_name = data.strip()
            elif self._counter == 0:
                self._sync_app._time = data.strip()
                self._sync_apps.append(self._sync_app)
                self._sync_app = SyncApplications()
                self._tournaments.append(
                        (self._tournament_id,
                         self._tournament_name,
                         data.strip()))

class LeaderHtmlParser(HTMLParser):
    def __init__(self, delegate_name):
        HTMLParser.__init__(self)
        self._leader_name = ''
        self._delegate_name = delegate_name
        self._counter = -1

    def get_res(self):
        return self._leader_name

    def handle_data(self, data):
        if self._counter < 0:
            if self._delegate_name == data.strip():
                self._counter = 4
            return
        self._counter -= 1
        if self._counter == 0:
            self._leader_name = data.strip()

class EditorsHtmlParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._editors = []
        self._parse_editors = False
        self._wait_next_data = False

    def get_editors(self):
        return self._editors

    def handle_starttag(self, tag, attrs):
        if self._parse_editors and tag == 'span':
            self._wait_next_data = True

    def handle_endtag(self, tag):
        if tag == 'div':
            self._parse_editors = False

    def handle_data(self, data):
        if data.strip() == 'Редакторы':
            self._parse_editors = True
        elif self._wait_next_data and len(data.strip()) > 0:
            self._editors.append(data.strip())
            self._wait_next_data = False


def isResultsOpen(results_json):
    commands = len(results_json)
    commands_with_result = 0
    for result in results_json:
        if 'position' in result and result['position'] != '9999':
            commands_with_result += 1
    return commands_with_result*2 > commands

class RatingClient:
    BASE_URL = 'https://rating.chgk.info'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    MOSCOW_TIMEZONE = ''

    def __init__(self):
        self._cache = ExpiringDict(max_len=1000, max_age_seconds=5*60)
        self._day_cache = ExpiringDict(max_len=1000, max_age_seconds=24*60*60)

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

    def fetch_tournaments_for_city(self, city_id):
        if ('city', city_id) in self._cache:
            log.info('Tournaments for city %d cached' % city_id)
            return self._cache[('city', city_id)]
        try:
            log.info('Fetching city %d' % city_id)
            r = requests.get('%s/synch_town/%d' % (self.BASE_URL, city_id))
            r.raise_for_status()
            parser = CityHtmlParser()
            parser.feed(r.text)
            result = {}
            for sync_app in parser.get_apps():
                self._get_leader(sync_app)
                sync_app._tournament_name = sync_app._tournament_name + ' (' + ', '.join(self._get_editors(sync_app._tournament_id)) + ')'
                if not sync_app._tournament_id in result:
                    result[sync_app._tournament_id] = []
                result[sync_app._tournament_id].append(sync_app)
            self._cache[('city', city_id)] = (parser.get_name(), result)
            return parser.get_name(), result
        except Exception as ex:
            log.exception(ex)
            return None

    def fetch_tournament(self, tournament_id):
        if ('tournament', tournament_id) in self._cache:
            log.info('Tournament %d cached' % tournament_id)
            return self._cache[('tournament', tournament_id)]
        try:
            log.info('Fetching tournament %d' % tournament_id)

            r = requests.get('%s/api/tournaments/%d.json' % (self.BASE_URL, tournament_id))
            r.raise_for_status()
            log.info('json %s' % r.json())
            tournament_json = r.json()[0]
            tournament_info = TournamentInfo()
            tournament_info.name = tournament_json['name']
            tournament_info.type = tournament_json['type_name']

            start_date = datetime.strptime(tournament_json['date_start'] + self.MOSCOW_TIMEZONE, self.DATE_FORMAT)
            end_date = datetime.strptime(tournament_json['date_end'] + self.MOSCOW_TIMEZONE, self.DATE_FORMAT)
            today_date = datetime.today() + timedelta(hours=2)
            tournament_info.time_delta = today_date - end_date
            if today_date < start_date:
                self._cache[('tournament', tournament_id)] = tournament_info
                return tournament_info
            tournament_info.status = TournamentStatus.RUNNING

            r = requests.get('%s/api/tournaments/%d/list.json' % (self.BASE_URL, tournament_id))
            r.raise_for_status()
            results_json = r.json()
            if isResultsOpen(results_json):
                tournament_info.status = TournamentStatus.RESULTS_OPEN

            if not tournament_info.isOchnik() and today_date > end_date + timedelta(days=1):
                r = requests.get('%s/tournament/%d/controversials' % (self.BASE_URL, tournament_id))
                r.raise_for_status()
                if r.text.find('Поданные спорные ответы') != -1 and r.text.find('class="controversial_status">\n                                    Новый') == -1:
                    tournament_info.status = TournamentStatus.CONTROVERSIALS_DONE

            if not tournament_info.isOchnik() and today_date > end_date + timedelta(days=5):
                r = requests.get('%s/tournament/%d/appeals' % (self.BASE_URL, tournament_id))
                r.raise_for_status()
                if r.text.find('Поданные апелляции') != -1 and r.text.find('Апелляция не рассмотрена') == -1:
                    tournament_info.status = TournamentStatus.APPEALS_DONE

            self._cache[('tournament', tournament_id)] = tournament_info
            return tournament_info
        except Exception as ex:
            log.exception(ex)
            return '', None

    def fetch_tournaments(self, team_id):
        cache_key = ('tournaments', team_id)
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            r = requests.get('%s/api/teams/%d/tournaments/last.json' % (self.BASE_URL, team_id))
            r.raise_for_status()
            self._cache[cache_key] = r.json()['tournaments']
            return r.json()['tournaments']
        except Exception as ex:
            log.exception(ex)
            return []

    def _get_leader(self, sync_app):
        cache_key = ('tournament_requests', sync_app._tournament_id)
        if not cache_key in self._cache:
            r = requests.get('%s/tournament/%d/requests/' % (self.BASE_URL, sync_app._tournament_id))
            r.raise_for_status()
            self._cache[cache_key] = r.text
        parser = LeaderHtmlParser(sync_app._delegate_name)
        parser.feed(self._cache[cache_key])
        sync_app._leader_name = parser.get_res()

    def _get_editors(self, tournament_id):
        cache_key = ('editors', tournament_id)
        if cache_key in self._day_cache:
            return self._day_cache[cache_key]
        r = requests.get('%s/tournament/%d' % (self.BASE_URL, tournament_id))
        r.raise_for_status()
        parser = EditorsHtmlParser()
        parser.feed(r.text)
        self._day_cache[cache_key] = parser.get_editors()
        return self._day_cache[cache_key]

    def status_url(self, tournament_id, status):
        options = {3: '%s/tournament/%d',
                   4: '%s/tournament/%d/controversials/',
                   5: '%s/tournament/%d/appeals/'}
        if not status.isImportant():
            return ''
        return options[status] % (self.BASE_URL, tournament_id)
