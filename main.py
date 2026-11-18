import asyncio, logging
from dataclasses import dataclass
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

URLS = [
    "https://api.bilibili.com/x/web-interface/popular?ps=5",
    "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
    "https://api.bilibili.com/x/web-interface/newlist?rid=1&ps=5",
]

@dataclass
class Result:
    url: str
    status: int
    ok: bool

async def fetch(client: httpx.AsyncClient, url: str) -> Result:
    try:
        resp = await client.get(url, timeout=10)
        return Result(url, resp.status_code, resp.status_code == 200)
    except Exception as e:
        logging.warning("请求失败 %s: %s", url, e)
        return Result(url, 0, False)

async def main() -> None:
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        results = await asyncio.gather(*(fetch(client, u) for u in URLS))
    ok = sum(1 for r in results if r.ok)
    logging.info("完成 %d/%d", ok, len(results))
    for r in results:
        print(r)

if __name__ == "__main__":
    asyncio.run(main())
#dev分支改动