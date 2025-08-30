import aiohttp
import json
import re
import asyncio
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from aiocqhttp import CQHttp
from astrbot.api import logger

# --- Utility Functions from Template ---

def _generate_gtk(skey: str) -> str:
    """Generate QQ Qzone gtk from skey."""
    hash_val = 5381
    for ch in skey:
        hash_val += (hash_val << 5) + ord(ch)
    return str(hash_val & 0x7FFFFFFF)

# --- Auth Dataclass from Template ---

@dataclass(slots=True)
class _Auth:
    uin: int
    skey: str
    p_skey: str
    gtk: str
    gtk2: str # Added gtk2 for p_skey
    p_uin: int

class QZoneAPI:
    """
    QQ空间动态API封装
    Modified to use implicit authentication via the bot's client object.
    """
    
    def __init__(self):
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ssl=False),
            timeout=aiohttp.ClientTimeout(total=10),
        )
        self._auth: Optional[_Auth] = None
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

    async def login(self, client: CQHttp) -> bool:
        """Login to Qzone using the bot's credentials."""
        if self._auth is not None:
            return True

        try:
            cookie_str = (await client.get_cookies(domain="qzone.qq.com")).get("cookies", "")
            if not cookie_str:
                cookie_str = (await client.get_cookies(domain="user.qzone.qq.com")).get("cookies", "")

            cookies = {k: v.value for k, v in SimpleCookie(cookie_str).items()}

            skey = cookies.get("skey", "")
            p_skey = cookies.get("p_skey", "")
            uin_str = cookies.get("uin", "0")
            p_uin_str = cookies.get("p_uin", uin_str)

            uin = int(uin_str[1:]) if uin_str.startswith('o') else int(uin_str)
            p_uin = int(p_uin_str[1:]) if p_uin_str.startswith('o') else int(p_uin_str)

            if not all((skey, p_skey, uin)):
                logger.error("QQ空间Cookie关键信息缺失 (skey, p_skey, uin)")
                return False

            self._auth = _Auth(
                uin=uin,
                skey=skey,
                p_skey=p_skey,
                gtk=_generate_gtk(skey),
                gtk2=_generate_gtk(p_skey), # Correctly generate gtk from p_skey
                p_uin=p_uin
            )
            logger.info(f"QQ空间隐式登录成功: uin={self._auth.uin}")
            return True
        except Exception as e:
            logger.error(f"QQ空间隐式登录失败: {e}")
            return False

    @property
    def _raw_cookies(self) -> Dict[str, str]:
        if self._auth is None:
            return {}
        return {
            "uin": f"o{self._auth.uin}",
            "p_uin": f"o{self._auth.p_uin}",
            "skey": self._auth.skey,
            "p_skey": self._auth.p_skey,
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Dict[str, Any] | None = None,
        data: Dict[str, Any] | None = None,
        timeout: int = 10,
    ) -> Dict[str, Any]:
        """aiohttp request wrapper."""
        headers = {
            'User-Agent': self.user_agent,
            'Referer': f'https://user.qzone.qq.com/{self._auth.uin if self._auth else ""}',
            'Origin': 'https://user.qzone.qq.com'
        }
        async with self._session.request(
            method.upper(),
            url,
            params=params,
            data=data,
            headers=headers,
            cookies=self._raw_cookies,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"请求失败，状态码: {resp.status}")
            text = await resp.text()
            if m := re.search(r"_Callback\s*\(\s*([^{]*(\{.*\})[^)]*)\s*\)", text, re.I | re.S):
                json_str = m.group(2)
            else:
                json_str = text[text.find("{") : text.rfind("}") + 1]
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"无法解析JSON: {text}")
                return {"ret": -1, "msg": "JSONDecodeError", "raw": text}

    async def close_session(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def is_ready(self, client: CQHttp) -> bool:
        """Check if the API is ready to make requests."""
        return await self.login(client)

    async def publish_dynamic(self, client: CQHttp, content: str, images: List[str] = None) -> bool:
        """发布QQ动态 (Corrected based on working template)"""
        if not await self.login(client):
            logger.warning("QQ空间未登录，无法发布动态")
            return False
        
        assert self._auth is not None

        try:
            post_data = {
                'syn_tweet_verson': '1',
                'paramstr': '1',
                'who': '1',
                'con': content,
                'feedversion': '1',
                'ver': '1',
                'ugc_right': '1',
                'to_sign': '0',
                'hostuin': self._auth.uin,
                'code_version': '1',
                'format': 'json',  # CORRECTED: from 'fs' to 'json'
                'qzreferrer': f'https://user.qzone.qq.com/{self._auth.uin}'
            }
            
            # Image handling logic would go here if needed

            params = {
                'g_tk': self._auth.gtk2, # CORRECTED: use gtk2 (from p_skey)
                'uin': self._auth.uin
            }
            url = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6"
            
            response = await self._request("POST", url, params=params, data=post_data)

            if response.get('code') == 0 or response.get('ret') == 0:
                logger.info(f"QQ动态发布成功: {response.get('tid', '')}")
                return True
            else:
                logger.warning(f"QQ动态发布失败: {response}")
                return False
                    
        except Exception as e:
            logger.error(f"发布QQ动态异常: {e}", exc_info=True)
            return False
    
    async def get_recent_dynamics(self, client: CQHttp, target_qq: str, count: int = 10) -> List[Dict]:
        """获取指定用户的最近动态"""
        if not await self.login(client):
            return []
        
        assert self._auth is not None
        
        try:
            params = {
                'uin': target_qq,
                'ftype': 0,
                'sort': 0,
                'pos': 0,
                'num': count,
                'g_tk': self._auth.gtk,
                'code_version': 1,
                'format': 'json',
            }
            
            url = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
            
            response = await self._request("GET", url, params=params)
            
            if response.get('code') == 0:
                msg_list = response.get('msglist', [])
                dynamics = []
                for msg in msg_list:
                    dynamics.append({
                        'tid': msg.get('tid', ''),
                        'content': msg.get('content', ''),
                        'createTime': msg.get('createTime', ''),
                        'uin': msg.get('uin', ''),
                        'name': msg.get('name', ''),
                        'has_comment': len(msg.get('cmtlist', [])) > 0
                    })
                return dynamics
            return []
                    
        except Exception as e:
            logger.error(f"获取用户动态失败: {e}")
            return []
    
    async def comment_dynamic(self, client: CQHttp, dynamic_id: str, owner_qq: str, comment_content: str) -> bool:
        """评论动态"""
        if not await self.login(client):
            return False
        
        assert self._auth is not None
        
        try:
            comment_data = {
                'topicId': f"{owner_qq}_{dynamic_id}__1",
                'feedsType': '100',
                'inCharset': 'utf-8',
                'outCharset': 'utf-8',
                'plat': 'qzone',
                'source': 'ic',
                'hostUin': owner_qq,
                'platformid': '50',
                'uin': self._auth.uin,
                'format': 'fs',
                'ref': 'feeds',
                'content': comment_content,
                'private': '0',
                'paramstr': '1',
                'qzreferrer': f'https://user.qzone.qq.com/{owner_qq}'
            }
            
            params = {'g_tk': self._auth.gtk2} # Use gtk2 for comments too
            url = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_re_feeds"
            
            response = await self._request("POST", url, params=params, data=comment_data)

            if response.get('code') == 0 or response.get('ret') == 0:
                logger.info(f"评论动态成功: {dynamic_id}")
                return True
            else:
                logger.warning(f"评论动态失败: {response}")
                return False
                        
        except Exception as e:
            logger.error(f"评论动态异常: {e}")
            return False