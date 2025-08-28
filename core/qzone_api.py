import aiohttp
import json
import re
import random
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urlencode
from astrbot.api import logger


class QZoneAPI:
    """QQ空间动态API封装"""
    
    def __init__(self, config: dict):
        self.config = config
        qzone_config = config.get('qzone_config', {})
        
        self.cookies = qzone_config.get('qq_cookies', '')
        self.user_agent = qzone_config.get('user_agent', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        self.session = None
        self.headers = {
            'User-Agent': self.user_agent,
            'Referer': 'https://user.qzone.qq.com/',
            'Cookie': self.cookies
        }
    
    async def init_session(self):
        """初始化会话"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.cookies and self.user_agent)
    
    async def publish_dynamic(self, content: str, images: List[str] = None) -> bool:
        """发布QQ动态
        
        Args:
            content: 动态文本内容
            images: 图片URL列表
            
        Returns:
            发布是否成功
        """
        if not self.is_configured():
            logger.warning("QQ空间配置不完整，无法发布动态")
            return False
        
        await self.init_session()
        
        try:
            # 这里是一个示例实现，实际的QQ空间API可能需要更复杂的认证和参数
            # 由于QQ空间API变化频繁，这里提供一个框架结构
            
            # 获取必要的参数（如g_tk等）
            params = await self._get_publish_params()
            if not params:
                return False
            
            # 构建发布数据
            post_data = {
                'syn_tweet_verson': '1',
                'paramstr': '1',
                'who': '1',
                'con': content,
                'feedversion': '1',
                'ver': '1',
                'ugc_right': '1',
                'to_sign': '0',
                'hostuin': params.get('hostuin', ''),
                'code_version': '1',
                'format': 'fs',
                'qzreferrer': 'https://user.qzone.qq.com/'
            }
            
            # 如果有图片，添加图片参数
            if images:
                uploaded_pics = []
                for img in images[:9]:  # QQ空间最多9张图
                    pic_info = await self._upload_image(img)
                    if pic_info:
                        uploaded_pics.append(pic_info)
                
                if uploaded_pics:
                    post_data['pic_template'] = ''
                    post_data['richtype'] = '1'
                    post_data['richval'] = ','.join(uploaded_pics)
            
            # 发送发布请求
            url = f"https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_publish_v6"
            
            async with self.session.post(url, headers=self.headers, data=post_data) as response:
                if response.status == 200:
                    result = await response.text()
                    # 解析结果
                    if self._parse_publish_result(result):
                        logger.info("QQ动态发布成功")
                        return True
                    else:
                        logger.warning(f"QQ动态发布失败: {result}")
                        return False
                else:
                    logger.error(f"QQ动态发布请求失败: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"发布QQ动态异常: {e}")
            return False
    
    async def _get_publish_params(self) -> Optional[Dict]:
        """获取发布动态所需的参数"""
        try:
            # 访问QQ空间主页获取必要参数
            url = "https://user.qzone.qq.com/"
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # 提取g_tk等参数
                    params = {}
                    
                    # 提取QQ号
                    uin_match = re.search(r'"uin":"(\d+)"', content)
                    if uin_match:
                        params['hostuin'] = uin_match.group(1)
                    
                    # 提取g_tk（这个算法可能需要根据实际情况调整）
                    skey_match = re.search(r'skey=([^;]+)', self.cookies)
                    if skey_match:
                        skey = skey_match.group(1)
                        params['g_tk'] = self._calculate_gtk(skey)
                    
                    return params
                    
        except Exception as e:
            logger.error(f"获取发布参数失败: {e}")
        
        return None
    
    def _calculate_gtk(self, skey: str) -> str:
        """计算g_tk值"""
        hash_value = 5381
        for char in skey:
            hash_value += (hash_value << 5) + ord(char)
        return str(hash_value & 2147483647)
    
    async def _upload_image(self, image_path: str) -> Optional[str]:
        """上传图片到QQ空间
        
        Args:
            image_path: 图片路径（本地路径或URL）
            
        Returns:
            上传后的图片信息字符串
        """
        try:
            # 这里是图片上传的示例框架
            # 实际实现需要根据QQ空间的上传接口来调整
            
            if image_path.startswith('http'):
                # 网络图片，先下载
                image_data = await self._download_image(image_path)
                if not image_data:
                    return None
            else:
                # 本地图片
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            
            # 上传图片到QQ空间
            upload_url = "https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image"
            
            form_data = aiohttp.FormData()
            form_data.add_field('filename', 'image.jpg')
            form_data.add_field('file', image_data, content_type='image/jpeg')
            
            async with self.session.post(upload_url, headers=self.headers, data=form_data) as response:
                if response.status == 200:
                    result = await response.text()
                    # 解析上传结果，提取图片信息
                    pic_info = self._parse_upload_result(result)
                    return pic_info
                    
        except Exception as e:
            logger.error(f"上传图片失败: {e}")
        
        return None
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载网络图片"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
        return None
    
    def _parse_publish_result(self, result: str) -> bool:
        """解析发布结果"""
        try:
            # QQ空间通常返回类似 _Callback({"code":0,"message":"success"}) 的格式
            if '"code":0' in result or '"ret":0' in result:
                return True
        except Exception as e:
            logger.error(f"解析发布结果失败: {e}")
        return False
    
    def _parse_upload_result(self, result: str) -> Optional[str]:
        """解析图片上传结果"""
        try:
            # 解析上传结果，提取图片ID等信息
            # 这里需要根据实际API响应格式来实现
            import json
            if result.startswith('_Callback('):
                json_str = result[10:-1]
                data = json.loads(json_str)
                if data.get('ret') == 0:
                    return data.get('data', {}).get('url', '')
        except Exception as e:
            logger.error(f"解析上传结果失败: {e}")
        return None
    
    async def get_recent_dynamics(self, target_qq: str, count: int = 10) -> List[Dict]:
        """获取指定用户的最近动态
        
        Args:
            target_qq: 目标用户QQ号
            count: 获取数量
            
        Returns:
            动态列表
        """
        if not self.is_configured():
            return []
        
        await self.init_session()
        
        try:
            # 构建获取动态的URL
            params = {
                'uin': target_qq,
                'format': 'jsonp',
                'num': count,
                'callback': '_Callback'
            }
            
            url = f"https://h5.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6?{urlencode(params)}"
            
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    result = await response.text()
                    return self._parse_dynamics_list(result)
                    
        except Exception as e:
            logger.error(f"获取用户动态失败: {e}")
        
        return []
    
    def _parse_dynamics_list(self, result: str) -> List[Dict]:
        """解析动态列表"""
        dynamics = []
        try:
            # 解析动态���表响应
            if result.startswith('_Callback('):
                json_str = result[10:-1]
                data = json.loads(json_str)
                
                if data.get('code') == 0:
                    msg_list = data.get('msglist', [])
                    for msg in msg_list:
                        dynamic = {
                            'tid': msg.get('tid', ''),
                            'content': msg.get('content', ''),
                            'createTime': msg.get('createTime', ''),
                            'uin': msg.get('uin', ''),
                            'name': msg.get('name', ''),
                            'has_comment': len(msg.get('cmtlist', [])) > 0
                        }
                        dynamics.append(dynamic)
                        
        except Exception as e:
            logger.error(f"解析动态列表失败: {e}")
        
        return dynamics
    
    async def comment_dynamic(self, dynamic_id: str, owner_qq: str, comment_content: str) -> bool:
        """评论动态
        
        Args:
            dynamic_id: 动态ID
            owner_qq: 动态主人QQ号
            comment_content: 评论内容
            
        Returns:
            评论是否成功
        """
        if not self.is_configured():
            return False
        
        await self.init_session()
        
        try:
            # 获取评论所需参数
            params = await self._get_publish_params()
            if not params:
                return False
            
            # 构建评论数据
            comment_data = {
                'content': comment_content,
                'hostUin': owner_qq,
                'topicId': dynamic_id,
                'format': 'json',
                'qzreferrer': f'https://user.qzone.qq.com/{owner_qq}'
            }
            
            url = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_addcomment_ugc"
            
            async with self.session.post(url, headers=self.headers, data=comment_data) as response:
                if response.status == 200:
                    result = await response.text()
                    if self._parse_comment_result(result):
                        logger.info(f"评论动态成功: {dynamic_id}")
                        return True
                    else:
                        logger.warning(f"评论动态失败: {result}")
                        return False
                        
        except Exception as e:
            logger.error(f"评论动态异常: {e}")
        
        return False
    
    def _parse_comment_result(self, result: str) -> bool:
        """解析评论结果"""
        try:
            if '"code":0' in result or '"ret":0' in result:
                return True
        except Exception as e:
            logger.error(f"解析评论结果失败: {e}")
        return False