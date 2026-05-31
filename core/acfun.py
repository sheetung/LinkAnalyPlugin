import re
from typing import Dict, Any

from .utils import format_count, async_request


class AcFunParser:
    def __init__(self, plugin=None):
        self.plugin = plugin

    def get_patterns(self):
        return [
            r"www\.acfun\.cn/v/(\w+)",
            r"acfun\.cn/v/(\w+)"
        ]

    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理AcFun链接解析，返回解析结果"""
        video_id = match.group(1)
        video_url = f"https://www.acfun.cn/v/{video_id}"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = await async_request("get", video_url, headers=headers, timeout=10)

            if resp.status_code != 200:
                raise ValueError(f"AcFun page returned {resp.status_code}")

            page_content = resp.text

            # 提取标题
            title = "AcFun视频"
            keywords_match = re.search(r'<meta name="keywords" content="(.*?)"', page_content)
            if keywords_match:
                keywords = keywords_match.group(1)
                if ',' in keywords:
                    keyword_title = keywords.split(',')[0]
                    if keyword_title and keyword_title != "null":
                        title = keyword_title

            if title == "AcFun视频":
                title_match = re.search(r'<title\s*>(.*?)</title>', page_content)
                if title_match:
                    raw_title = title_match.group(1)
                    if " - AcFun弹幕视频网" in raw_title:
                        title = raw_title.split(" - AcFun弹幕视频网")[0]
                    else:
                        title = raw_title

            if title == "AcFun视频":
                video_info_match = re.search(r'window\.videoInfo = (.*?);', page_content, re.DOTALL)
                if video_info_match:
                    video_info_str = video_info_match.group(1)
                    title_matches = re.findall(r'title\":[\"\']?([^\"\']+)[\"\']?', video_info_str)
                    for t in title_matches:
                        if t and t != "noTitle" and t != "null":
                            title = t
                            break

            # 提取封面图片
            image_url = None
            image_match = re.search(r'<meta property="og:image" content="(.*?)"', page_content)
            if image_match:
                image_url = image_match.group(1)

            if not image_url:
                video_info_match = re.search(r'window\.videoInfo = (.*?);', page_content, re.DOTALL)
                if video_info_match:
                    video_info_str = video_info_match.group(1)
                    cover_match = re.search(r'coverUrl":["\']?([^\"\']+)[\"\']?', video_info_str)
                    if cover_match:
                        image_url = cover_match.group(1)

            if not image_url:
                image_match = re.search(r'<meta name="image" content="(.*?)"', page_content)
                if image_match:
                    image_url = image_match.group(1)

            # 提取简介
            desc_match = re.search(r'<meta name="description" content="(.*?)"', page_content)
            description = desc_match.group(1) if desc_match else ""
            desc_line = None
            if description:
                clean_desc = description.replace("\n", " ").strip()
                desc_line = f"📝 简介：{clean_desc[:97]}..." if len(clean_desc) > 100 else f"📝 简介：{clean_desc}"

            # 初始化变量
            view_count = "0"
            danmaku_count = "0"
            up_name = "未知"
            like_count = "0"
            comment_count = "0"
            stow_count = "0"

            # 提取UP主信息
            if keywords_match:
                keywords = keywords_match.group(1)
                up_match = re.search(r',([^,]+?),A站', keywords)
                if up_match:
                    up_name = up_match.group(1)

            # 从window.videoInfo中提取信息
            video_info_match = re.search(r'window\.videoInfo = (.*?);', page_content, re.DOTALL)
            if video_info_match:
                video_info_str = video_info_match.group(1)
                view_match = re.search(r'viewCount":(\d+)', video_info_str)
                if not view_match:
                    view_match = re.search(r'viewCountShow":["\']?(\d+)["\']?', video_info_str)
                if view_match:
                    view_count = view_match.group(1)
                danmaku_match = re.search(r'danmakuCount":(\d+)', video_info_str)
                if not danmaku_match:
                    danmaku_match = re.search(r'danmakuCountShow":["\']?(\d+)["\']?', video_info_str)
                if danmaku_match:
                    danmaku_count = danmaku_match.group(1)
                like_match = re.search(r'likeCount":(\d+)', video_info_str)
                if not like_match:
                    like_match = re.search(r'likeCountShow":["\']?(\d+)["\']?', video_info_str)
                if like_match:
                    like_count = like_match.group(1)
                comment_match = re.search(r'commentCount":(\d+)', video_info_str)
                if not comment_match:
                    comment_match = re.search(r'commentCountShow":["\']?(\d+)["\']?', video_info_str)
                if not comment_match:
                    comment_match = re.search(r'commentCountRealValue":(\d+)', video_info_str)
                if comment_match:
                    comment_count = comment_match.group(1)
                stow_match = re.search(r'stowCount":(\d+)', video_info_str)
                if not stow_match:
                    stow_match = re.search(r'stowCountShow":["\']?(\d+)["\']?', video_info_str)
                if stow_match:
                    stow_count = stow_match.group(1)

            # 构建消息
            message_acfun = [
                f"🎬 AcFun 视频 | {title}",
                f"👤 UP主：{up_name}"
            ]

            if desc_line:
                message_acfun.append(desc_line)

            message_acfun.extend([
                f"👁️ 播放：{format_count(int(view_count))}  "
                f"💬 弹幕：{format_count(int(danmaku_count))}",
                f"👍 点赞：{format_count(int(like_count))}  "
                f"💬 评论：{format_count(int(comment_count))}",
                f"⭐ 收藏：{format_count(int(stow_count))}",
                "─" * 3,
                f"🔗 {video_url}"
            ])

            return {
                "success": True,
                "title": title,
                "image_url": image_url,
                "message": "\n".join(message_acfun)
            }

        except Exception:
            return {
                "success": False,
                "message": "❌ AcFun 视频解析失败，请稍后重试"
            }
