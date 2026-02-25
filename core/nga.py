import re
import requests
from typing import Dict, Any

class NGAParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r"nga\.178\.com/read\?tid=(\d+)",
            r"bbs\.nga\.cn/read\?tid=(\d+)",
            r"ngabbs\.com/read\?tid=(\d+)",
            r"nga\.178\.com/thread-(\d+)-(\d+)-(\d+)\.html",
            r"bbs\.nga\.cn/thread-(\d+)-(\d+)-(\d+)\.html",
            r"ngabbs\.com/thread-(\d+)-(\d+)-(\d+)\.html"
        ]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理NGA链接解析，返回解析结果"""
        try:
            # 提取帖子ID
            if "tid=" in match.group(0):
                # 格式1: nga.178.com/read?tid=123456 或 ngabbs.com/read?tid=123456
                thread_id = match.group(1)
            else:
                # 格式2: nga.178.com/thread-123456-1-1.html 或 ngabbs.com/thread-123456-1-1.html
                thread_id = match.group(1)
            
            # 构建完整的NGA URL
            url = f"https://nga.178.com/read.php?tid={thread_id}"
            
            # 添加完整的请求头，模拟真实浏览器访问
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://ngabbs.com/",
                "Cache-Control": "max-age=0"
            }
            
            # 获取页面内容
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                raise ValueError(f"NGA page returned {resp.status_code}")
            
            # 提取NGA信息
            page_content = resp.text
            
            # 提取标题
            title = "NGA帖子"
            title_match = re.search(r'<title>(.*?)\s*-\s*NGA玩家社区</title>', page_content)
            if title_match:
                title = title_match.group(1)
            
            # 提取作者信息
            author = "未知作者"
            author_match = re.search(r'作者:\s*<a[^>]+>(.*?)</a>', page_content)
            if not author_match:
                author_match = re.search(r'作者:\s*(.*?)\s*&nbsp;', page_content)
            if author_match:
                author = author_match.group(1)
            
            # 提取回复数和浏览量
            reply_count = 0
            view_count = 0
            stats_match = re.search(r'回复:\s*(\d+)\s*&nbsp;\s*浏览:\s*(\d+)', page_content)
            if stats_match:
                reply_count = int(stats_match.group(1))
                view_count = int(stats_match.group(2))
            
            # 提取板块信息
            forum = "未知板块"
            forum_match = re.search(r'板块:\s*<a[^>]+>(.*?)</a>', page_content)
            if forum_match:
                forum = forum_match.group(1)
            
            # 构建消息
            message_nga = [
                f"📖 NGA 帖子 | {title}",
                f"👤 作者：{author}",
                f"🏷️ 板块：{forum}",
                f"💬 回复：{self._format_count(reply_count)}  "
                f"👁️ 浏览：{self._format_count(view_count)}",
                "─" * 3,
                f"🔗 {url}"
            ]

            return {
                "success": True,
                "title": title,
                "image_url": None,  # NGA帖子通常没有封面图片
                "message": "\n".join(message_nga)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"❌ NGA 帖子解析失败，请稍后重试：{str(e)}"
            }
