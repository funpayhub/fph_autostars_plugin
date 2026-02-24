__all__ = ['get_mainnet_config']

from aiohttp import ClientSession


async def get_mainnet_config():
    async with ClientSession() as session:
        async with session.get('https://ton.org/global-config.json', raise_for_status=True) as r:
            return await r.json()
