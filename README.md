# py-mon-eau

Version 0.0.21

Get your water meter data from your online Suez account (<www.toutsurmoneau.fr>) as well as other sites using the same interface.

Two Classes are provided:

- `Client` is a legacy synchronous client, compatible with module `pySuez`
- `AsyncClient` is an asynchronous client

## Installation

```bash
pip install toutsurmoneau
```

## CLI Usage

```bash
toutsurmoneau [-h] -u _user_name_here_ -p _password_here_ [-c _meter_id_] [-e _action_]
```

## API Usage

### Async use

```python
import toutsurmoneau
import aiohttp
import asyncio


async def the_job():
    async with aiohttp.ClientSession() as session:
        obj = toutsurmoneau.AsyncClient(
            username='_username_here_', password='_password_here_', session=session)
        return await obj.async_contracts()

print(f">>{asyncio.run(the_job())}")
```

### Sync use

```python
import toutsurmoneau

client = toutsurmoneau.Client('_username_here_', '_password_here_')

print(f">>{client.contracts()}")
```

The sync object returns the same values as `pySuez`.

## History

This module is inspired from [pySuez from Ooii](https://github.com/ooii/pySuez) itself inspired by [domoticz sensor](https://github.com/Sirus10/domoticz) and [pyLinky](https://github.com/pirionfr/pyLinky).
