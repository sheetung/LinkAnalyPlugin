import re
import requests
from typing import Dict, Any

class AcFunParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r"www\.acfun\.cn/v/(\w+)",
            r"acfun\.cn/v/(\w+)"
        ]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理AcFun链接解析，返回解析结果"""
        video_id = match.group(1)
        video_url = f"https://www.acfun.cn/v/{video_id}"

        try:
            # 获取视频页面
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = requests.get(video_url, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                raise ValueError(f"AcFun page returned {resp.status_code}")
            
            # 提取标题
            # 1. 优先从keywords中提取标题（最可靠）
            title = "AcFun视频"
            keywords_match = re.search(r'<meta name="keywords" content="(.*?)"', resp.text)
            if keywords_match:
                keywords = keywords_match.group(1)
                if ',' in keywords:
                    # 第一个逗号前的内容通常是标题
                    keyword_title = keywords.split(',')[0]
                    if keyword_title and keyword_title != "null":
                        title = keyword_title
            
            # 2. 如果从keywords中提取失败，尝试从title标签中提取
            if title == "AcFun视频":
                # 匹配<title>标签，允许标签名后有空格
                title_match = re.search(r'<title\s*>(.*?)</title>', resp.text)
                if title_match:
                    raw_title = title_match.group(1)
                    # 移除可能的后缀
                    if " - AcFun弹幕视频网" in raw_title:
                        title = raw_title.split(" - AcFun弹幕视频网")[0]
                    else:
                        title = raw_title
            
            # 3. 如果前两种方法都失败，尝试从window.videoInfo中提取标题
            if title == "AcFun视频":
                video_info_match = re.search(r'window\.videoInfo = (.*?);', resp.text, re.DOTALL)
                if video_info_match:
                    video_info_str = video_info_match.group(1)
                    # 查找所有可能的title字段，选择非"noTitle"的那个
                    title_matches = re.findall(r'title\":[\"\']?([^\"\']+)[\"\']?', video_info_str)
                    for t in title_matches:
                        if t and t != "noTitle" and t != "null":
                            title = t
                            break
            
            # 提取封面图片
            image_url = None
            # 1. 尝试从og:image中提取
            image_match = re.search(r'<meta property="og:image" content="(.*?)"', resp.text)
            if image_match:
                image_url = image_match.group(1)
            
            # 2. 如果og:image中没有找到，尝试从window.videoInfo中提取
            if not image_url:
                video_info_match = re.search(r'window\.videoInfo = (.*?);', resp.text, re.DOTALL)
                if video_info_match:
                    video_info_str = video_info_match.group(1)
                    # 查找coverUrl字段
                    cover_match = re.search(r'coverUrl":["\']?([^\"\']+)[\"\']?', video_info_str)
                    if cover_match:
                        image_url = cover_match.group(1)
            
            # 3. 如果window.videoInfo中没有找到，尝试从其他meta标签中提取
            if not image_url:
                image_match = re.search(r'<meta name="image" content="(.*?)"', resp.text)
                if image_match:
                    image_url = image_match.group(1)
            
            # 提取简介
            desc_match = re.search(r'<meta name="description" content="(.*?)"', resp.text)
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
            keywords_match = re.search(r'<meta name="keywords" content="(.*?)"', resp.text)
            if keywords_match:
                keywords = keywords_match.group(1)
                up_match = re.search(r',([^,]+?),A站', keywords)
                if up_match:
                    up_name = up_match.group(1)
            
            # 从window.videoInfo中提取信息
            video_info_match = re.search(r'window\.videoInfo = (.*?);', resp.text, re.DOTALL)
            if video_info_match:
                video_info_str = video_info_match.group(1)
                # 提取播放量
                view_match = re.search(r'viewCount":(\d+)', video_info_str)
                if not view_match:
                    view_match = re.search(r'viewCountShow":["\']?(\d+)["\']?', video_info_str)
                if view_match:
                    view_count = view_match.group(1)
                # 提取弹幕数
                danmaku_match = re.search(r'danmakuCount":(\d+)', video_info_str)
                if not danmaku_match:
                    danmaku_match = re.search(r'danmakuCountShow":["\']?(\d+)["\']?', video_info_str)
                if danmaku_match:
                    danmaku_count = danmaku_match.group(1)
                # 提取点赞数
                like_match = re.search(r'likeCount":(\d+)', video_info_str)
                if not like_match:
                    like_match = re.search(r'likeCountShow":["\']?(\d+)["\']?', video_info_str)
                if like_match:
                    like_count = like_match.group(1)
                # 提取评论数
                comment_match = re.search(r'commentCount":(\d+)', video_info_str)
                if not comment_match:
                    comment_match = re.search(r'commentCountShow":["\']?(\d+)["\']?', video_info_str)
                if not comment_match:
                    comment_match = re.search(r'commentCountRealValue":(\d+)', video_info_str)
                if comment_match:
                    comment_count = comment_match.group(1)
                # 提取收藏数
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
            
            # 添加统计信息
            message_acfun.extend([
                f"👁️ 播放：{self._format_count(int(view_count))}  "
                f"💬 弹幕：{self._format_count(int(danmaku_count))}",
                f"👍 点赞：{self._format_count(int(like_count))}  "
                f"💬 评论：{self._format_count(int(comment_count))}",
                f"⭐ 收藏：{self._format_count(int(stow_count))}",
                "─" * 3,
                f"🔗 {video_url}"
            ])

            return {
                "success": True,
                "title": title,
                "image_url": image_url,
                "message": "\n".join(message_acfun)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"❌ AcFun 视频解析失败，请稍后重试：{str(e)}"
            }