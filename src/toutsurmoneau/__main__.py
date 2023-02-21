import toutsurmoneau
import argparse
import sys
import datetime


def command_line():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', required=True,
                        help='Suez username')
    parser.add_argument('-p', '--password',
                        required=True, help='Password')
    parser.add_argument('-c', '--counter_id',
                        required=False, help='Counter Id')
    parser.add_argument('-P', '--provider',
                        required=False, help='Provider name')
    parser.add_argument('-e', '--execute',
                        required=False, help='Command to execute')

    args = parser.parse_args()

    client = toutsurmoneau.ToutSurMonEau(args.username, args.password,
                                         args.counter_id, args.provider, auto_close=False)
    command=args.execute or 'attributes'

    try:
        client.update()
    except BaseException as exp:
        print(exp)
        return 1
    finally:
        client.close_session()
    if command == 'attributes':
        data = client.attributes
    elif command == 'contracts':
        data = client.contracts()
    elif command == 'total_volume':
        data = client.total_volume()
    elif command == 'monthly_recent':
        data = client.monthly_recent()
    elif command == 'daily_for_month':
        data = client.daily_for_month(datetime.date.today())
    elif command == 'check_credentials':
        data = client.check_credentials()
    elif command == 'state':
        data = client.state
    else:
        raise Exception('No such command: '+command)
    print(data)
    return 0


if __name__ == '__main__':
    sys.exit(command_line())
