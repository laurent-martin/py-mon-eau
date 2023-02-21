import requests
import re
import datetime


class ToutSurMonEau():
    """Access API from toutsurmoneau.fr"""
    # supported providers
    BASE_URIS = {
        'Suez': 'https://www.toutsurmoneau.fr/mon-compte-en-ligne',
        'Eau Olivet': 'https://www.eau-olivet.fr/mon-compte-en-ligne'
    }
    PAGE_LOGIN = 'je-me-connecte'
    PAGE_DASHBOARD = 'tableau-de-bord'
    PAGE_CONSUMPTION = 'historique-de-consommation-tr'
    # daily (Jours) : /Y/m/counterid : Array(JJMMYYY, daily volume, cumulative volume). Volumes: .xxx
    API_ENDPOINT_DAILY = 'statJData'
    # monthly (Mois) : /counterid : Array(mmm. yy, monthly volume, cumulative volume, Mmmmm YYYY)
    API_ENDPOINT_MONTHLY = 'statMData'
    API_ENDPOINT_CONTRACT = 'donnees-contrats'
    SESSION_ID = 'eZSESSID'
    # regex is before utf8 encoding
    CSRF_TOKEN_REGEX = '\\\\u0022csrfToken\\\\u0022\\\\u003A\\\\u0022([^,]+)\\\\u0022'
    MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    def __init__(self, username, password, counter_id=None, provider=None, session=None, timeout=None, auto_close=None, use_litre=True, compatibility=True):
        """Initialize the client object.
        If counter_id is None, it will be read from the web.
        If provider is None, 'Suez' is used.
        If session is None, an HTTP session is opened locally and auto_close default to True
        Else auto_close default to False
        auto_close set to True/False overrides default behavior.
        """
        self.attributes = {}
        self.state = {}
        self._username = username
        self._password = password
        self._id = counter_id
        self._session = session
        self._timeout = timeout
        self._cookies = None
        self._compatibility = compatibility
        if self._compatibility:
            self._use_litre = True
        else:
            self._use_litre = use_litre
        if provider is None:
            provider = 'Suez'
        if auto_close is None:
            if session is None:
                self._auto_close = True
            else:
                self._auto_close = False
        else:
            self._auto_close = auto_close
        self._base_uri = self.BASE_URIS[provider]
        if self._base_uri is None:
            self._base_uri = provider

    def _session_get(self, endpoint, cookies=None):
        """Call GET on specified endpoint (path)"""
        if self._session is None:
            self._session = requests.Session()
        return self._session.get(self._base_uri+'/'+endpoint, cookies=cookies, timeout=self._timeout)

    def _find_in_page(self, page: str, reg_ex: str) -> str:
        """
        Extract the regex from the specified page.
        If _cookies is None, then it sets it, else it remains unchanged.
        """
        response = self._session_get(page, cookies=self._cookies)
        # get counter id from page
        matcher = re.compile(reg_ex)
        matches = matcher.search(response.content.decode('utf-8'))
        if matches is None:
            raise Exception('Could not find '+reg_ex+' in '+page)
        result = matches.group(1)
        # when not authenticated, cookies are used for authentication
        if self._cookies is None:
            self._cookies = response.cookies
        return result

    def _generate_access_cookie(self):
        """
        Generate authentication cookie.
        self._cookies is None when called, and is set after call.
        """
        if self._cookies is not None:
            raise Exception('Clear cookie before asking update')
        # go to login page, retrieve token and login cookies
        csrf_token = self._find_in_page(
            self.PAGE_LOGIN, self.CSRF_TOKEN_REGEX).encode('utf-8').decode('unicode-escape')
        # former regex: "_csrf_token" value="([^"]+)"
        login_cookies = self._cookies
        # reset cookies , as it is not yet the auth cookies
        self._cookies = None
        data = {
            '_csrf_token': csrf_token,
            '_username': self._username,
            '_password': self._password,
            'signin[username]': self._username,
            'signin[password]': None,
            'tsme_user_login[_username]': self._username,
            'tsme_user_login[_password]': self._password
        }
        # get session cookie used to be authenticated
        response = self._session.post(
            self._base_uri + '/' + self.PAGE_LOGIN,
            data=data,
            cookies=login_cookies,
            allow_redirects=False)
        the_cookies = response.cookies.get_dict()
        if (self.PAGE_DASHBOARD not in response.content.decode('utf-8')) or (self.SESSION_ID not in the_cookies):
            raise Exception(
                'Login error: Please check your username/password.')
        # build cookie used when authenticated
        self._cookies = {self.SESSION_ID: the_cookies[self.SESSION_ID]}

    def _counter_id(self) -> str:
        if self._id is None or "".__eq__(self._id):
            if self._cookies is None:
                self._generate_access_cookie()
            # Read counter ID
            self._id = self._find_in_page(
                self.PAGE_CONSUMPTION, '/month/([0-9]+)')
        return self._id

    def _call_api(self, endpoint) -> dict:
        """Call the API, regenerate cookie if necessary"""
        retried = False
        while True:
            if self._cookies is None:
                self._generate_access_cookie()
            response = self._session_get(endpoint, cookies=self._cookies)
            if 'application/json' in response.headers.get('content-type'):
                if self._auto_close:
                    self.close_session()
                return response.json()
            if retried:
                raise Exception('Failed refreshing cookie')
            retried = True
            # reset cookie to regenerate
            self._cookies = None

    def _convert_volume(self, volume: float) -> float | int:
        if self._use_litre:
            return int(1000*volume)
        else:
            return volume

    def contracts(self):
        return self._call_api(self.API_ENDPOINT_CONTRACT)

    # @param report_date [datetime.date] use year and month, built with Date.new(year,month,1)
    # @return Hash [day_in_month]={day:, total:}
    def daily_for_month(self, report_date: datetime.date) -> dict:
        """Returns daily usage for the specified month, give Date object"""
        if not isinstance(report_date, datetime.date):
            raise Exception('provide a date')
        daily = self._call_api('{}/{}/{}/{}'.format(
            self.API_ENDPOINT_DAILY, report_date.year, report_date.month, self._counter_id()))
        # since the month is known, keep only day in result (avoid redundant information)
        result = {}
        for i in daily:
            if i[2] != 0:
                result[datetime.datetime.strptime(
                    i[0], '%d/%m/%Y').day] = {'day': i[1], 'total': i[2]}
        return result

    # @return [Hash] current month
    def monthly_recent(self) -> dict:
        monthly = self._call_api(
            self.API_ENDPOINT_MONTHLY + '/' + self._counter_id())
        h = {}
        result = {
            'monthly':                h,
            'state':                  None,
            'highest_monthly_volume': monthly.pop(),
            'last_year_volume':       monthly.pop(),
            'this_year_volume':       monthly.pop()
        }
        # fill monthly by year and month
        for i in monthly:
            total_volume = self._convert_volume(i[2])
            # skip futures
            if total_volume == 0:
                next
            # date is Month Year
            d = i[3].split(' ')
            year = int(d[1])
            month = 1 + self.MONTHS.index(d[0])
            if year not in h:
                h[year] = {}
            result['state'] = total_volume
            h[year][month] = {
                'month': self._convert_volume(i[1]),
                'total': total_volume
            }
        return result

    def total_volume(self) -> float | int:
        return self.monthly_recent()['state']

    def check_credentials(self):
        """Exception if credentials are not valid"""
        self.contracts()

    def update(self):
        """Return a summary of collected data."""
        if self._compatibility:
            self.attributes['attribution'] = "Data provided by "+self._base_uri
            summary = self.monthly_recent()
            self.state = summary['state']
            self.attributes['lastYearOverAll'] = summary['last_year_volume']
            self.attributes['thisYearOverAll'] = summary['this_year_volume']
            self.attributes['highestMonthlyConsumption'] = summary['highest_monthly_volume']
            self.attributes['history'] = summary['monthly']
            today = datetime.date.today()
            self.attributes['thisMonthConsumption'] = self.daily_for_month(
                today)
            self.attributes['previousMonthConsumption'] = self.daily_for_month(
                datetime.date(today.year, today.month - 1, 1))
        else:
            self.attributes['attribution'] = "Data provided by "+self._base_uri
            self.attributes['contracts'] = self.contracts()
            self.attributes['summary'] = self.monthly_recent()
            self.attributes['this_month'] = self.daily_for_month(
                datetime.date.today())
            self.state = self.attributes['summary']['state']
        return self.attributes

    def close_session(self):
        """Close current session."""
        if self._session is not None:
            self._session.close()
            self._session = None
