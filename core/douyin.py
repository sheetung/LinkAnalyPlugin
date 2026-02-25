import re
import json
import requests
from typing import Optional, Tuple, Dict, Any

class DouyinParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_patterns(self):
        return [
            r"v\.douyin\.com/([^/]+)/",
            r"www\.douyin\.com/video/([^/]+)/"
        ]
    
    async def handle(self, match: re.Match) -> Dict[str, Any]:
        """处理抖音链接解析，返回解析结果"""
        douyin_url = match.group(0)
        
        # 确保抖音链接包含协议头
        if not douyin_url.startswith(('http://', 'https://')):
            douyin_url = f"https://{douyin_url}"
        
        try:
            # 使用直接解析抖音页面的方法
            return await self._handle_douyin_direct(douyin_url)
        except Exception as e:
            return {
                "success": False,
                "message": f"❌ 抖音解析失败，请稍后重试：{str(e)}"
            }
    
    async def _handle_douyin_direct(self, douyin_url: str) -> Dict[str, Any]:
        """直接解析抖音页面获取信息，返回解析结果"""
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
        
        return {
            "success": True,
            "title": title,
            "image_url": cover,
            "message": "\n".join(message_douyin)
        }