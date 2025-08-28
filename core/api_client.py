import aiohttp
import json
from typing import Optional, Dict, List
from astrbot.api import logger


class CustomAPIClient:
    """自定义API客户端 - 支持OpenAI兼容的API接口"""
    
    def __init__(self, config: dict):
        self.config = config
        api_config = config.get('api_config', {})
        
        self.enabled = api_config.get('enable_custom_api', False)
        self.api_url = api_config.get('api_url', '')
        self.api_key = api_config.get('api_key', '')
        self.model_name = api_config.get('model_name', 'gpt-3.5-turbo')
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}' if self.api_key else ''
        }
    
    def is_enabled(self) -> bool:
        """检查自定义API是否启用且配置完整"""
        return (self.enabled and 
                self.api_url and 
                self.api_key and 
                self.model_name)
    
    async def text_chat(self, prompt: str, system_prompt: str = "", contexts: List[Dict] = None) -> Optional[Dict]:
        """调用自定义API进行文本对话"""
        if not self.is_enabled():
            return None
        
        if contexts is None:
            contexts = []
        
        # 构建消息列表
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({
                "role": "system", 
                "content": system_prompt
            })
        
        # 添加历史上下文
        messages.extend(contexts)
        
        # 添加用户输入
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # 构建请求数据
        request_data = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        # 解析响应
                        if 'choices' in result and len(result['choices']) > 0:
                            choice = result['choices'][0]
                            message = choice.get('message', {})
                            content = message.get('content', '').strip()
                            
                            if content:
                                return {
                                    'role': 'assistant',
                                    'completion_text': content,
                                    'raw_completion': result
                                }
                    else:
                        error_text = await response.text()
                        logger.error(f"自定义API调用失败: {response.status} - {error_text}")
                        
        except asyncio.TimeoutError:
            logger.error("自定义API调用超时")
        except Exception as e:
            logger.error(f"自定义API调用异常: {e}")
        
        return None
    
    async def test_connection(self) -> Dict[str, any]:
        """测试API连接"""
        if not self.api_url or not self.api_key:
            return {
                'success': False,
                'error': 'API配置不完整'
            }
        
        test_data = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "max_tokens": 10
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=test_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            'success': True,
                            'model': result.get('model', 'unknown'),
                            'response': result
                        }
                    else:
                        error_text = await response.text()
                        return {
                            'success': False,
                            'status': response.status,
                            'error': error_text
                        }
                        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }