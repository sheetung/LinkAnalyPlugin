from __future__ import annotations
import re
import logging
import urllib.parse
from typing import Optional, Tuple
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from langbot_plugin.api.definition.components.common.event_listener import EventListener

logger = logging.getLogger(__name__)
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message

from core import BilibiliParser, GitParser, DouyinParser, ScreenshotParser, AcFunParser, WeiboParser, NGAParser, XHSparser, YoutubeParser


class DefaultEventListener(EventListener):

    async def initialize(self):
        await super().initialize()

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
            # 只从 Plain 文本获取当前消息内容，避免 Quote 中的原消息被包含进来
            msg_parts = []
            for component in event_context.event.message_chain:
                if isinstance(component, platform_message.Plain):
                    msg_parts.append(component.text)
            msg = "".join(msg_parts).strip()
            # print(f"Received message: {event_context}")

            # 检查是否为回复消息，并获取原消息中的链接
            quote = event_context.event.message_chain.get_first(platform_message.Quote)
            origin_link_match = None

            if quote is not None and quote.origin is not None:
                # 检查被引用的原消息中是否包含链接
                origin_msg = str(quote.origin).strip()
                logger.info(f"[LinkAnaly] 检测到 Quote 组件，原消息内容: {origin_msg[:150]}...")
                for platform in self.link_handlers.values():
                    origin_match = self._match_link(origin_msg, platform["patterns"])
                    if origin_match:
                        origin_link_match = origin_match
                        logger.info(f"[LinkAnaly] 原消息中包含链接: {origin_match.group(0)}")
                        break

            # 遍历所有支持平台
            for platform in self.link_handlers.values():
                match = self._match_link(msg, platform["patterns"])
                if match:
                    current_link_text = match.group(0)
                    
                    # 如果是回复消息且原消息有链接，检查是否是相同的链接
                    if origin_link_match:
                        origin_link_text = origin_link_match.group(0)
                        # 提取核心链接信息进行比较（只比较域名+路径，忽略协议和查询参数）
                        try:
                            origin_parsed = urllib.parse.urlparse(origin_link_text)
                            current_parsed = urllib.parse.urlparse(current_link_text)
                            
                            # 比较：netloc(域名) + path(路径)
                            origin_key = f"{origin_parsed.netloc}{origin_parsed.path}".rstrip("/")
                            current_key = f"{current_parsed.netloc}{current_parsed.path}".rstrip("/")
                            
                            logger.info(f"[LinkAnaly] 链接对比 - 原: {origin_key} | 当前: {current_key}")
                            
                            if origin_key == current_key:
                                logger.info(f"[LinkAnaly] ✓ 拦截重复链接解析: {current_link_text}")
                                event_context.prevent_default()
                                event_context.prevent_postorder()
                                return
                            else:
                                logger.info(f"[LinkAnaly] ✗ 链接不同，继续解析新链接")
                        except Exception as e:
                            logger.info(f"[LinkAnaly] 链接比较异常: {str(e)}，继续解析")
                    
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