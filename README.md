# py-mon-eau

Version 0.0.9

Get your water counter data from your Suez account (<www.toutsurmoneau.fr>)

## Installation

```bash
pip install toutsurmoneau
```

## CLI Usage

```bash
toutsurmoneau -u _user_name_here_ -p _password_here_
```

## API Usage

```python
import toutsurmoneau

client = toutsurmoneau.ToutSurMonEau('_user_name_here_', '_password_here_')

print(client.total_volume())
```

## History

This module is inspired from [Ooii's pySuez](https://github.com/ooii/pySuez) itself inspired by [domoticz sensor](https://github.com/Sirus10/domoticz) and [pyLinky](https://github.com/pirionfr/pyLinky).
