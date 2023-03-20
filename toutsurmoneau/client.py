import asyncio
import aiohttp
import datetime
from typing import Optional, Union
from .errors import ClientError
from .async_client import AsyncClient


class Client():
    """
    Retrieve subscriber and meter information from Suez on toutsurmoneau.fr
    """

    def __init__(self, username, password: str, meter_id: Optional[str] = None, provider: Optional[str] = None, session=None, timeout=None):
        """Initialize the client object.

        If meter_id is None, A default value will be used from the web account.

        @param username account id
        @param password account password
        @param meter_id water meter ID (optional)
        @param provider name of provider from PROVIDER_URLS, or URL of provider
        @param session an HTTP session (not used)
        @param timeout HTTP timeout (not used)
        """
        # updated when update() is called
        self.attributes = {}
        # current meter reading
        self.state = {}
        # Legacy, not used:
        self.success = True
        # Legacy, not used:
        self.data = {}
        self._async_client = AsyncClient(
            username=username, password=password, session=None, meter_id=meter_id, url=provider, use_litre=True)

    async def _async_task(self, check_only: bool = False):
        async with aiohttp.ClientSession() as session:
            # using this session will autoclose
            self._async_client._client_session = session
            if check_only:
                return await self._async_client.async_check_credentials()
            today = datetime.date.today()
            self.attributes['attribution'] = f"Data provided by {self._async_client._base_url}"
            summary = await self._async_client.async_monthly_recent()
            self.attributes['lastYearOverAll'] = summary['last_year_volume']
            self.attributes['thisYearOverAll'] = summary['this_year_volume']
            self.attributes['highestMonthlyConsumption'] = summary['highest_monthly_volume']
            self.attributes['history'] = summary['monthly']
            self.attributes['thisMonthConsumption'] = await self._async_client.async_daily_for_month(
                today)
            self.attributes['previousMonthConsumption'] = await self._async_client.async_daily_for_month(
                datetime.date(today.year, today.month - 1, 1))
            self.state = (await self._async_client.async_latest_meter_reading(
                'daily', self.attributes['thisMonthConsumption']))['volume']

    def check_credentials(self) -> bool:
        """
        @return True if credentials are valid
        """
        return asyncio.run(main=self._async_task(True))

    def update(self) -> dict:
        """
        @return a summary of collected data.
        """
        asyncio.run(main=self._async_task())
        return self.attributes

    def close_session(self) -> None:
        """Close current session."""
        pass
