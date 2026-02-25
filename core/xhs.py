import re
import requests
from typing import Dict, Any

class XHSparser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r"xhs\.com/(explore|home)/\d+",
            r"xiaohongshu\.com/(explore|home)/\d+",
            r"xhs\.com/notes/(\d+)",
            r"xiaohongshu\.com/notes/(\d+)",
            r"xiaohongshu\.com/discovery/item/(\w+)"
        ]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理小红书链接解析，返回解析结果"""
        try:
            # 提取笔记ID
            note_id = None
            if "notes/" in match.group(0):
                # 格式: xhs.com/notes/123456
                note_id = match.group(1)
            elif "discovery/item/" in match.group(0):
                # 格式: xiaohongshu.com/discovery/item/699b1179000000001a0242bf
                note_id = match.group(1)
            else:
                # 格式: xhs.com/explore/123456
                note_id = match.group(2)
            
            if not note_id:
                raise ValueError("无法提取小红书笔记ID")
            
            # 构建完整的小红书URL
            if note_id.isdigit():
                # 纯数字ID使用notes格式
                url = f"https://xhs.com/notes/{note_id}"
            else:
                # 字母数字混合ID使用discovery/item格式
                url = f"https://xiaohongshu.com/discovery/item/{note_id}"
            
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
                raise ValueError(f"小红书页面返回 {resp.status_code}")
            
            # 提取小红书信息
            page_content = resp.text
            
            # 提取标题
            title = "小红书笔记"
            # 尝试从多个位置提取标题
            title_match = re.search(r'<title>(.*?)\s*-\s*小红书</title>', page_content)
            if title_match:
                title = title_match.group(1)
            # 尝试从og:title提取
            elif re.search(r'<meta property="og:title" content="(.*?)"', page_content):
                title_match = re.search(r'<meta property="og:title" content="(.*?)"', page_content)
                title = title_match.group(1)
            
            # 提取用户信息
            user_name = "未知用户"
            # 尝试从og:description提取
            user_match = re.search(r'<meta property="og:description" content="(.*?)"', page_content)
            if user_match:
                desc = user_match.group(1)
                # 通常格式为 "用户名的笔记" 或 "用户名分享"
                if "的笔记" in desc:
                    user_name = desc.split("的笔记")[0]
                elif "分享" in desc:
                    user_name = desc.split("分享")[0]
            # 尝试从其他位置提取
            elif re.search(r'"nickname":"(.*?)"', page_content):
                user_match = re.search(r'"nickname":"(.*?)"', page_content)
                user_name = user_match.group(1)
            
            # 提取图片
            image_url = None
            # 尝试从og:image提取
            image_match = re.search(r'<meta property="og:image" content="(.*?)"', page_content)
            if image_match:
                image_url = image_match.group(1)
            # 尝试从其他位置提取
            elif re.search(r'"cover_image":"(.*?)"', page_content):
                image_match = re.search(r'"cover_image":"(.*?)"', page_content)
                image_url = image_match.group(1)
            
            # 提取统计信息（点赞、评论、收藏）
            like_count = 0
            comment_count = 0
            collect_count = 0
            
            # 尝试从页面中提取统计信息
            stats_matches = re.findall(r'(\d+)\s*(赞|评论|收藏)', page_content)
            for count, stat_type in stats_matches:
                if stat_type == "赞":
                    like_count = int(count)
                elif stat_type == "评论":
                    comment_count = int(count)
                elif stat_type == "收藏":
                    collect_count = int(count)
            
            # 尝试从JSON数据中提取统计信息
            if re.search(r'"likes":(\d+)', page_content):
                like_match = re.search(r'"likes":(\d+)', page_content)
                like_count = int(like_match.group(1))
            if re.search(r'"comments":(\d+)', page_content):
                comment_match = re.search(r'"comments":(\d+)', page_content)
                comment_count = int(comment_match.group(1))
            if re.search(r'"collections":(\d+)', page_content):
                collect_match = re.search(r'"collections":(\d+)', page_content)
                collect_count = int(collect_match.group(1))
            
            # 构建消息
            message_xhs = [
                f"📱 小红书 笔记 | {title}",
                f"👤 用户：{user_name}",
                f"👍 点赞：{self._format_count(like_count)}  "
                f"💬 评论：{self._format_count(comment_count)}  "
                f"⭐ 收藏：{self._format_count(collect_count)}",
                "─" * 3,
                f"🔗 {url}"
            ]

            return {
                "success": True,
                "title": title,
                "image_url": image_url,
                "message": "\n".join(message_xhs)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 小红书笔记解析失败，请稍后重试：{str(e)}"
            }
