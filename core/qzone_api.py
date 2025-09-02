import aiohttp
import asyncio
import json
from typing import Dict, List, Optional, Any
from urllib.parse import quote
import time
import re
from http.cookies import SimpleCookie

class QzoneAPI:
    """QQ空间API接口"""
    
    def __init__(self):
        self.session = None
        self.cookies = {}
        self.g_tk = None
        self.uin = None
        self.base_url = "https://user.qzone.qq.com"
        self.api_url = "https://h5.qzone.qq.com"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def login(self, client) -> bool:
        """使用QQ客户端登录"""
        try:
            # 获取QQ客户端Cookie
            cookie_str = await client.get_cookies(domain="user.qzone.qq.com")
            if not cookie_str:
                raise RuntimeError("无法获取QQ Cookie")
            
            # 解析Cookie
            self.cookies = {k: v.value for k, v in SimpleCookie(cookie_str).items()}
            
            # 获取关键参数
            self.skey = self.cookies.get("skey", "")
            self.p_skey = self.cookies.get("p_skey", "")
            
            # 解析uin
            uin_str = self.cookies.get("uin", "")
            if uin_str.startswith("o"):
                self.uin = int(uin_str[1:])
            else:
                self.uin = int(uin_str) if uin_str.isdigit() else 0
            
            if not self.uin:
                raise RuntimeError("无法解析用户ID")
            
            # 计算g_tk
            self.g_tk = self._calculate_gtk(self.skey)
            
            # 验证登录状态
            return await self._verify_login()
            
        except Exception as e:
            print(f"QQ空间登录失败: {e}")
            return False
    
    def _calculate_gtk(self, skey: str) -> int:
        """计算g_tk参数"""
        if not skey:
            return 0
        
        hash_val = 5381
        for char in skey:
            hash_val += (hash_val << 5) + ord(char)
        
        return hash_val & 0x7fffffff
    
    async def _verify_login(self) -> bool:
        """验证登录状态"""
        try:
            url = f"{self.api_url}/proxy/domain/r.qzone.qq.com/cgi-bin/user/cgi_personal_card"
            params = {
                "uin": self.uin,
                "g_tk": self.g_tk
            }
            
            async with self.session.get(url, params=params, cookies=self.cookies) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("code", -1) == 0
            
            return False
            
        except Exception:
            return False
    
    async def publish_emotion(self, content: str, images: List[str] = None) -> Optional[str]:
        """发表说说"""
        try:
            # 上传图片
            image_urls = []
            if images:
                image_urls = await self._upload_images(images)
            
            # 构建请求数据
            url = f"{self.api_url}/proxy/domain/qzonestyle.gtimg.cn/qzone/club/417/feed_v7.html"
            params = {
                "g_tk": self.g_tk,
                "uin": self.uin
            }
            
            # 发表说说
            post_url = f"{self.base_url}/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_publish_v6"
            
            data = {
                "syn_tweet_verson": "1",
                "paramstr": "1",
                "pic_template": "",
                "richtype": "",
                "richval": "",
                "special_url": "",
                "subrichtype": "",
                "who": "1",
                "con": content,
                "feedversion": "1",
                "ver": "1",
                "ugc_right": "1",
                "to_tweet": "0",
                "to_video": "0",
                "flg": "1",
                "qzreferrer": f"https://user.qzone.qq.com/{self.uin}"
            }
            
            # 添加图片
            if image_urls:
                data["richtype"] = "1"
                data["richval"] = json.dumps(image_urls)
            
            async with self.session.post(post_url, data=data, cookies=self.cookies) as response:
                result = await response.json()
                
                if result.get("code", -1) == 0:
                    # 返回说说ID
                    return result.get("data", {}).get("tid", "")
                else:
                    print(f"发表说说失败: {result}")
                    return None
                    
        except Exception as e:
            print(f"发表说说异常: {e}")
            return None
    
    async def _upload_images(self, images: List[str]) -> List[Dict]:
        """上传图片到QQ空间"""
        uploaded_urls = []
        
        for image_url in images:
            try:
                # 下载图片
                async with self.session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # 上传图片
                        upload_url = f"{self.api_url}/proxy/domain/up.qzone.qq.com/cgi-bin/upload/cgi_upload_image"
                        
                        form_data = aiohttp.FormData()
                        form_data.add_field('filename', 'image.jpg')
                        form_data.add_field('uploadtype', '1')
                        form_data.add_field('uin', str(self.uin))
                        form_data.add_field('g_tk', str(self.g_tk))
                        form_data.add_field('file', image_data, content_type='image/jpeg')
                        
                        async with self.session.post(upload_url, data=form_data, cookies=self.cookies) as upload_response:
                            upload_result = await upload_response.json()
                            
                            if upload_result.get("code", -1) == 0:
                                img_data = upload_result.get("data", {})
                                uploaded_urls.append({
                                    "url": img_data.get("url", ""),
                                    "width": img_data.get("width", 0),
                                    "height": img_data.get("height", 0)
                                })
            
            except Exception as e:
                print(f"上传图片失败: {e}")
                continue
        
        return uploaded_urls
    
    async def get_emotions(self, num: int = 10) -> List[Dict]:
        """获取说说列表"""
        try:
            url = f"{self.api_url}/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
            params = {
                "uin": self.uin,
                "ftype": "0",
                "sort": "0",
                "pos": "0",
                "num": num,
                "replynum": "100",
                "g_tk": self.g_tk,
                "callback": "_preloadCallback"
            }
            
            async with self.session.get(url, params=params, cookies=self.cookies) as response:
                text = await response.text()
                
                # 解析JSONP响应
                match = re.search(r'_preloadCallback\((.*)\)', text)
                if match:
                    data = json.loads(match.group(1))
                    
                    if data.get("code", -1) == 0:
                        return data.get("msglist", [])
                
                return []
                
        except Exception as e:
            print(f"获取说说列表失败: {e}")
            return []
    
    async def like_emotion(self, tid: str) -> bool:
        """点赞说说"""
        try:
            url = f"{self.api_url}/proxy/domain/qzonestyle.gtimg.cn/qzone/app/mood_v6/cgi-bin/mood_like_v6"
            
            data = {
                "uin": self.uin,
                "tid": tid,
                "op": "1",
                "g_tk": self.g_tk
            }
            
            async with self.session.post(url, data=data, cookies=self.cookies) as response:
                result = await response.json()
                return result.get("code", -1) == 0
                
        except Exception as e:
            print(f"点赞说说失败: {e}")
            return False
    
    async def comment_emotion(self, tid: str, content: str) -> bool:
        """评论说说"""
        try:
            url = f"{self.api_url}/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_comment_v6"
            
            data = {
                "uin": self.uin,
                "tid": tid,
                "content": content,
                "feedtype": "0",
                "ref": "0",
                "richtype": "",
                "richval": "",
                "special_url": "",
                "to_tweet": "0",
                "to_video": "0",
                "g_tk": self.g_tk
            }
            
            async with self.session.post(url, data=data, cookies=self.cookies) as response:
                result = await response.json()
                return result.get("code", -1) == 0
                
        except Exception as e:
            print(f"评论说说失败: {e}")
            return False