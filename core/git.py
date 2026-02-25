import re
import requests
from typing import Optional, Tuple, Dict, Any

class GitParser:
    def __init__(self, plugin=None):
        self.plugin = plugin
    
    def get_github_patterns(self):
        return [r"github\.com/([^/]+)/([^/?#]+)"]
    
    def get_gitee_patterns(self):
        return [r"gitee\.com/([^/]+)/([^/?#]+)"]
    
    def _format_count(self, count: int) -> str:
        """格式化数字为K单位"""
        if count >= 1000:
            if count % 1000 == 0:
                return f"{count//1000}K"
            return f"{count/1000:.1f}K"
        return str(count)
    
    async def handle_github(self, match: re.Match) -> Dict[str, Any]:
        return await self._handle_git_repo(match.groups(), "GitHub",
            api_template="https://api.github.com/repos/{owner}/{repo}")
    
    async def handle_gitee(self, match: re.Match) -> Dict[str, Any]:
        return await self._handle_git_repo(match.groups(), "Gitee",
            api_template="https://gitee.com/api/v5/repos/{owner}/{repo}")
    
    async def _handle_git_repo(self, groups: Tuple[str],
                             platform: str,
                             api_template: str) -> Dict[str, Any]:
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

            return {
                "success": True,
                "title": data['name'],
                "message": "\n".join(message_git)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"❌ {platform} 仓库信息获取失败，请稍后重试"
            }