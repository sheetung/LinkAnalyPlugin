import re
import requests
from typing import Optional, Dict, Any, Tuple

class BilibiliParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r"www\.bilibili\.com/video/(BV\w+)",
            r"b23\.tv/(BV\w+)",
            r"www\.bilibili\.com/video/av(\d+)"
        ]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理B站链接解析，返回解析结果"""
        id_type = "BV" if "BV" in match.group(0) else "av"
        video_id = match.group(1)

        api_url = (
            f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
            if id_type == "BV"
            else f"https://api.bilibili.com/x/web-interface/view?aid={video_id}"
        )

        try:
            resp = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if data["code"] != 0:
                raise ValueError("Bilibili API error")

            video_data = data['data']
            stat_data = video_data['stat']

            # 处理描述信息
            description = video_data.get('desc') or video_data.get('dynamic', '')
            desc_line = None
            if isinstance(description, str) and len(description) > 0:
                # 移除换行符并限制长度
                clean_desc = description.replace("\n", " ").strip()
                desc_line = f"📝 简介：{clean_desc[:97]}..." if len(clean_desc) > 100 else f"📝 简介：{clean_desc}"

            # 构建消息
            message_b = [
                f"📺 Bilibili 视频 | {video_data['title']}",
                f"👤 UP主：{video_data['owner']['name']}",
            ]

            if desc_line:
                message_b.append(desc_line)

            message_b.extend([
                f"💖 {self._format_count(stat_data.get('like', 0))}  "
                f"🪙 {self._format_count(stat_data.get('coin', 0))}  "
                f"⭐ {self._format_count(stat_data.get('favorite', 0))}",
                f"👁️ 播放：{self._format_count(stat_data.get('view', 0))}  "
                f"💬 评论：{self._format_count(stat_data.get('reply', 0))}  "
                f"💬 弹幕：{self._format_count(stat_data.get('danmaku', 0))}",
                "─" * 3,
                f"🔗 https://www.bilibili.com/video/{video_id}"
            ])

            return {
                "success": True,
                "title": video_data['title'],
                "image_url": video_data['pic'],
                "message": "\n".join(message_b)
            }

        except Exception as e:
            return {
                "success": False,
                "message": "❌ 视频解析失败，请稍后重试"
            }