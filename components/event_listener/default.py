from __future__ import annotations
import re
import logging
from typing import Optional, Tuple
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from langbot_plugin.api.definition.components.common.event_listener import EventListener

logger = logging.getLogger(__name__)
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from core import BilibiliParser, GitParser, DouyinParser, ScreenshotParser, AcFunParser, WeiboParser, NGAParser, XHSparser, YoutubeParser


class DefaultEventListener(EventListener):

    async def initialize(self):
        await super().initialize()

        self.block_reply_link_parse = self.plugin.get_config().get("block_reply_link_parse", True)
        self.screensnap_enabled = self.plugin.get_config().get("screenshotsnap", False)
        self.enable_github_gitee = self.plugin.get_config().get("enable_github_gitee", True)
        self.enable_bilibili = self.plugin.get_config().get("enable_bilibili", True)
        self.enable_douyin = self.plugin.get_config().get("enable_douyin", True)
        self.enable_acfun = self.plugin.get_config().get("enable_acfun", True)
        self.enable_weibo = self.plugin.get_config().get("enable_weibo", False)
        self.enable_nga = self.plugin.get_config().get("enable_nga", False)
        self.enable_xhs = self.plugin.get_config().get("enable_xhs", False)
        self.enable_youtube = self.plugin.get_config().get("enable_youtube", True)
        
        # 初始化解析器
        self.bilibili_parser = BilibiliParser(self.plugin)
        self.git_parser = GitParser(self.plugin)
        self.douyin_parser = DouyinParser(self.plugin)
        self.screenshot_parser = ScreenshotParser(self.plugin)
        self.acfun_parser = AcFunParser(self.plugin)
        self.weibo_parser = WeiboParser(self.plugin)
        self.nga_parser = NGAParser(self.plugin)
        self.xhs_parser = XHSparser(self.plugin)
        self.youtube_parser = YoutubeParser(self.plugin)
        
        # 注册消息事件处理
        @self.handler(events.PersonMessageReceived)
        @self.handler(events.GroupMessageReceived)
        async def handler(event_context: context.EventContext):
            msg = str(event_context.event.message_chain).strip()
            # print(f"Received message: {event_context}")

            # 检查是否为回复消息，并获取 Quote 组件
            quote = event_context.event.message_chain.get_first(platform_message.Quote)
            is_reply_with_link = False

            if quote is not None and quote.origin is not None:
                # 检查被引用的原消息中是否包含链接
                origin_msg = str(quote.origin).strip()
                logger.info(f"[LinkAnaly] 检测到 Quote 组件，原消息内容: {origin_msg[:100]}...")
                for platform in self.link_handlers.values():
                    if self._match_link(origin_msg, platform["patterns"]):
                        is_reply_with_link = True
                        logger.info(f"[LinkAnaly] 原消息中包含链接，标记为 is_reply_with_link=True")
                        break

            # 如果是回复消息且原消息包含链接，始终跳过链接解析（防止重复解析）
            if is_reply_with_link:
                logger.info(f"[LinkAnaly] 拦截回复消息中的链接解析，block_reply_link_parse={self.block_reply_link_parse}")
                # 如果开启了拦截，还阻止 AI/TTS 处理
                if self.block_reply_link_parse:
                    logger.info(f"[LinkAnaly] 开关已开启，阻止 AI/TTS 处理")
                    event_context.prevent_default()
                    event_context.prevent_postorder()
                return

            # 如果开启了拦截回复消息中的链接解析
            if self.block_reply_link_parse:
                # 先检查消息中是否包含可识别的链接
                has_link = False
                for platform in self.link_handlers.values():
                    if self._match_link(msg, platform["patterns"]):
                        has_link = True
                        break

                # 只有同时满足「是回复消息」+「包含链接」才拦截
                if has_link:
                    is_reply = (
                        platform_message.At in event_context.event.message_chain
                        or platform_message.Image in event_context.event.message_chain
                    )
                    if is_reply:
                        event_context.prevent_default()
                        event_context.prevent_postorder()
                        return

            # 遍历所有支持平台
            for platform in self.link_handlers.values():
                match = self._match_link(msg, platform["patterns"])
                if match:
                    # 调用解析器处理
                    result = await platform["handler"](match)
                    
                    # 处理解析结果
                    if result.get("skip"):
                        continue
                    
                    if result["success"]:
                        # 构建消息链
                        message_chain = []
                        
                        # 添加图片（如果有）
                        # 对于YouTube，始终不发送图片，避免网络问题
                        if result.get("image_url"):
                            message_chain.append(platform_message.Image(url=result["image_url"]))
                        elif result.get("image_base64"):
                            message_chain.append(platform_message.Image(base64=result["image_base64"]))
                        
                        # 添加文本消息
                        message_chain.append(platform_message.Plain(text=result["message"]))
                        
                        # 发送回复，添加异常处理
                        try:
                            await event_context.reply(
                                platform_message.MessageChain(message_chain)
                            )
                        except Exception as e:
                            # 发送消息失败，记录错误但不中断执行
                            print(f"发送消息失败: {str(e)}")
                    else:
                        # 发送错误消息，添加异常处理
                        try:
                            await event_context.reply(
                                platform_message.MessageChain([
                                    platform_message.Plain(text=result["message"])
                                ])
                            )
                        except Exception as e:
                            # 发送消息失败，记录错误但不中断执行
                            print(f"发送错误消息失败: {str(e)}")
                    
                    # 阻止默认行为
                    event_context.prevent_default()
                    return

        # 定义支持的链接
        self.link_handlers = {}
        
        # 根据配置添加Bilibili支持
        if self.enable_bilibili:
            self.link_handlers["bilibili"] = {
                "patterns": [
                    r"www\.bilibili\.com/video/(BV\w+)",
                    r"b23\.tv/(\w+)",  # 短链接，ID 不一定是 BV 开头
                    r"www\.bilibili\.com/video/av(\d+)"
                ],
                "handler": self.bilibili_parser.handle
            }
        
        # 根据配置添加GitHub和Gitee支持
        if self.enable_github_gitee:
            self.link_handlers["github"] = {
                "patterns": [r"github\.com/([^/]+)/([^/?#]+)"],
                "handler": self.git_parser.handle_github
            }
            self.link_handlers["gitee"] = {
                "patterns": [r"gitee\.com/([^/]+)/([^/?#]+)"],
                "handler": self.git_parser.handle_gitee
            }
        
        # 根据配置添加抖音支持
        if self.enable_douyin:
            self.link_handlers["douyin"] = {
                "patterns": [
                    r"v\.douyin\.com/([^/]+)/",
                    r"www\.douyin\.com/video/([^/]+)/"
                ],
                "handler": self.douyin_parser.handle
            }
        
        # 根据配置添加AcFun支持
        if self.enable_acfun:
            self.link_handlers["acfun"] = {
                "patterns": [
                    r"www\.acfun\.cn/v/(\w+)",
                    r"acfun\.cn/v/(\w+)"
                ],
                "handler": self.acfun_parser.handle
            }
        
        # 根据配置添加微博支持
        if self.enable_weibo:
            self.link_handlers["weibo"] = {
                "patterns": [
                    r"weibo\.com/\d+/([a-zA-Z0-9]+)",
                    r"sina\.weibo\.com/\d+/([a-zA-Z0-9]+)",
                    r"weibo\.cn/\d+/([a-zA-Z0-9]+)"
                ],
                "handler": self.weibo_parser.handle
            }
        
        # 根据配置添加NGA支持
        if self.enable_nga:
            self.link_handlers["nga"] = {
                "patterns": [
                    r"nga\.178\.com/read\?tid=(\d+)",
                    r"bbs\.nga\.cn/read\?tid=(\d+)",
                    r"ngabbs\.com/read\?tid=(\d+)",
                    r"nga\.178\.com/thread-(\d+)-(\d+)-(\d+)\.html",
                    r"bbs\.nga\.cn/thread-(\d+)-(\d+)-(\d+)\.html",
                    r"ngabbs\.com/thread-(\d+)-(\d+)-(\d+)\.html"
                ],
                "handler": self.nga_parser.handle
            }
        
        # 根据配置添加小红书支持
        if self.enable_xhs:
            self.link_handlers["xhs"] = {
                "patterns": [
                    r"xhs\.com/notes/(\d+)",
                    r"xiaohongshu\.com/notes/(\d+)",
                    r"xhs\.com/(explore|home)/(\d+)",
                    r"xiaohongshu\.com/(explore|home)/(\d+)",
                    r"xiaohongshu\.com/discovery/item/(\w+)"
                ],
                "handler": self.xhs_parser.handle
            }
        
        # 根据配置添加YouTube支持
        if self.enable_youtube:
            self.link_handlers["youtube"] = {
                "patterns": [
                    r'www\.youtube\.com/watch\?v=([\w-]{11})',
                    r'youtu\.be/([\w-]{11})',
                    r'youtube\.com/shorts/([\w-]{11})'
                ],
                "handler": self.youtube_parser.handle
            }
        
        # 添加截图支持
        if self.screensnap_enabled:
            self.link_handlers["screenshot"] = {
                "patterns": [r"(https?://[^\s]+)"],
                "handler": self.screenshot_parser.handle,
                "priority": -1  # 最低优先级，作为兜底
            }

    # ------------------ 工具方法 ------------------
    def _match_link(self, msg: str, patterns: list) -> Optional[re.Match]:
        for pattern in patterns:
            if match := re.search(pattern, msg):
                return match
        return None