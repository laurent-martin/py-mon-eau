import argparse
import sys
import toutsurmoneau


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

    args = parser.parse_args()

    client = toutsurmoneau.ToutSurMonEau(args.username, args.password,
                                         args.counter_id, args.provider, auto_close=False)

    try:
        client.update()
    except BaseException as exp:
        print(exp)
        return 1
    finally:
        client.close_session()
    print(client.attributes)
    return 0


if __name__ == '__main__':
    sys.exit(command_line())
