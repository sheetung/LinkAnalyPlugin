import re
from typing import Dict, Any

from .utils import format_count, async_request


class YoutubeParser:
    def __init__(self, plugin=None):
        self.plugin = plugin

    def get_patterns(self):
        return [
            r'www\.youtube\.com/watch\?v=([\w-]{11})',
            r'youtu\.be/([\w-]{11})',
            r'youtube\.com/shorts/([\w-]{11})'
        ]

    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理YouTube链接解析，返回解析结果"""
        try:
            video_id = match.group(1)
            url = f"https://youtu.be/{video_id}"

            youtube_key = self.plugin.get_config().get("youtube_key", None)
            if not youtube_key:
                return {
                    "success": False,
                    "message": "❌ YouTube 解析需要配置 API Key"
                }

            youtube_proxy = self.plugin.get_config().get("youtube_proxy", None)

            proxies = {}
            if youtube_proxy:
                proxies = {
                    "http": youtube_proxy,
                    "https": youtube_proxy
                }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'
            }

            api_url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={youtube_key}&part=snippet,statistics"
            response = await async_request("get", api_url, headers=headers, proxies=proxies, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"YouTube API 返回 {response.status_code}")

            data = response.json()
            if data['pageInfo']['totalResults'] == 0:
                raise ValueError("视频不存在或无法访问")

            snippet = data['items'][0]['snippet']
            statistics = data['items'][0].get('statistics', {})

            title = snippet.get('title', 'YouTube视频')
            channel_title = snippet.get('channelTitle', '未知频道')
            thumbnail_url = None

            view_count = int(statistics.get('viewCount', 0))
            like_count = int(statistics.get('likeCount', 0))
            comment_count = int(statistics.get('commentCount', 0))

            message_youtube = [
                f"🎬 YouTube 视频 | {title}",
                f"👤 频道：{channel_title}",
                f"👁️ 播放：{format_count(view_count)}  "
                f"👍 点赞：{format_count(like_count)}  "
                f"💬 评论：{format_count(comment_count)}",
                "─" * 3,
                f"🔗 {url}"
            ]

            return {
                "success": True,
                "title": title,
                "image_url": thumbnail_url,
                "message": "\n".join(message_youtube)
            }

        except Exception:
            return {
                "success": False,
                "message": "❌ YouTube 视频解析失败，请稍后重试"
            }
