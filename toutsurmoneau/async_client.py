import datetime
import logging
import re
import aiohttp
from typing import Optional, Union, Any
from urllib.parse import urlparse
from .errors import ClientError
from .const import KNOWN_PROVIDER_URLS

_LOGGER = logging.getLogger(__name__)
PAGE_LOGIN = 'je-me-connecte'
PAGE_DASHBOARD = 'tableau-de-bord'
PAGE_CONSUMPTION = 'historique-de-consommation-tr'
# daily (Jours) : /Y/m/meter_id : Array(JJMMYYY, daily volume, cumulative volume). Volumes: .xxx
API_ENDPOINT_DAILY = 'statJData'
# monthly (Mois) : /meter_id : Array(mmm. yy, monthly volume, cumulative volume, Mmmmm YYYY)
API_ENDPOINT_MONTHLY = 'statMData'
API_ENDPOINT_CONTRACT = 'donnees-contrats'
AUTHENTICATION_COOKIE = 'eZSESSID'
# regex is before utf8 encoding
# former regex: "_csrf_token" value="([^"]+)"
CSRF_TOKEN_REGEX = '\\\\u0022csrfToken\\\\u0022\\\\u003A\\\\u0022([^,]+)\\\\u0022'
# Map french months to its index
MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
          'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
METER_RETRIEVAL_MAX_DAYS_BACK = 3
METER_NO_VALUE = 0


class AsyncClient():
    """
    Retrieve subscriber and meter information from Suez on toutsurmoneau.fr
    """

    def __init__(self, username: str, password: str, meter_id: Optional[str] = None, url: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None, use_litre: bool = True) -> None:
        """
        Initialize the client object.
        @param username account id
        @param password account password
        @param meter_id water meter ID (optional)
        @param url URL of provider, e.g. one of KNOWN_PROVIDER_URLS or other URL of provider.
        @param session an HTTP session
        @param use_litre use Litre a unit if True, else use api native unit (cubic meter)
        If meter_id is None, it will be read from the web.
        """
        # store useful parameters
        self._username = username
        self._password = password
        self._id = meter_id
        self._client_session = session
        self._use_litre = use_litre
        # Default value: first known provider (Suez)
        if url is None:
            self._base_url = KNOWN_PROVIDER_URLS[0]
        else:
            self._base_url = url

    def _full_url(self, endpoint: str) -> str:
        """Just concatenate the sub path with base URL"""
        return f"{self._base_url}/{endpoint}"

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
        @return True if not zero: valid value
        """
        return int(value) != METER_NO_VALUE

    def _request(self, path: str, data=None, **kwargs: Any) -> aiohttp.ClientSession:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()
        method = 'post'
        if data is None:
            method = 'get'
        return self._client_session.request(method=method, url=self._full_url(path), data=data, **kwargs)

    async def _async_find_in_page(self, page: str, reg_ex: str) -> str:
        """
        Extract the regex from the specified page.
        If _cookies is None, then it sets it, else it remains unchanged.
        """
        async with self._request(path=page) as response:
            page_content = await response.text(encoding='utf-8')
            # get meter id from page
            matches = re.compile(reg_ex).search(page_content)
            if matches is None:
                raise ClientError(f"Could not find {reg_ex} in {page}")
            result = matches.group(1)
            return result

    async def _async_ensure_logged_in(self) -> None:
        """
        Authenticate if not yet done.
        """
        if self._client_session is not None:
            the_cookies = self._client_session.cookie_jar.filter_cookies(
                self._base_url)
            if AUTHENTICATION_COOKIE in the_cookies:
                return
        # go to login page, retrieve CSRF token and login cookies (because cookie is None)
        csrf_token = await self._async_find_in_page(
            PAGE_LOGIN, CSRF_TOKEN_REGEX)
        data = {
            '_csrf_token': csrf_token.encode('utf-8').decode('unicode-escape'),
            '_username': self._username,
            '_password': self._password,
            'signin[username]': self._username,
            'signin[password]': None,
            'tsme_user_login[_username]': self._username,
            'tsme_user_login[_password]': self._password
        }
        # get session cookie used to be authenticated, cookies=login_cookies
        async with self._request(path=PAGE_LOGIN, data=data, allow_redirects=False) as response:
            the_cookies = self._client_session.cookie_jar.filter_cookies(
                self._base_url)
            if AUTHENTICATION_COOKIE not in the_cookies:
                raise ClientError(
                    f'Login error: no {AUTHENTICATION_COOKIE} found in cookies for {PAGE_LOGIN}.')
            page_content = await response.text(encoding='utf-8')
            if PAGE_DASHBOARD not in page_content:
                raise ClientError(
                    f'Login error: no {PAGE_DASHBOARD} found in {PAGE_LOGIN}.')

    async def _async_call_api(self, endpoint) -> dict:
        """Call the specified API

        Regenerate cookie if necessary
        @return the dict of result
        """
        _LOGGER.debug("Calling: %s", endpoint)
        retried = False
        while True:
            await self._async_ensure_logged_in()
            async with self._request(path=endpoint) as response:
                if 'application/json' not in response.headers.get('content-type'):
                    if retried:
                        raise ClientError('Failed refreshing cookie')
                    retried = True
                    # reset cookie to regenerate
                    self._client_session.cookie_jar.clear_domain(
                        urlparse(self._base_url).netloc)
                    # try again
                    continue
                result = await response.json()
            if isinstance(result, list) and len(result) == 2 and result[0] == 'ERR':
                raise ClientError(result[1])
            _LOGGER.debug("Result: %s", result)
            return result

    async def async_meter_id(self) -> str:
        """Water meter identifier

        @return subscriber's water meter identifier
        If it was not provided in initialization, then it is read mon the web site.
        """
        if self._id is None or "".__eq__(self._id):
            await self._async_ensure_logged_in()
            # Read meter ID
            self._id = await self._async_find_in_page(
                PAGE_CONSUMPTION, '/month/([0-9]+)')
        return self._id

    async def async_contracts(self) -> dict:
        """List of contracts for the user.

        @return the list of contracts associated to the calling user.
        """
        contract_list = await self._async_call_api(API_ENDPOINT_CONTRACT)
        for contract in contract_list:
            # remove keys not used
            for key in ['website-link', 'searchData']:
                if key in contract:
                    del contract[key]
        return contract_list

    async def async_daily_for_month(self, report_date: datetime.date, throw: bool = False) -> dict:
        """
        @param report_date [datetime.date] specify year/month for report, e.g. built with Date.new(year,month,1)
        @param throw set to True to get an exception if there is no data for that date
        @return [dict] [day_in_month]={day:, total:} daily usage for the specified month
        """
        if not isinstance(report_date, datetime.date):
            raise ClientError('Argument: Provide a date object')
        try:
            daily = await self._async_call_api(
                f"{API_ENDPOINT_DAILY}/{report_date.year}/{report_date.month}/{await self.async_meter_id()}")
        except Exception as e:
            if throw:
                raise e
            else:
                _LOGGER.debug("Error: %s", e)
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
        _LOGGER.debug("daily_for_month: %s", result)
        return result

    async def async_monthly_recent(self) -> dict:
        """
        @return [Hash] current month
        """
        monthly = await self._async_call_api(
            f"{API_ENDPOINT_MONTHLY}/{await self.async_meter_id()}")
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

    async def async_latest_meter_reading(self, what='absolute', month_data=None) -> Union[float, int]:
        """
        @return the latest meter reading
        """
        reading_date = datetime.date.today()
        # latest available value may be yesterday or the day before
        for _ in range(METER_RETRIEVAL_MAX_DAYS_BACK):
            test_day = reading_date.day
            _LOGGER.debug("Trying day: %d", test_day)
            if month_data is None:
                month_data = await self.async_daily_for_month(reading_date)
            if test_day in month_data[what]:
                return {'date': reading_date, 'volume': month_data[what][test_day]}
            reading_date = reading_date - datetime.timedelta(days=1)
            if reading_date.day > test_day:
                month_data = None
        raise ClientError(
            f"Cannot get latest meter value in last {METER_RETRIEVAL_MAX_DAYS_BACK} days")

    async def async_check_credentials(self) -> bool:
        """
        @return True if credentials are valid
        """
        try:
            await self.async_contracts()
        except Exception as error:
            _LOGGER.debug("Login failed: %s", error)
            return False
        return True
