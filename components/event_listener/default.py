from __future__ import annotations
import re
import requests
from typing import Optional, Tuple

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DefaultEventListener(EventListener):

    def __init__(self):
        super().__init__()

        # 注册消息事件处理
        @self.handler(events.PersonMessageReceived)
        @self.handler(events.GroupMessageReceived)
        async def handler(event_context: context.EventContext):
            msg = str(event_context.event.message_chain).strip()

            # 遍历所有支持平台
            for platform in self.link_handlers.values():
                match = self._match_link(msg, platform["patterns"])
                if match:
                    await platform["handler"](event_context, match)
                    return

        # 定义支持的链接
        self.link_handlers = {
            "bilibili": {
                "patterns": [
                    r"www\.bilibili\.com/video/(BV\w+)",
                    r"b23\.tv/(BV\w+)",
                    r"www\.bilibili\.com/video/av(\d+)"
                ],
                "handler": self.handle_bilibili
            },
            "github": {
                "patterns": [r"github\.com/([^/]+)/([^/?#]+)"],
                "handler": self.handle_github
            },
            "gitee": {
                "patterns": [r"gitee\.com/([^/]+)/([^/?#]+)"],
                "handler": self.handle_gitee
            }
        }

    # ------------------ 工具方法 ------------------
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)

    def _match_link(self, msg: str, patterns: list) -> Optional[re.Match]:
        for pattern in patterns:
            if match := re.search(pattern, msg):
                return match
        return None

    # ------------------ B站处理 ------------------
    async def handle_bilibili(self, event_context: context.EventContext, match: re.Match):
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
                f"💬 评论：{self._format_count(stat_data.get('reply', 0))}",
                "─" * 3,
                f"🔗 https://www.bilibili.com/video/{video_id}"
            ])

            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Image(url=video_data['pic']),
                    platform_message.Plain(text="\n".join(message_b))
                ])
            )

        except Exception as e:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text="❌ 视频解析失败，请稍后重试")
                ])
            )

    # ------------------ GitHub 处理 ------------------
    async def handle_github(self, event_context: context.EventContext, match: re.Match):
        await self._handle_git_repo(event_context, match.groups(), "GitHub",
            api_template="https://api.github.com/repos/{owner}/{repo}")

    # ------------------ Gitee 处理 ------------------
    async def handle_gitee(self, event_context: context.EventContext, match: re.Match):
        await self._handle_git_repo(event_context, match.groups(), "Gitee",
            api_template="https://gitee.com/api/v5/repos/{owner}/{repo}")

    # ------------------ Git平台通用 ------------------
    async def _handle_git_repo(self, event_context: context.EventContext,
                             groups: Tuple[str],
                             platform: str,
                             api_template: str):
        owner, repo = groups
        try:
            resp = requests.get(
                api_template.format(owner=owner, repo=repo),
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            data = resp.json()

            stars = self._format_count(data.get('stargazers_count', 0))
            forks = self._format_count(data.get('forks_count', 0))
            watchers = self._format_count(data.get('watchers_count', 0))

            # 处理描述信息
            description = data.get('description', '')
            if description and len(description) > 0:
                clean_desc = description.replace("\n", " ").strip()
                desc_text = f"📝 {clean_desc[:97]}..." if len(clean_desc) > 100 else f"📝 {clean_desc}"
            else:
                desc_text = "📝 暂无描述"

            # 获取主要编程语言
            language = data.get('language', '未知')

            message_git = [
                f"📦 {platform} 仓库 | {data['name']}",
                f"👤 作者：{owner}",
                desc_text,
                 "─" * 3,
                f"⭐ {stars} | 🍴 {forks}",
                f"💻 语言：{language}",
                f"🔗 {data['html_url']}"
            ]

            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text="\n".join(message_git))
                ])
            )

        except Exception as e:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"❌ {platform} 仓库信息获取失败，请稍后重试")
                ])
            )