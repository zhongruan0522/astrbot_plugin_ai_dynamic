from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime, timedelta
import asyncio
import random

class AIGenerator:
    """AI文案生成器"""
    
    def __init__(self, context):
        self.context = context
    
    async def generate_post_content(self, 
                                  chat_records: List, 
                                  memories: List, 
                                  prompt: str,
                                  custom_prompt: Optional[str] = None) -> str:
        """生成朋友圈文案"""
        
        # 构建聊天记录摘要
        chat_summary = self._summarize_chats(chat_records)
        
        # 构建记忆摘要
        memory_summary = self._summarize_memories(memories)
        
        # 构建完整提示词
        full_prompt = prompt
        if custom_prompt:
            full_prompt = custom_prompt
        
        full_prompt += f"\n\n聊天记录摘要:\n{chat_summary}\n\n记忆信息:\n{memory_summary}"
        
        try:
            # 获取LLM提供者
            provider = self.context.get_using_provider()
            if not provider:
                return "AI服务未配置，无法生成文案"
            
            # 调用AI生成文案
            response = await provider.text_chat(
                prompt=full_prompt,
                session_id=None,
                contexts=[],
                image_urls=[],
                func_tool=None,
                system_prompt="你是一个擅长写朋友圈文案的助手，语言风格自然、生动、有趣。"
            )
            
            if response.role == "assistant":
                return response.completion_text.strip()
            else:
                return "AI生成失败，请稍后重试"
                
        except Exception as e:
            return f"AI生成出错: {str(e)}"
    
    async def generate_memory_summary(self, 
                                    chat_records: List,
                                    prompt: str,
                                    summary_type: str = "daily") -> str:
        """生成记忆总结"""
        
        # 构建聊天记录内容
        chat_content = self._format_chats_for_summary(chat_records)
        
        # 构建完整提示词
        full_prompt = prompt + f"\n\n请按{summary_type}的方式总结以下聊天记录：\n\n{chat_content}"
        
        try:
            # 获取LLM提供者
            provider = self.context.get_using_provider()
            if not provider:
                return "AI服务未配置，无法生成记忆"
            
            # 调用AI生成记忆
            response = await provider.text_chat(
                prompt=full_prompt,
                session_id=None,
                contexts=[],
                image_urls=[],
                func_tool=None,
                system_prompt="你是一个擅长总结和记录的助手，能够从对话中提取重要信息并形成清晰的记忆。"
            )
            
            if response.role == "assistant":
                return response.completion_text.strip()
            else:
                return "AI记忆生成失败，请稍后重试"
                
        except Exception as e:
            return f"AI记忆生成出错: {str(e)}"
    
    def _summarize_chats(self, chat_records: List) -> str:
        """总结聊天记录"""
        if not chat_records:
            return "暂无聊天记录"
        
        # 按时间排序
        sorted_chats = sorted(chat_records, key=lambda x: x.timestamp, reverse=True)
        
        # 提取关键信息
        topics = []
        for chat in sorted_chats[:20]:  # 只取最近20条
            if chat.content.strip():
                topics.append(f"{chat.sender_name}: {chat.content[:100]}")
        
        return "\n".join(topics)
    
    def _summarize_memories(self, memories: List) -> str:
        """总结记忆信息"""
        if not memories:
            return "暂无记忆信息"
        
        # 按时间排序
        sorted_memories = sorted(memories, key=lambda x: x.created_at, reverse=True)
        
        # 提取记忆内容
        memory_content = []
        for memory in sorted_memories[:10]:  # 只取最近10条
            memory_content.append(f"- {memory.content}")
        
        return "\n".join(memory_content)
    
    def _format_chats_for_summary(self, chat_records: List) -> str:
        """格式化聊天记录用于记忆总结"""
        if not chat_records:
            return "暂无聊天记录"
        
        # 按时间排序
        sorted_chats = sorted(chat_records, key=lambda x: x.timestamp)
        
        # 格式化聊天记录
        formatted_chats = []
        for chat in sorted_chats:
            time_str = datetime.fromtimestamp(chat.timestamp).strftime("%Y-%m-%d %H:%M")
            formatted_chats.append(f"[{time_str}] {chat.sender_name}: {chat.content}")
        
        return "\n".join(formatted_chats)

class PostScheduler:
    """朋友圈发布调度器"""
    
    def __init__(self, config):
        self.config = config
        self.running = False
        self.tasks: List[asyncio.Task] = []
    
    def parse_schedule_time(self, time_str: str) -> tuple:
        """解析时间配置"""
        try:
            start_time, end_time = time_str.split('-')
            start_hour, start_minute = map(int, start_time.split(':'))
            end_hour, end_minute = map(int, end_time.split(':'))
            return (start_hour, start_minute), (end_hour, end_minute)
        except:
            # 默认时间 9:00-22:00
            return (9, 0), (22, 0)
    
    def get_random_post_time(self) -> datetime:
        """获取随机发布时间"""
        (start_hour, start_minute), (end_hour, end_minute) = self.parse_schedule_time(
            self.config.get('schedule_time', '09:00-22:00')
        )
        
        now = datetime.now()
        
        # 计算时间范围
        start_time = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        # 如果开始时间已过，设置为明天
        if start_time <= now:
            start_time = start_time + timedelta(days=1)
            end_time = end_time + timedelta(days=1)
        
        # 生成随机时间
        total_seconds = int((end_time - start_time).total_seconds())
        random_seconds = random.randint(0, total_seconds)
        
        return start_time + timedelta(seconds=random_seconds)
    
    def get_today_post_count(self) -> int:
        """获取今日应发朋友圈次数"""
        max_posts = self.config.get('max_posts_per_day', 3)
        return random.randint(1, max_posts)
    
    async def start_scheduler(self, post_callback):
        """启动调度器"""
        self.running = True
        
        # 每日调度任务
        async def daily_schedule():
            while self.running:
                try:
                    # 等待到下一个总结时间
                    await self.wait_until_summary_time()
                    
                    if not self.running:
                        break
                    
                    # 生成今日发布计划
                    post_count = self.get_today_post_count()
                    post_times = []
                    
                    for i in range(post_count):
                        post_time = self.get_random_post_time()
                        post_times.append(post_time)
                        
                        # 创建发布任务
                        task = asyncio.create_task(
                            self.schedule_post(post_time, post_callback)
                        )
                        self.tasks.append(task)
                    
                    print(f"已安排今日 {post_count} 条朋友圈发布任务")
                    
                    # 等待到明天
                    await asyncio.sleep(24 * 60 * 60)
                    
                except Exception as e:
                    print(f"调度器错误: {e}")
                    await asyncio.sleep(60)  # 错误后等待1分钟
        
        # 启动调度任务
        schedule_task = asyncio.create_task(daily_schedule())
        self.tasks.append(schedule_task)
    
    async def wait_until_summary_time(self):
        """等待到总结时间"""
        summary_time_str = self.config.get('memory_summary_time', '23:00')
        try:
            hour, minute = map(int, summary_time_str.split(':'))
        except:
            hour, minute = 23, 0
        
        now = datetime.now()
        summary_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果总结时间已过，设置为明天
        if summary_time <= now:
            summary_time = summary_time + timedelta(days=1)
        
        wait_seconds = (summary_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
    
    async def schedule_post(self, post_time: datetime, post_callback):
        """调度单个朋友圈发布"""
        now = datetime.now()
        wait_seconds = (post_time - now).total_seconds()
        
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        
        if self.running:
            try:
                await post_callback()
            except Exception as e:
                print(f"发布朋友圈失败: {e}")
    
    async def stop_scheduler(self):
        """停止调度器"""
        self.running = False
        
        # 取消所有任务
        for task in self.tasks:
            task.cancel()
        
        # 等待任务完成
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()