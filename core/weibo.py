import re
import requests
from typing import Dict, Any

class WeiboParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r"weibo\.com/\d+/([a-zA-Z0-9]+)",
            r"weibo\.com/u/\d+",
            r"weibo\.com/\d+",
            r"sina\.weibo\.com/\d+/([a-zA-Z0-9]+)",
            r"weibo\.cn/\d+/([a-zA-Z0-9]+)"
        ]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理微博链接解析，返回解析结果"""
        try:
            # 构建完整的微博URL
            if "weibo.com" in match.group(0):
                url = f"https://{match.group(0)}"
            else:
                url = f"https://weibo.com{match.group(0)}"
            
            # 添加完整的请求头，模拟手机浏览器访问
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            # 获取页面内容
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                raise ValueError(f"Weibo page returned {resp.status_code}")
            
            # 提取微博信息
            page_content = resp.text
            
            # 提取标题/内容
            content = "微博内容"
            
            # 1. 尝试从微博页面的核心内容区域提取
            # 查找微博正文区域 - 更通用的选择器
            text_match = re.search(r'<div[^>]+class=["\'].*?WB_text.*?["\'][^>]*>(.*?)</div>', page_content, re.DOTALL)
            if text_match:
                text_content = text_match.group(1)
                # 移除HTML标签
                clean_text = re.sub(r'<[^>]+>', '', text_content)
                # 移除多余空白字符
                content = ' '.join(clean_text.split())
                # 移除开头的用户名（如果有）
                if "：" in content:
                    content = content.split("：", 1)[1]
            
            # 2. 尝试从微博的JSON数据中提取
            if content == "微博内容":
                # 查找包含微博数据的脚本
                script_match = re.search(r'\$CONFIG\s*=\s*(\{[^;]+\});', page_content, re.DOTALL)
                if not script_match:
                    script_match = re.search(r'FM\.view\((\{[^;]+\})\);', page_content, re.DOTALL)
                if script_match:
                    script_content = script_match.group(1)
                    # 尝试提取内容
                    content_match = re.search(r'content\s*:\s*["\']([^"\']+)["\']', script_content)
                    if content_match:
                        content = content_match.group(1)
            
            # 3. 尝试从og:description提取
            if content == "微博内容":
                desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', page_content)
                if not desc_match:
                    desc_match = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']', page_content)
                if desc_match:
                    content = desc_match.group(1)
            
            # 4. 尝试从og:title提取
            if content == "微博内容":
                title_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', page_content)
                if title_match:
                    content = title_match.group(1)
            
            # 提取用户信息
            user_name = "未知用户"
            
            # 1. 尝试从微博页面的用户信息区域提取
            user_match = re.search(r'<a[^>]+href=["\']/\d+["\'][^>]+class=["\'].*?W_f14.*?W_fb.*?["\'][^>]*>(.*?)</a>', page_content)
            if not user_match:
                user_match = re.search(r'<a[^>]+href=["\']/\d+["\'][^>]*>(.*?)</a>', page_content)
            if user_match:
                user_name = user_match.group(1)
                # 移除HTML标签
                user_name = re.sub(r'<[^>]+>', '', user_name)
                # 移除多余空白字符
                user_name = ' '.join(user_name.split())
            
            # 2. 尝试从微博正文开头提取用户名
            if user_name == "未知用户" and "：" in content:
                user_name = content.split("：", 1)[0]
                content = content.split("：", 1)[1]
            
            # 提取图片
            image_url = None
            
            # 1. 尝试从og:image提取
            image_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']', page_content)
            if image_match:
                image_url = image_match.group(1)
            
            # 2. 尝试从页面中提取图片
            if not image_url:
                # 查找微博图片
                pic_match = re.search(r'<div[^>]+class=["\']WB_pic[^>]*>.*?<img[^>]+src=["\'](https?://[^"\']+)["\']', page_content, re.DOTALL)
                if not pic_match:
                    # 查找所有图片
                    pic_match = re.search(r'<img[^>]+src=["\'](https?://wx[0-9]+\.sinaimg\.cn/[^"\']+)["\']', page_content)
                if pic_match:
                    image_url = pic_match.group(1)
            
            # 提取统计信息（点赞、评论、转发）
            like_count = 0
            comment_count = 0
            repost_count = 0
            
            # 尝试从页面中提取统计信息
            # 提取评论数
            comment_match = re.search(r'评论\[(\d+)\]', page_content)
            if not comment_match:
                comment_match = re.search(r'\d+\s*评论', page_content)
                if comment_match:
                    comment_text = comment_match.group(0)
                    comment_count = int(re.search(r'\d+', comment_text).group(0))
            else:
                comment_count = int(comment_match.group(1))
            
            # 提取转发数
            repost_match = re.search(r'转发\[(\d+)\]', page_content)
            if not repost_match:
                repost_match = re.search(r'\d+\s*转发', page_content)
                if repost_match:
                    repost_text = repost_match.group(0)
                    repost_count = int(re.search(r'\d+', repost_text).group(0))
            else:
                repost_count = int(repost_match.group(1))
            
            # 提取点赞数
            like_match = re.search(r'赞\[(\d+)\]', page_content)
            if not like_match:
                like_match = re.search(r'\d+\s*赞', page_content)
                if like_match:
                    like_text = like_match.group(0)
                    like_count = int(re.search(r'\d+', like_text).group(0))
            else:
                like_count = int(like_match.group(1))
            
            # 构建消息
            message_weibo = [
                f"📱 微博 | {content[:50]}..." if len(content) > 50 else f"📱 微博 | {content}",
                f"👤 用户：{user_name}"
            ]
            
            # 添加统计信息
            message_weibo.extend([
                f"👍 点赞：{self._format_count(like_count)}  "
                f"💬 评论：{self._format_count(comment_count)}  "
                f"↗️ 转发：{self._format_count(repost_count)}",
                "─" * 3,
                f"🔗 {url}"
            ])

            return {
                "success": True,
                "title": content[:50] + "..." if len(content) > 50 else content,
                "image_url": image_url,
                "message": "\n".join(message_weibo)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 微博解析失败，请稍后重试：{str(e)}"
            }
