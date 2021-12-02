import asyncio

from spider import run as run_spider
from timer import send_loop
from push import push_loop
from scanner import scanner_loop


async def main():
    await asyncio.gather(run_spider(), send_loop(), push_loop(), scanner_loop())
    # await asyncio.gather(run_spider(), send_loop(), push_loop())


if __name__ == "__main__":
    asyncio.run(main())
