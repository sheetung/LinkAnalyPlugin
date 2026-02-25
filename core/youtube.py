import re
import requests
from typing import Dict, Any

class YoutubeParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r'www\.youtube\.com/watch\?v=([\w-]{11})',
            r'youtu\.be/([\w-]{11})',
            r'youtube\.com/shorts/([\w-]{11})'
        ]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理YouTube链接解析，返回解析结果"""
        try:
            # 提取视频ID
            video_id = match.group(1)
            
            # 构建完整的YouTube URL
            url = f"https://youtu.be/{video_id}"
            
            # 获取YouTube API Key
            youtube_key = self.plugin.get_config().get("youtube_key", None)
            if not youtube_key:
                return {
                    "success": False,
                    "message": "❌ YouTube 解析需要配置 API Key"
                }
            
            # 获取YouTube HTTP代理
            youtube_proxy = self.plugin.get_config().get("youtube_proxy", None)
            
            # 配置代理
            proxies = {}
            if youtube_proxy:
                proxies = {
                    "http": youtube_proxy,
                    "https": youtube_proxy
                }
            
            # 添加请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'
            }
            
            # 调用YouTube API
            api_url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={youtube_key}&part=snippet,statistics"
            response = requests.get(api_url, headers=headers, proxies=proxies, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"YouTube API 返回 {response.status_code}")
            
            # 解析API响应
            data = response.json()
            if data['pageInfo']['totalResults'] == 0:
                raise ValueError("视频不存在或无法访问")
            
            snippet = data['items'][0]['snippet']
            statistics = data['items'][0].get('statistics', {})
            
            # 提取信息
            title = snippet.get('title', 'YouTube视频')
            channel_title = snippet.get('channelTitle', '未知频道')
            # 不处理图片，避免网络问题
            thumbnail_url = None
            
            # 提取统计信息
            view_count = int(statistics.get('viewCount', 0))
            like_count = int(statistics.get('likeCount', 0))
            comment_count = int(statistics.get('commentCount', 0))
            
            # 构建消息
            message_youtube = [
                f"🎬 YouTube 视频 | {title}",
                f"👤 频道：{channel_title}",
                f"👁️ 播放：{self._format_count(view_count)}  "
                f"👍 点赞：{self._format_count(like_count)}  "
                f"💬 评论：{self._format_count(comment_count)}",
                "─" * 3,
                f"🔗 {url}"
            ]

            return {
                "success": True,
                "title": title,
                "image_url": thumbnail_url,
                "message": "\n".join(message_youtube)
            }

        except Exception as e:
            return {
                "success": False,
                # "message": f"❌ YouTube 视频解析失败，请稍后重试：{str(e)}"
                "message": "❌ YouTube 视频解析失败，请稍后重试"
            }
