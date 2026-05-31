import asyncio
import requests


def format_count(count: int) -> str:
    """格式化数字为K单位"""
    if count >= 1000:
        if count % 1000 == 0:
            return f"{count // 1000}K"
        return f"{count / 1000:.1f}K"
    return str(count)


async def async_request(method: str, url: str, **kwargs) -> requests.Response:
    """在线程池中执行同步requests调用，避免阻塞事件循环"""
    return await asyncio.to_thread(
        lambda: getattr(requests, method)(url, **kwargs)
    )
