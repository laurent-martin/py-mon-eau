# py-mon-eau

Version 0.0.14

Get your water meter data from your online Suez account (<www.toutsurmoneau.fr>)

## Installation

```bash
pip install toutsurmoneau
```

## CLI Usage

```bash
toutsurmoneau [-h] -u _user_name_here_ -p _password_here_ [-c _meter_id_] [-e _action_]
```

## API Usage

```python
import toutsurmoneau

client = toutsurmoneau.ToutSurMonEau('_user_name_here_', '_password_here_')

print(client.latest_meter_reading())
```

The object tries to mimic `pySuez` when option `compatibility` = `True`.

## History

This module is inspired from [pySuez from Ooii](https://github.com/ooii/pySuez) itself inspired by [domoticz sensor](https://github.com/Sirus10/domoticz) and [pyLinky](https://github.com/pirionfr/pyLinky).
