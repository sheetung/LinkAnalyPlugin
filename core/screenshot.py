import re
import base64
from typing import Dict, Any

from .utils import async_request


class ScreenshotParser:
    def __init__(self, plugin=None):
        self.plugin = plugin

    def get_patterns(self):
        return [r"(https?://[^\s]+)"]

    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """使用 screenshotsnap.com API 获取网站截图，返回解析结果"""
        url = match.group(1)

        try:
            api_url = f"https://screenshotsnap.com/api/screenshot?url={url}&format=webp"
            resp = await async_request("get", api_url, timeout=30)

            if resp.status_code != 200:
                raise ValueError(f"Screenshot API returned {resp.status_code}")

            content_type = resp.headers.get('Content-Type', '')
            if 'image' not in content_type:
                raise ValueError("API did not return an image")

            image_base64 = base64.b64encode(resp.content).decode('utf-8')

            return {
                "success": True,
                "title": f"网站截图 | {url}",
                "image_base64": image_base64,
                "message": f"🌐 网站截图 | {url}"
            }

        except Exception:
            return {
                "success": False,
                "message": f"❌ 网站截图获取失败 | {url}\n手动访问试试吧！"
            }
