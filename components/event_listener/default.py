from __future__ import annotations
import re
import json
import requests
from typing import Optional, Tuple

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message


class DefaultEventListener(EventListener):

    async def initialize(self):
        await super().initialize()

        self.screensnap_enabled = self.plugin.get_config().get("screenshotsnap", False)
        self.enable_github_gitee = self.plugin.get_config().get("enable_github_gitee", True)
        self.enable_bilibili = self.plugin.get_config().get("enable_bilibili", True)
        self.enable_douyin = self.plugin.get_config().get("enable_douyin", True)
        
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
        self.link_handlers = {}
        
        # 根据配置添加Bilibili支持
        if self.enable_bilibili:
            self.link_handlers["bilibili"] = {
                "patterns": [
                    r"www\.bilibili\.com/video/(BV\w+)",
                    r"b23\.tv/(BV\w+)",
                    r"www\.bilibili\.com/video/av(\d+)"
                ],
                "handler": self.handle_bilibili
            }
        
        # 根据配置添加GitHub和Gitee支持
        if self.enable_github_gitee:
            self.link_handlers["github"] = {
                "patterns": [r"github\.com/([^/]+)/([^/?#]+)"],
                "handler": self.handle_github
            }
            self.link_handlers["gitee"] = {
                "patterns": [r"gitee\.com/([^/]+)/([^/?#]+)"],
                "handler": self.handle_gitee
            }
        
        # 根据配置添加抖音支持
        if self.enable_douyin:
            self.link_handlers["douyin"] = {
                "patterns": [
                    r"v\.douyin\.com/([^/]+)/",
                    r"www\.douyin\.com/video/([^/]+)/"
                ],
                "handler": self.handle_douyin
            }
        
        # 添加截图支持
        if self.screensnap_enabled:
            self.link_handlers["screenshot"] = {
                "patterns": [r"(https?://[^\s]+)"],
                "handler": self.handle_screenshot,
                "priority": -1  # 最低优先级，作为兜底
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

            # 阻止默认行为
            event_context.prevent_default()

        except Exception as e:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text="❌ 视频解析失败，请稍后重试")
                ])
            )

            # 阻止默认行为
            event_context.prevent_default()

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
            # 阻止默认行为
            event_context.prevent_default()

        except Exception as e:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"❌ {platform} 仓库信息获取失败，请稍后重试")
                ])
            )

            # 阻止默认行为
            event_context.prevent_default()

    # ------------------ 抖音处理 ------------------
    async def handle_douyin(self, event_context: context.EventContext, match: re.Match):
        """处理抖音链接解析"""
        douyin_url = match.group(0)
        
        # 确保抖音链接包含协议头
        if not douyin_url.startswith(('http://', 'https://')):
            douyin_url = f"https://{douyin_url}"
        
        try:
            # 使用直接解析抖音页面的方法
            await self._handle_douyin_direct(event_context, douyin_url)
            return
        except Exception as e:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"❌ 抖音解析失败，请稍后重试：{str(e)}")
                ])
            )
            event_context.prevent_default()
            return
    
    async def _handle_douyin_direct(self, event_context: context.EventContext, douyin_url: str):
        """直接解析抖音页面获取信息"""
        # 使用CSDN博客提供的请求头
        headers = {
            'user-agent': 'Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36',
            'referer': 'https://www.douyin.com/?is_from_mobile_home=1&recommend=1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        
        # 尝试获取重定向后的URL
        session = requests.Session()
        resp = session.get(douyin_url, headers=headers, allow_redirects=True, timeout=10)
        
        if resp.status_code != 200:
            raise ValueError(f"Douyin page returned {resp.status_code}")
        
        # 从页面中提取视频ID
        video_id_match = re.search(r'/video/([^/]+)/', resp.url)
        if not video_id_match:
            video_id_match = re.search(r'video_id=([^&]+)', resp.url)
        
        if not video_id_match:
            raise ValueError("无法从URL中提取视频ID")
        
        video_id = video_id_match.group(1)
        
        # 构建iesdouyin链接
        ies_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
        ies_resp = requests.get(ies_url, headers=headers, timeout=10)
        
        if ies_resp.status_code != 200:
            raise ValueError(f"IES Douyin page returned {ies_resp.status_code}")
        
        # 从页面中提取window._ROUTER_DATA
        data_match = re.search(r'window\._ROUTER_DATA = (.*?)</script>', ies_resp.text)
        if not data_match:
            raise ValueError("无法从页面中提取ROUTER_DATA")
        
        data = data_match.group(1)
        json_data = json.loads(data)
        
        # 提取视频信息
        item_list = json_data['loaderData']['video_(id)/page']['videoInfoRes']['item_list'][0]
        nickname = item_list['author']['nickname']
        title = item_list['desc']
        video_uri = item_list['video']['play_addr']['uri']
        cover = item_list['video']['cover']['url_list'][0]
        
        # 构建视频播放链接
        video = f"https://www.douyin.com/aweme/v1/play/?video_id={video_uri}" if 'mp3' not in video_uri else video_uri
        
        # 处理描述信息
        desc_line = None
        if isinstance(title, str) and len(title) > 0:
            # 移除换行符并限制长度
            clean_desc = title.replace("\n", " ").strip()
            desc_line = f"📝 简介：{clean_desc[:97]}..." if len(clean_desc) > 100 else f"📝 简介：{clean_desc}"
        
        # 构建消息
        message_douyin = [
            f"🎵 抖音视频",
            f"👤 作者：{nickname}",
        ]
        
        if desc_line:
            message_douyin.append(desc_line)
        
        message_douyin.extend([
            "─" * 3,
            f"🔗 播放链接：{video}",
            f"🔗 原链接：{douyin_url}"
        ])
        
        # 发送消息
        await event_context.reply(
            platform_message.MessageChain([
                platform_message.Image(url=cover),
                platform_message.Plain(text="\n".join(message_douyin))
            ])
        )
        
        # 阻止默认行为
        event_context.prevent_default()

    # ------------------ 网站截图处理 ------------------
    async def handle_screenshot(self, event_context: context.EventContext, match: re.Match):
        """使用 screenshotsnap.com API 获取网站截图"""
        if not self.screensnap_enabled:
            return

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
                return

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
            import base64
            image_base64 = base64.b64encode(resp.content).decode('utf-8')

            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"🌐 网站截图 | {url}\n"),
                    platform_message.Image(base64=image_base64)
                ])
            )

            # 阻止默认行为
            event_context.prevent_default()

        except Exception as e:
            # await event_context.reply(
            #     platform_message.MessageChain([
            #         platform_message.Plain(text=f"❌ 网站截图获取失败：{str(e)}")
            #     ])
            # )
            platform_message.MessageChain([
                    platform_message.Plain(text=f"❌ 网站截图获取失败 | {url}\n手动访问试试吧！"),
                ])
            
            # 阻止默认行为
            event_context.prevent_default()