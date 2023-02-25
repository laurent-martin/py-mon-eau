import toutsurmoneau
import argparse
import sys
import yaml
import datetime


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
                        required=False, help='Provider name')
    parser.add_argument('-e', '--execute',
                        required=False, help='Command to execute (attributes,contracts,meter_id,latest_meter_reading,monthly_recent,daily_for_month,check_credentials)')
    parser.add_argument('--compat', action=argparse.BooleanOptionalAction, default= False)
    args = parser.parse_args()

    client = toutsurmoneau.ToutSurMonEau(args.username, args.password,
                                         args.meter_id, args.provider, auto_close=False, compatibility=args.compat)
    command = args.execute or 'attributes'

    try:
        if command == 'attributes':
            client.update()
            data = {
                'attr': client.attributes,
                'state': client.state
            }
        elif command == 'check_credentials':
            data = client.check_credentials()
        elif command == 'contracts':
            data = client.contracts()
        elif command == 'meter_id':
            data = client.meter_id()
        elif command == 'latest_meter_reading':
            data = client.latest_meter_reading()
        elif command == 'monthly_recent':
            data = client.monthly_recent()
        elif command == 'daily_for_month':
            data = client.daily_for_month(datetime.date.today())
        else:
            raise Exception('No such command: '+command)
        yaml.dump(data, sys.stdout)
        return 0
    # except BaseException as exp:
    #    print(exp)
    #    return 1
    finally:
        client.close_session()


if __name__ == '__main__':
    sys.exit(command_line())
