import datetime
import requests
import logging
import re
from typing import Optional, Union

_LOGGER = logging.getLogger(__name__)
# supported providers
PROVIDER_URLS = {
    'Suez': 'https://www.toutsurmoneau.fr/mon-compte-en-ligne',
    'Eau Olivet': 'https://www.eau-olivet.fr/mon-compte-en-ligne'
}
PAGE_LOGIN = 'je-me-connecte'
PAGE_DASHBOARD = 'tableau-de-bord'
PAGE_CONSUMPTION = 'historique-de-consommation-tr'
# daily (Jours) : /Y/m/meter_id : Array(JJMMYYY, daily volume, cumulative volume). Volumes: .xxx
API_ENDPOINT_DAILY = 'statJData'
# monthly (Mois) : /meter_id : Array(mmm. yy, monthly volume, cumulative volume, Mmmmm YYYY)
API_ENDPOINT_MONTHLY = 'statMData'
API_ENDPOINT_CONTRACT = 'donnees-contrats'
SESSION_ID = 'eZSESSID'
# regex is before utf8 encoding
# former regex: "_csrf_token" value="([^"]+)"
CSRF_TOKEN_REGEX = '\\\\u0022csrfToken\\\\u0022\\\\u003A\\\\u0022([^,]+)\\\\u0022'
# Map french months to its index
MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
          'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
METER_RETRIEVAL_MAX_DAYS_BACK = 3


class ToutSurMonEauError(Exception):
    """Raised a problem occurs while calling the API"""
    pass


class ToutSurMonEau():
    """
    Retrieve subscriber and meter information from Suez on toutsurmoneau.fr
    """

    def __init__(self, username, password: str, meter_id: Optional[str] = None, provider: Optional[str] = None, session=None, timeout=None, auto_close: Optional[bool] = None, use_litre=True, compatibility=True):
        """
        Initialize the client object.
        @param username account id
        @param password account password
        @param meter_id water meter ID (optional)
        @param provider name of provider from PROVIDER_URLS, or URL of provider
        @param session an HTTP session
        @param timeout HTTP timeout
        @param auto_close close the http session after each api call
        @param use_litre use Litre a unit if True, else use api native unit (cubic meter)
        @param compatibility if True, return values compatible with pySuez
        If meter_id is None, it will be read from the web.
        If session is None, an HTTP session is opened locally and auto_close default to True
        Else auto_close default to False
        auto_close set to True/False overrides default behavior.
        """
        # updated when update() is called
        self.attributes = {}
        # current meter reading
        self.state = {}
        # Legacy, not used:
        self.success = True
        # Legacy, not used:
        self.data = {}
        # store useful parameters
        self._username = username
        self._password = password
        self._id = meter_id
        self._session = session
        self._timeout = timeout
        self._cookies = None
        self._compatibility = compatibility
        self._use_litre = use_litre
        if self._compatibility:
            self._use_litre = True
        if auto_close is None:
            if session is None:
                self._auto_close = True
            else:
                self._auto_close = False
        else:
            self._auto_close = auto_close
        # Default value
        if provider is None:
            provider = 'Suez'
        # If name in table, use URL, or the provider is the URL
        if provider in PROVIDER_URLS:
            self._base_url = PROVIDER_URLS[provider]
        else:
            self._base_url = provider

    def _load_page(self, endpoint, cookies=None, data=None) -> str:
        """Call GET (data=None) or POST on specified endpoint (path)"""
        if self._session is None:
            self._session = requests.Session()
        if data is None:
            return self._session.get(f"{self._base_url}/{endpoint}", cookies=cookies, timeout=self._timeout)
        else:
            return self._session.post(
                f"{self._base_url}/{endpoint}", cookies=cookies, data=data, allow_redirects=False)

    def _find_in_page(self, page: str, reg_ex: str) -> str:
        """
        Extract the regex from the specified page.
        If _cookies is None, then it sets it, else it remains unchanged.
        """
        response = self._load_page(page, cookies=self._cookies)
        # get meter id from page
        matcher = re.compile(reg_ex)
        matches = matcher.search(response.content.decode('utf-8'))
        if matches is None:
            raise ToutSurMonEauError(f"Could not find {reg_ex} in {page}")
        result = matches.group(1)
        # when not authenticated, cookies are used for authentication
        if self._cookies is None:
            self._cookies = response.cookies
        return result

    def _generate_access_cookie(self) -> None:
        """
        Generate authentication cookie.
        self._cookies is None when called, and is set after call.
        """
        if self._cookies is not None:
            raise ToutSurMonEauError('INTERNAL ERROR: Clear cookie before asking update of it')
        # go to login page, retrieve token and login cookies
        csrf_token = self._find_in_page(
            PAGE_LOGIN, CSRF_TOKEN_REGEX).encode('utf-8').decode('unicode-escape')
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
        response = self._load_page(
            PAGE_LOGIN, cookies=login_cookies, data=data)
        the_cookies = response.cookies.get_dict()
        if (PAGE_DASHBOARD not in response.content.decode('utf-8')) or (SESSION_ID not in the_cookies):
            raise ToutSurMonEauError(
                'Login error: Please check your username/password.')
        # build cookie used when authenticated
        self._cookies = {SESSION_ID: the_cookies[SESSION_ID]}

    def _call_api(self, endpoint) -> dict:
        """Call the specified API

        Regenerate cookie if necessary
        @return the dict of result
        """
        _LOGGER.debug(f"Calling: {endpoint}")
        retried = False
        while True:
            if self._cookies is None:
                self._generate_access_cookie()
            response = self._load_page(endpoint, cookies=self._cookies)
            if 'application/json' in response.headers.get('content-type'):
                if self._auto_close:
                    self.close_session()
                result = response.json()
                if isinstance(result, list) and len(result) == 2 and result[0] == 'ERR':
                    raise ToutSurMonEauError(result[1])
                _LOGGER.debug(f"Result: {result}")
                return result
            if retried:
                raise ToutSurMonEauError('Failed refreshing cookie')
            retried = True
            # reset cookie to regenerate
            self._cookies = None

    def _convert_volume(self, volume: float) -> Union[float, int]:
        """
        @return volume converted to desired unit (m3 or litre)
        """
        if self._use_litre:
            return int(1000*volume)
        else:
            return volume

    def _is_valid_absolute(self, value) -> bool:
        """
        @param value the absolute volume value on meter
        @return True if zero: invalid value
        """
        return int(value) != 0

    def meter_id(self) -> str:
        """Water meter identifier

        @return subscriber's water meter identifier
        If it was not provided in initialization, then it is read mon the web site.
        """
        if self._id is None or "".__eq__(self._id):
            if self._cookies is None:
                self._generate_access_cookie()
            # Read meter ID
            self._id = self._find_in_page(
                PAGE_CONSUMPTION, '/month/([0-9]+)')
        return self._id

    def contracts(self) -> dict:
        """List of contracts for the user.
        
        @return the list of contracts associated to the calling user.
        """
        contract_list = self._call_api(API_ENDPOINT_CONTRACT)
        for contract in contract_list:
            # remove keys not used
            for key in ['website-link', 'searchData']:
                if key in contract:
                    del contract[key]
        return contract_list

    def daily_for_month(self, report_date: datetime.date, throw: bool = False) -> dict:
        """
        @param report_date [datetime.date] specify year/month for report, e.g. built with Date.new(year,month,1)
        @param throw set to True to get an exception if there is no data for that date
        @return [dict] [day_in_month]={day:, total:} daily usage for the specified month
        """
        if not isinstance(report_date, datetime.date):
            raise ToutSurMonEauError('Argument: Provide a date object')
        try:
            daily = self._call_api(
                f"{API_ENDPOINT_DAILY}/{report_date.year}/{report_date.month}/{self.meter_id()}")
        except Exception as e:
            if throw:
                raise e
            else:
                _LOGGER.debug(f"Error: {e}")
            daily = []
        # since the month is known, keep only day in result (avoid redundant information)
        result = {
            'daily': {},
            'absolute': {}
        }
        for i in daily:
            if self._is_valid_absolute(i[2]):
                day_index = int(
                    datetime.datetime.strptime(i[0], '%d/%m/%Y').day)
                result['daily'][day_index] = self._convert_volume(i[1])
                result['absolute'][day_index] = self._convert_volume(i[2])
        _LOGGER.debug(f"daily_for_month: {result}")
        return result

    def monthly_recent(self) -> dict:
        """
        @return [Hash] current month
        """
        monthly = self._call_api(
            f"{API_ENDPOINT_MONTHLY}/{self.meter_id()}")
        result = {
            'highest_monthly_volume': self._convert_volume(monthly.pop()),
            'last_year_volume':       self._convert_volume(monthly.pop()),
            'this_year_volume':       self._convert_volume(monthly.pop()),
            'monthly':                {},
            'absolute':               {}
        }
        # fill monthly by year and month, we assume values are in date order
        for i in monthly:
            # skip values in the future... (meter value is set to zero if there is no reading for future values)
            if self._is_valid_absolute(i[2]):
                # date is "Month Year"
                d = i[3].split(' ')
                year = int(d[1])
                if year not in result['monthly']:
                    result['monthly'][year] = {}
                    result['absolute'][year] = {}
                month_index = 1+MONTHS.index(d[0])
                result['monthly'][year][month_index] = self._convert_volume(
                    i[1])
                result['absolute'][year][month_index] = self._convert_volume(
                    i[2])
        return result

    def latest_meter_reading(self, what='absolute', month_data=None) -> Union[float, int]:
        """
        @return the latest meter reading
        """
        reading_date = datetime.date.today()
        # latest available value may be yesterday or the day before
        for _ in range(METER_RETRIEVAL_MAX_DAYS_BACK):
            test_day = reading_date.day
            _LOGGER.debug(f"Trying day: {test_day}", )
            if month_data is None:
                month_data = self.daily_for_month(reading_date)
            if test_day in month_data[what]:
                return {'date': reading_date, 'volume': month_data[what][test_day]}
            reading_date = reading_date - datetime.timedelta(days=1)
            if reading_date.day > test_day:
                month_data = None
        raise ToutSurMonEauError(
            f"Cannot get latest meter value in last {METER_RETRIEVAL_MAX_DAYS_BACK} days")

    def check_credentials(self) -> bool:
        """
        @return True if credentials are valid
        """
        try:
            self.contracts()
        except Exception:
            return False
        return True

    def update(self) -> dict:
        """
        @return a summary of collected data.
        """
        today = datetime.date.today()
        self.attributes['attribution'] = f"Data provided by {self._base_url}"
        if self._compatibility:
            summary = self.monthly_recent()
            self.attributes['lastYearOverAll'] = summary['last_year_volume']
            self.attributes['thisYearOverAll'] = summary['this_year_volume']
            self.attributes['highestMonthlyConsumption'] = summary['highest_monthly_volume']
            self.attributes['history'] = summary['monthly']
            self.attributes['thisMonthConsumption'] = self.daily_for_month(
                today)
            self.attributes['previousMonthConsumption'] = self.daily_for_month(
                datetime.date(today.year, today.month - 1, 1))
            self.state = self.latest_meter_reading(
                'daily', self.attributes['thisMonthConsumption'])['volume']
        else:
            self.attributes['contracts'] = self.contracts()
            self.attributes['monthly'] = self.monthly_recent()
            self.attributes['this_month'] = self.daily_for_month(
                datetime.date.today())
            self.attributes['latest_daily'] = self.latest_meter_reading(
                'daily', self.attributes['this_month'])
            self.state = self.latest_meter_reading(
                'absolute', self.attributes['this_month'])['volume']
        return self.attributes

    def close_session(self) -> None:
        """Close current session."""
        if self._session is not None:
            self._session.close()
            self._session = None
