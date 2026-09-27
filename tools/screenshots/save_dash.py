import asyncio,aiohttp,ha,yaml,sys
cfg=yaml.safe_load(open(sys.argv[1]))
async def m():
    async with aiohttp.ClientSession() as s:
        a=await ha.token(s)
        async with ha.WS(s,a) as w:
            await w.call(type='lovelace/config/save', config=cfg)
asyncio.run(m())
