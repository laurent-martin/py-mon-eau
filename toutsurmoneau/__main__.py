import toutsurmoneau
import argparse
import sys
import yaml
import datetime
import logging
import asyncio
import aiohttp

_LOGGER = logging.getLogger('aiohttp.client')


async def on_request_start(session, context, params):
    _LOGGER.debug(f'Starting request <%s>', params)


def command_line():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', required=True,
                        help='Suez username')
    parser.add_argument('-p', '--password',
                        required=True, help='Password')
    parser.add_argument('-c', '--meter_id',
                        required=False, help='Water Meter Id')
    parser.add_argument('-P', '--provider',
                        required=False, help='Provider name or URL')
    parser.add_argument('-e', '--execute',
                        required=False, default='attributes', help='Command to execute (attributes,contracts,meter_id,latest_meter_reading,monthly_recent,daily_for_month,check_credentials)')
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
        result = execute_legacy(args)
    else:
        result = asyncio.run(async_execute(args))
    yaml.dump(result, sys.stdout)


def execute_legacy(args):
    client = toutsurmoneau.Client(args.username, args.password,
                                  args.meter_id, args.provider)
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


async def async_execute(args):
    async with aiohttp.ClientSession() as session:
        client = toutsurmoneau.AsyncClient(username=args.username, password=args.password,
                                           meter_id=args.meter_id, provider=args.provider, session=session)
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
        yaml.dump(data, sys.stdout)


if __name__ == '__main__':
    sys.exit(command_line())
