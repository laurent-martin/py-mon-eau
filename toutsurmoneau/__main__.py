import toutsurmoneau
import argparse
import sys
import yaml
import datetime
import logging

# logging.setLevel(logging.DEBUG)



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
        '--compat', action='store_true', default=False)
    parser.add_argument(
        '--debug', action='store_true', default=False)
    parser.add_argument(
        '--doasync', action='store_true', default=False)
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    if args.doasync:
        execute_async(args)
    else:
        execute_sync(args)

def execute_sync(args):
    client = toutsurmoneau.ToutSurMonEau(args.username, args.password,
                                         args.meter_id, args.provider, compatibility=args.compat)
    try:
        if args.execute == 'attributes':
            client.update()
            data = {
                'attr': client.attributes,
                'state': client.state
            }
        elif args.execute == 'check_credentials':
            data = client.check_credentials()
        elif args.execute == 'contracts':
            data = client.contracts()
        elif args.execute == 'meter_id':
            data = client.meter_id()
        elif args.execute == 'latest_meter_reading':
            data = client.latest_meter_reading()
        elif args.execute == 'monthly_recent':
            data = client.monthly_recent()
        elif args.execute == 'daily_for_month':
            if args.data is None:
                test_date = datetime.date.today()
            else:
                test_date = datetime.datetime.strptime(args.data, '%Y%m').date()
            data = client.daily_for_month(test_date)
        else:
            raise Exception('No such command: '+args.execute)
        yaml.dump(data, sys.stdout)
        return 0
    finally:
        client.close_session()

def execute_async(args):
    client = toutsurmoneau_async.ToutSurMonEauAsync(args.username, args.password,
                                         args.meter_id, args.provider, compatibility=args.compat)
    try:
        if args.execute == 'attributes':
            client.update()
            data = {
                'attr': client.attributes,
                'state': client.state
            }
        elif args.execute == 'check_credentials':
            data = client.check_credentials()
        elif args.execute == 'contracts':
            data = client.contracts()
        elif args.execute == 'meter_id':
            data = client.meter_id()
        elif args.execute == 'latest_meter_reading':
            data = client.latest_meter_reading()
        elif args.execute == 'monthly_recent':
            data = client.monthly_recent()
        elif args.execute == 'daily_for_month':
            if args.data is None:
                test_date = datetime.date.today()
            else:
                test_date = datetime.datetime.strptime(args.data, '%Y%m').date()
            data = client.daily_for_month(test_date)
        else:
            raise Exception('No such command: '+args.execute)
        yaml.dump(data, sys.stdout)
        return 0
    finally:
        client.close_session()


if __name__ == '__main__':
    sys.exit(command_line())
