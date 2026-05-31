import re
from typing import Optional, Dict, Any

from .utils import format_count, async_request


class BilibiliParser:
    def __init__(self, plugin=None):
        self.plugin = plugin

    def get_patterns(self):
        return [
            r"www\.bilibili\.com/video/(BV\w+)",
            r"b23\.tv/(\w+)",
            r"www\.bilibili\.com/video/av(\d+)"
        ]

    async def _resolve_short_url(self, short_id: str) -> Optional[str]:
        """解析 b23.tv 短链接，获取真实的 BV 号"""
        try:
            resp = await async_request(
                "get",
                f"https://b23.tv/{short_id}",
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=True,
                timeout=10
            )
            match = re.search(r"bilibili\.com/video/(BV\w+)", resp.url)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理B站链接解析，返回解析结果"""
        matched_text = match.group(0)
        video_id = match.group(1)

        if "b23.tv" in matched_text and not video_id.startswith("BV"):
            real_bvid = await self._resolve_short_url(video_id)
            if real_bvid:
                video_id = real_bvid
            else:
                return {
                    "success": False,
                    "message": "❌ 短链接解析失败，请稍后重试"
                }

        id_type = "BV" if video_id.startswith("BV") else "av"

        api_url = (
            f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
            if id_type == "BV"
            else f"https://api.bilibili.com/x/web-interface/view?aid={video_id}"
        )

        try:
            resp = await async_request("get", api_url, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if data["code"] != 0:
                raise ValueError("Bilibili API error")

            video_data = data['data']
            stat_data = video_data['stat']

            description = video_data.get('desc') or video_data.get('dynamic', '')
            desc_line = None
            if isinstance(description, str) and len(description) > 0:
                clean_desc = description.replace("\n", " ").strip()
                desc_line = f"📝 简介：{clean_desc[:97]}..." if len(clean_desc) > 100 else f"📝 简介：{clean_desc}"

            message_b = [
                f"📺 Bilibili 视频 | {video_data['title']}",
                f"👤 UP主：{video_data['owner']['name']}",
            ]

            if desc_line:
                message_b.append(desc_line)

            message_b.extend([
                f"💖 {format_count(stat_data.get('like', 0))}  "
                f"🪙 {format_count(stat_data.get('coin', 0))}  "
                f"⭐ {format_count(stat_data.get('favorite', 0))}",
                f"👁️ 播放：{format_count(stat_data.get('view', 0))}  "
                f"💬 评论：{format_count(stat_data.get('reply', 0))}  "
                f"💬 弹幕：{format_count(stat_data.get('danmaku', 0))}",
                "─" * 3,
                f"🔗 https://www.bilibili.com/video/{video_id}"
            ])

            return {
                "success": True,
                "title": video_data['title'],
                "image_url": video_data['pic'],
                "message": "\n".join(message_b)
            }

        except Exception:
            return {
                "success": False,
                "message": "❌ 视频解析失败，请稍后重试"
            }
