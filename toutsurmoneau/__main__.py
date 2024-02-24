import toutsurmoneau
import argparse
import sys
import yaml
import datetime
import logging
import asyncio
import aiohttp


def command_line():
    """Main function for command line"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', required=True,
                        help='Suez username')
    parser.add_argument('-p', '--password',
                        required=True, help='Password')
    parser.add_argument('-c', '--meter_id',
                        required=False, help='Water Meter Id')
    parser.add_argument('-U', '--url',
                        required=False, help='full URL of provider, including mon-compte-en-ligne')
    parser.add_argument('-e', '--execute',
                        required=False, default='check_credentials', help='Command to execute (attributes,contracts,meter_id,latest_meter_reading,monthly_recent,daily_for_month,check_credentials)')
    parser.add_argument('-d', '--data',
                        required=False, help='Additional data for the command (e.g. date for daily_for_month)')
    parser.add_argument(
        '--debug', action='store_true', default=False)
    parser.add_argument(
        '--legacy', action='store_true', default=False)
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    if args.legacy:
        result = legacy_execute(args)
    else:
        result = asyncio.run(async_execute(args))
    yaml.dump(result, sys.stdout)


def legacy_execute(args):
    """Execute the command in legacy mode (sync)."""
    client = toutsurmoneau.Client(
        username=args.username, password=args.password,
        meter_id=args.meter_id, provider=args.url)
    try:
        if args.execute == 'check_credentials':
            data = client.check_credentials()
        elif args.execute == 'attributes':
            client.update()
            data = {
                'attr': client.attributes,
                'state': client.state
            }
        else:
            raise Exception('No such command: '+args.execute)
        return data
    finally:
        client.close_session()


_LOGGER = logging.getLogger('aiohttp.client')


async def on_request_start(session, context, params):
    """Debug http"""
    _LOGGER.debug(f'Starting request <%s>', params)


async def async_execute(args):
    """Execute the CLI command in async mode."""
    trace_config = aiohttp.TraceConfig()
    if args.debug:
        trace_config.on_request_start.append(on_request_start)
    async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:
        client = toutsurmoneau.AsyncClient(username=args.username, password=args.password,
                                           meter_id=args.meter_id, url=args.url, session=session)
        if args.execute == 'check_credentials':
            data = await client.async_check_credentials()
        elif args.execute == 'contracts':
            data = await client.async_contracts()
        elif args.execute == 'meter_id':
            data = await client.async_meter_id()
        elif args.execute == 'latest_meter_reading':
            data = await client.async_latest_meter_reading()
        elif args.execute == 'monthly_recent':
            data = await client.async_monthly_recent()
        elif args.execute == 'daily_for_month':
            if args.data is None:
                test_date = datetime.date.today()
            else:
                test_date = datetime.datetime.strptime(
                    args.data, '%Y%m').date()
            data = await client.async_daily_for_month(test_date)
        else:
            raise Exception('No such command: '+args.execute)
        return data


if __name__ == '__main__':
    sys.exit(command_line())
