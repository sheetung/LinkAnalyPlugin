import re
import requests
import base64
from typing import Optional, Tuple, Dict, Any

class ScreenshotParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
        self.enable_github_gitee = True
        self.enable_bilibili = True
        self.enable_douyin = True
        
        if plugin:
            self.enable_github_gitee = plugin.get_config().get("enable_github_gitee", True)
            self.enable_bilibili = plugin.get_config().get("enable_bilibili", True)
            self.enable_douyin = plugin.get_config().get("enable_douyin", True)
    
    def get_patterns(self):
        return [r"(https?://[^\s]+)"]
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """使用 screenshotsnap.com API 获取网站截图，返回解析结果"""
        url = match.group(1)

        # 排除已被其他处理器处理的链接
        excluded_patterns = []
        if self.enable_bilibili:
            excluded_patterns.extend([r"bilibili\.com", r"b23\.tv"])
        if self.enable_github_gitee:
            excluded_patterns.extend([
                r"github\.com",
                r"gitee\.com"
            ])
        if self.enable_douyin:
            excluded_patterns.extend([r"douyin\.com", r"v\.douyin\.com"])
        for pattern in excluded_patterns:
            if re.search(pattern, url):
                return {"success": False, "skip": True}

        try:
            # 调用 screenshotsnap API 获取截图
            api_url = f"https://screenshotsnap.com/api/screenshot?url={url}&format=webp"
            resp = requests.get(api_url, timeout=30)

            if resp.status_code != 200:
                raise ValueError(f"Screenshot API returned {resp.status_code}")

            # 检查返回的是否是图片
            content_type = resp.headers.get('Content-Type', '')
            if 'image' not in content_type:
                raise ValueError("API did not return an image")

            # 由于 API 返回的是二进制图片，我们需要使用 base64
            image_base64 = base64.b64encode(resp.content).decode('utf-8')

            return {
                "success": True,
                "title": f"网站截图 | {url}",
                "image_base64": image_base64,
                "message": f"🌐 网站截图 | {url}"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 网站截图获取失败 | {url}\n手动访问试试吧！"
            }