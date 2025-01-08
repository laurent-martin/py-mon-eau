import aiohttp
import datetime
import logging
import re
from typing import Optional, Union, Any
from urllib.parse import urlparse
from .errors import ClientError

_LOGGER = logging.getLogger(__name__)
# Generic URL of Suez web site
GENERIC_BASE_URL = 'https://www.toutsurmoneau.fr'
# pages (return some HTML content, not JSON data)
PAGE_LOGIN = '/mon-compte-en-ligne/je-me-connecte'
PAGE_DASHBOARD = '/mon-compte-en-ligne/tableau-de-bord'
# daily (Jours) : /Y/m/meter_id : Array(JJMMYYY, daily volume, cumulative volume). Volumes: .xxx
API_ENDPOINT_DAILY = '/mon-compte-en-ligne/statJData'
# monthly (Mois) : /meter_id : Array(mmm. yy, monthly volume, cumulative volume, Mmmmm YYYY)
API_ENDPOINT_MONTHLY = '/mon-compte-en-ligne/statMData'
# list contracts associated with account
API_ENDPOINT_CONTRACT = '/public-api/user/donnees-contrats'
API_ENDPOINT_METER_LIST = '/public-api/cel-consumption/meters-list'
API_ENDPOINT_TELEMETRY = '/public-api/cel-consumption/telemetry'
# regex for token in PAGE_LOGIN (before utf8 encoding)
CSRF_TOKEN_REGEX = '\\\\u0022csrfToken\\\\u0022\\\\u003A\\\\u0022([^,]+)\\\\u0022'
# Map french months to its index
MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
          'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
# for retrieval of last reading
METER_RETRIEVAL_MAX_DAYS_BACK = 5
# no reading for meter (total is zero means no value available for meter reading)
METER_NO_VALUE = 0


class AsyncClient():
    '''
    Retrieve subscriber and meter information from Suez on toutsurmoneau.fr
    '''

    def __init__(self, username: str, password: str, meter_id: Optional[str] = None,
                 url: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None,
                 use_litre: bool = True) -> None:
        '''
        Initialize the client object but no network connection is made.

        :param username: account id
        :param password: account password
        :param meter_id: water meter ID (optional)
        :param url: URL of provider, e.g. one of KNOWN_PROVIDER_URLS or other URL of provider.
        :param session: an HTTP session
        :param use_litre: use Litre a unit if True, else use api native unit (cubic meter)

        If meter_id is None, it will be read from the web later.
        '''
        # store useful parameters
        self._username = username
        self._password = password
        self._id = meter_id
        self._client_session = session
        self._use_litre = use_litre
        # base url contains the scheme, address and base path
        if url is None:
            self._provider_url = GENERIC_BASE_URL
            _LOGGER.debug('Defaulting URL to %s', self._provider_url)
        else:
            self._provider_url = url
        self._provider_name = self._provider_url

    def provider_name(self) -> str:
        '''
        :returns: the name of the provider
        '''
        return self._provider_name

    def _full_url(self, endpoint: str) -> str:
        '''
        :returns: full URL by concatenating base URL and sub path
        '''
        return f'{self._provider_url}{endpoint}'

    def _convert_volume(self, volume_m3: float) -> Union[float, int]:
        '''
        :returns: volume converted from API (m3) to desired unit (m3 or litre)
        '''
        if self._use_litre:
            return int(1000 * volume_m3)
        else:
            return volume_m3

    def _is_valid_absolute(self, value) -> bool:
        '''
        :param value: the absolute volume value on meter
        :returns: True if not zero: valid value
        '''
        return int(value) != METER_NO_VALUE

    def ensure_logout(self) -> None:
        '''
        Clear login cookie to force logout and login next time.
        '''
        if self._client_session is not None:
            self._client_session.cookie_jar.clear_domain(urlparse(self._api_base_url).netloc)

    def _dump_cookie_jar(self, jar) -> None:
        _LOGGER.debug('Cookie jar:')
        for cookie in jar:
            _LOGGER.debug(f'Domain: %s, Name: %s = %s', cookie['domain'], cookie.key, cookie.value)

    def _request(self, path: str, data=None, **kwargs: Any) -> aiohttp.ClientResponse:
        '''
        Create a request context manager depending on presence of data: get or post

        If no session exists, create one
        '''
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()
        self._dump_cookie_jar(self._client_session.cookie_jar)
        _LOGGER.debug('=====================================================')
        full_url = self._full_url(path)
        method = 'get'
        if data is not None:
            method = 'post'
            _LOGGER.debug('Data: %s', data)
        if 'params' in kwargs:
            _LOGGER.debug('Params: %s', kwargs['params'])
        _LOGGER.debug('Accessing: %s %s', method, full_url)
        return self._client_session.request(
            method=method,
            url=full_url,
            data=data,
            **kwargs)

    def _validate_response(self, response: aiohttp.ClientResponse, success_code=200) -> None:
        '''
        Validate the response, raise an exception if not successful.
        '''
        _LOGGER.debug('Request Cookie: %s', response.request_info.headers.get('Cookie'))
        _LOGGER.debug('Response: %s', response)
        for cookie in response.cookies:
            _LOGGER.debug('Response Cookie: %s', cookie)
        if response.status != success_code:
            response.raise_for_status()
            raise ClientError(f'HTTP error {response.status} for {response.url}')

    def _find_in_text(self, text: str, reg_ex: str, page: str) -> str:
        '''
        Find the specified regex in the text and return the first group.
        '''
        # get expected regex from page
        matches = re.compile(reg_ex).search(text)
        if matches is None:
            raise ClientError(f'Could not find {reg_ex} in page {page}')
        result = matches.group(1)
        return result

    async def _async_call_with_auth(self, endpoint, decode: bool = True, **kwargs: Any) -> Union[dict, str]:
        '''
        Call the specified endpoint ensuring authentication.

        :param endpoint: the endpoint to call
        :param decode: if True, decode the result as JSON

        :returns: the dict of result, or page
        '''
        _LOGGER.debug('Calling with auth: %s', endpoint)
        # if first attempt fails, login, then try again
        for attempt in range(1, 3):
            async with self._request(path=endpoint, **kwargs) as response:
                self._validate_response(response)
                if not response.url.path.endswith(PAGE_LOGIN):
                    # success !
                    if not decode:
                        return await response.text(encoding='utf-8')
                    if 'application/json' not in response.headers.get('content-type'):
                        raise ClientError('Failed getting data: not JSON content')
                    result = await response.json()
                    if isinstance(result, list) and len(result) == 2 and result[0] == 'ERR':
                        raise ClientError(f'API returned error: {result[1]}')
                    if isinstance(result, dict) and 'content' in result:
                        if result['content'] == None:
                            raise ClientError(f'API returned error: {result['message']}')    
                        result=result['content']
                    _LOGGER.debug('Result: %s', result)
                    return result
                # second attempt, after login failed
                if attempt == 2:
                    raise ClientError(f'Login failed.')
                # first attempt failed, so try to login
                _LOGGER.debug(f'Redirected to {PAGE_LOGIN}, performing login...')
                # step 1: GET login page, retrieve CSRF token
                csrf_token = None
                async with self._request(path=PAGE_LOGIN) as response:
                    text = await response.text(encoding='utf-8')
                    csrf_token = self._find_in_text(text, CSRF_TOKEN_REGEX, PAGE_LOGIN)
                csrf_token = csrf_token.encode('utf-8').decode('unicode-escape')
                _LOGGER.debug('Token: %s', csrf_token)
                # step 2: POST credentials in login page
                credential_data = {
                    '_csrf_token': csrf_token,
                    'tsme_user_login[_username]': self._username,
                    'tsme_user_login[_password]': self._password,
                    'tsme_user_login[_target_path]': PAGE_DASHBOARD,
                }
                # cookies are set in the session
                async with self._request(path=PAGE_LOGIN, data=credential_data, allow_redirects=True) as response:
                    self._validate_response(response)

    async def async_meter_list(self) -> dict:
        '''
        List of meters for the user.

        :returns: the list of meters associated to the calling user.
        '''
        # ignore keys: code, message
        return (await self._async_call_with_auth(API_ENDPOINT_METER_LIST))

    async def async_meter_id(self) -> str:
        '''
        Water meter identifier

        :returns: subscriber's water meter identifier
        If it was not provided in initialization, then it is read from the web site.
        '''
        if self._id is None or ''.__eq__(self._id):
            # Read meter ID
            meter_list = await self.async_meter_list()
            if meter_list['nbMeters'] != 1:
                raise ClientError(f'Unexpected number of meters: {meter_list["nbMeters"]}')
            self._id = meter_list['clientCompteursPro'][0]['compteursPro'][0]['idPDS']
        return self._id

    async def async_contracts(self, active_only: Optional[bool] = True) -> dict:
        '''
        List of contracts for the user.

        :returns: the list of contracts associated to the calling user.
        '''
        contract_list = await self._async_call_with_auth(API_ENDPOINT_CONTRACT)
        for contract in contract_list:
            # remove keys not used
            for key in ['website-link', 'searchData']:
                if key in contract:
                    del contract[key]
        if active_only:
            contract_list = list(filter(lambda c: c['isActif'], contract_list))
        return contract_list

    async def async_daily_for_month(self, report_date: datetime.date) -> dict:
        '''
        :param report_date: specify year/month for report, e.g. built with Date.new(year,month,1)
        :returns: [day_in_month]={day:, total:} daily usage for the specified month
        raise an exception if there is no data for that date
        '''
        if not isinstance(report_date, datetime.date):
            raise ClientError('Coding error: Provide a date object for report_date')
        daily = await self._async_call_with_auth(f'{API_ENDPOINT_DAILY}/{report_date.year}/{report_date.month}/{await self.async_meter_id()}')
        # since the month is known, keep only day in result (avoid redundant information)
        result = {
            'daily': {},
            'absolute': {}
        }
        for i in daily:
            if self._is_valid_absolute(i[2]):
                day_index = int(datetime.datetime.strptime(i[0], '%d/%m/%Y').day)
                result['daily'][day_index] = self._convert_volume(i[1])
                result['absolute'][day_index] = self._convert_volume(i[2])
        _LOGGER.debug('daily_for_month: %s', result)
        return result

    async def async_telemetry(self, mode: str, date_begin: datetime.date, date_end: datetime.date) -> dict:
        '''
        :param mode: monthly or daily
        :param date_begin: date for start
        :param date_end: date for stop
        :returns: measures
        raise an exception if there is a problem
        '''
        if not isinstance(date_begin, datetime.date):
            raise ClientError('Coding error: Provide a date object for date_begin')
        if not isinstance(date_end, datetime.date):
            raise ClientError('Coding error: Provide a date object for date_end')
        result = await self._async_call_with_auth(API_ENDPOINT_TELEMETRY, params = {
            "id_PDS":await self.async_meter_id(),
            "mode": mode,
            "start_date":date_begin.strftime("%Y-%m-%d"),
            "end_date":date_end.strftime("%Y-%m-%d"),
        })
        return result['measures']

    async def async_monthly_recent(self) -> dict:
        '''
        :returns: [Hash] current month
        '''
        monthly = await self._async_call_with_auth(f'{API_ENDPOINT_MONTHLY}/{await self.async_meter_id()}')
        result = {
            'highest_monthly_volume': self._convert_volume(monthly.pop()),
            'last_year_volume': self._convert_volume(monthly.pop()),
            'this_year_volume': self._convert_volume(monthly.pop()),
            'monthly': {},
            'absolute': {}
        }
        # fill monthly by year and month, we assume values are in date order
        for i in monthly:
            # skip values in the future... (meter value is set to zero if there is no reading for future values)
            if self._is_valid_absolute(i[2]):
                # date is 'Month Year'
                d = i[3].split(' ')
                year = int(d[1])
                if year not in result['monthly']:
                    result['monthly'][year] = {}
                    result['absolute'][year] = {}
                month_index = 1 + MONTHS.index(d[0])
                result['monthly'][year][month_index] = self._convert_volume(i[1])
                result['absolute'][year][month_index] = self._convert_volume(i[2])
        return result

    async def async_latest_meter_reading(self, what='absolute', month_data=None) -> Union[float, int]:
        '''
        :returns: the latest meter reading
        '''
        reading_date = datetime.date.today()
        # latest available value may be yesterday or the day before
        for _ in range(METER_RETRIEVAL_MAX_DAYS_BACK):
            test_day = reading_date.day
            _LOGGER.debug('Trying day: %d', test_day)
            try:
                if month_data is None:
                    month_data = await self.async_daily_for_month(reading_date)
                if test_day in month_data[what]:
                    return {'date': reading_date, 'volume': month_data[what][test_day]}
            except Exception as error:
                _LOGGER.debug('Error getting month data: %s', error)
            reading_date = reading_date - datetime.timedelta(days=1)
            if reading_date.day > test_day:
                month_data = None
        raise ClientError(f'Cannot get latest meter value in the last {METER_RETRIEVAL_MAX_DAYS_BACK} days')

    async def async_check_credentials(self) -> bool:
        '''
        :returns: True if credentials are valid
        '''
        try:
            await self.async_contracts()
            return True
        except Exception as error:
            _LOGGER.debug('Login failed: %s', error)
            return False
