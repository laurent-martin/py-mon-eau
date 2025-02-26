# py-mon-eau

Version 0.0.27

Get your water meter data from your online Suez account (<www.toutsurmoneau.fr>) as well as other sites managed by Suez and using the same interface.

Two Classes are provided:

- `AsyncClient` is an asynchronous client
- `Client` is a legacy synchronous client, compatible with module `pySuez`

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

This module was inspired from [pySuez from Ooii](https://github.com/ooii/pySuez).

## Dev data

Open developer tools in browser, and select the network tab.
Then apply the following filter:

```text
-nr-data -google -1password -cookiebot -acticdn -xiti -cloudfront -qualtrics
```

## Debugging

As the API is not really public, it changes sometimes, and the module also needs some adjustments.

## Contribution

Release procedure:

```bash
source .venv/bin/activate
make inst
make bumpver
make release
make publish
```
