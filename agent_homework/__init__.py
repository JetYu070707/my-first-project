"""Agent 方向作业 · 任务一：用 asyncio 并发请求多个 HTTP 接口并汇总结果。

结构说明（单文件，方便对照学习记录逐段阅读）：
- Result    : 单条请求结果，不可变数据类，可跨协程安全传递
- fetch_one : 抓一个 URL，异常一律收敛成 Result，不向上抛
- fetch_all : 并发抓一批 URL，Semaphore 限流 + gather 收敛
- summarize : 算成功数、失败数、墙钟耗时
- main      : 命令行入口（argparse）
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import httpx
from dotenv import load_dotenv

DEFAULT_URLS: tuple[str, ...] = (
    "https://api.bilibili.com/x/web-interface/popular?ps=5",
    "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
    "https://api.bilibili.com/x/web-interface/newlist?rid=1&ps=5",
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

logger = logging.getLogger("agent_homework")


@dataclass(frozen=True, slots=True)
class Result:
    """单个 URL 的抓取结果。失败时 status 为 0，原因写进 error。"""

    url: str
    status: int
    ok: bool
    elapsed_ms: float
    size_bytes: int = 0
    error: str | None = None


async def fetch_one(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_s: float,
    semaphore: asyncio.Semaphore,
) -> Result:
    """抓取单个 URL。超时与网络异常都收敛成 Result，绝不向上抛。"""
    async with semaphore:  # 限流：同一时刻最多 N 个请求在飞
        started = time.perf_counter()
        try:
            response = await client.get(url, timeout=timeout_s)
        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - started) * 1000
            logger.warning("超时 %.1fs %s", timeout_s, url)
            return Result(url, 0, False, elapsed_ms=elapsed, error="timeout")
        except httpx.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            logger.warning("请求异常 %s: %s", url, exc)
            return Result(url, 0, False, elapsed_ms=elapsed, error=type(exc).__name__)

        elapsed = (time.perf_counter() - started) * 1000
        body = response.content
        ok = 200 <= response.status_code < 300
        if not ok:
            logger.warning("HTTP %d %s", response.status_code, url)
        return Result(url, response.status_code, ok, elapsed, len(body))


async def fetch_all(
    urls: Sequence[str],
    *,
    concurrency: int = 6,
    timeout_s: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> list[Result]:
    """并发抓取一批 URL，返回顺序与输入一致的 Result 列表。"""
    if not urls:
        raise ValueError("urls 不能为空")

    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency)
    headers = {"User-Agent": user_agent}

    async with httpx.AsyncClient(headers=headers, limits=limits) as client:
        tasks = [fetch_one(client, url, timeout_s=timeout_s, semaphore=semaphore) for url in urls]
        return list(await asyncio.gather(*tasks))


def summarize(results: Sequence[Result], wall_ms: float) -> dict[str, int | float]:
    """把结果算成可打印、可序列化的统计。"""
    ok = sum(1 for r in results if r.ok)
    return {
        "requested": len(results),
        "ok": ok,
        "failed": len(results) - ok,
        "wall_ms": round(wall_ms, 1),
    }


def render(results: Sequence[Result], wall_ms: float) -> str:
    """渲染成终端可读的逐条列表 + 汇总行。"""
    lines: list[str] = []
    for r in results:
        state = "ok" if r.ok else (r.error or "fail")
        lines.append(
            f"[{state:<7}] {r.status:>3}  {r.elapsed_ms:>8.1f}ms  {r.size_bytes:>7}B  {r.url}"
        )
    stats = summarize(results, wall_ms)
    lines.append("-" * 72)
    lines.append(
        f"完成 {stats['ok']}/{stats['requested']}"
        f"（失败 {stats['failed']}），墙钟 {stats['wall_ms']}ms"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-homework",
        description="并发请求多个 HTTP 接口并汇总结果",
    )
    parser.add_argument(
        "-u",
        "--url",
        dest="urls",
        action="append",
        metavar="URL",
        help="目标地址，可重复；不传则用内置的三个 B 站接口",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=int(os.getenv("CONCURRENCY", "6")),
        metavar="N",
        help="最大并发数（默认 6，可用 CONCURRENCY 环境变量覆盖）",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=float(os.getenv("REQUEST_TIMEOUT", "10")),
        metavar="SEC",
        help="单请求超时秒数（默认 10）",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        metavar="PATH",
        nargs="?",
        const="-",
        help="输出 JSON 结果：给路径则写文件，省略值则打印到 stdout",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认 INFO）",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。返回 0 表示全部成功，1 表示有失败，2 表示参数错误。"""
    load_dotenv(override=False)  # 真实环境变量优先于 .env
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        stream=sys.stderr,
    )
    # 第三方库的 INFO 日志太吵（每条请求一行），压到 WARNING 只留本项目的业务日志
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.concurrency < 1:
        logger.error("并发数必须 >= 1，收到 %d", args.concurrency)
        return 2

    urls = args.urls or list(DEFAULT_URLS)
    user_agent = os.getenv("HTTP_USER_AGENT", DEFAULT_USER_AGENT)
    logger.info("开始：%d 个地址，并发 %d，超时 %.1fs", len(urls), args.concurrency, args.timeout)

    started = time.perf_counter()
    try:
        results = asyncio.run(
            fetch_all(
                urls,
                concurrency=args.concurrency,
                timeout_s=args.timeout,
                user_agent=user_agent,
            )
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    wall_ms = (time.perf_counter() - started) * 1000

    stats = summarize(results, wall_ms)
    logger.info("完成 %d/%d，墙钟 %.0fms", stats["ok"], stats["requested"], stats["wall_ms"])
    print(render(results, wall_ms))

    if args.json_path is not None:
        payload = {"summary": stats, "results": [asdict(r) for r in results]}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json_path == "-":
            print(text)
        else:
            with open(args.json_path, "w", encoding="utf-8") as fp:
                fp.write(text + "\n")
            logger.info("JSON 已写入 %s", args.json_path)

    return 0 if stats["failed"] == 0 else 1
