import asyncio
import os
import time
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Comp

from core.memory import MemoryManager, ChatRecorder, ChatMessage
from core.ai_generator import AIGenerator, PostScheduler
from core.qzone_api import QzoneAPI

@register("auto_moments", "Assistant", "自动发朋友圈插件", "1.0.0", "https://github.com/zhongruan0522/astrbot_plugin_ai_dynamic")
class AutoMomentsPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(context.get_data_dir()) / "auto_moments"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化核心组件
        self.memory_manager = MemoryManager(str(self.data_dir))
        self.chat_recorder = ChatRecorder(str(self.data_dir))
        self.ai_generator = AIGenerator(context)
        self.scheduler = PostScheduler(config)
        self.qzone_api = QzoneAPI()
        
        # 启动调度器
        if config.get('enable_auto_post', True):
            asyncio.create_task(self.start_scheduler())
    
    async def start_scheduler(self):
        """启动自动发布调度器"""
        try:
            await self.scheduler.start_scheduler(self.auto_post_callback)
            logger.info("自动发朋友圈调度器已启动")
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
    
    async def auto_post_callback(self):
        """自动发布回调函数"""
        try:
            # 获取今日聊天记录
            today_chats = self.chat_recorder.get_today_chats()
            
            # 获取记忆
            memories = self.memory_manager.get_memories(10)
            
            # 生成文案
            post_content = await self.ai_generator.generate_post_content(
                chat_records=today_chats,
                memories=memories,
                prompt=self.config.get('post_prompt', '')
            )
            
            # 发布朋友圈
            success = await self.publish_moments(post_content)
            
            if success:
                logger.info(f"自动发布朋友圈成功: {post_content[:50]}...")
            else:
                logger.error("自动发布朋友圈失败")
                
        except Exception as e:
            logger.error(f"自动发布回调出错: {e}")
    
    async def publish_moments(self, content: str, images: List[str] = None, event: AstrMessageEvent = None) -> bool:
        """发布朋友圈"""
        try:
            # 自动获取QQ客户端并登录
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            
            if event and isinstance(event, AiocqhttpMessageEvent):
                client = event.bot
            else:
                # 如果没有event，尝试从上下文获取客户端
                try:
                    # 获取aiocqhttp平台适配器
                    platform = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
                    if platform:
                        client = platform.get_client()
                    else:
                        logger.error("无法获取QQ客户端，请确保使用QQ个人号")
                        return False
                except Exception as e:
                    logger.error(f"获取QQ客户端失败: {e}")
                    return False
            
            # 使用QQ空间API发布
            async with self.qzone_api:
                success = await self.qzone_api.login(client)
                if not success:
                    logger.error("QQ空间自动登录失败")
                    return False
                
                # 发布说说
                tid = await self.qzone_api.publish_emotion(content, images)
                
                if tid:
                    logger.info(f"朋友圈发布成功: {content[:50]}... ID: {tid}")
                    return True
                else:
                    logger.error("朋友圈发布失败")
                    return False
                    
        except Exception as e:
            logger.error(f"发布朋友圈异常: {e}")
            return False
    
    @filter.command("主动动态")
    async def manual_post(self, event: AstrMessageEvent, custom_prompt: Optional[str] = None):
        """手动触发发布朋友圈"""
        try:
            # 获取最近聊天记录
            recent_chats = self.chat_recorder.get_recent_chats(7)
            
            # 获取记忆
            memories = self.memory_manager.get_memories(10)
            
            # 生成文案
            post_content = await self.ai_generator.generate_post_content(
                chat_records=recent_chats,
                memories=memories,
                prompt=self.config.get('post_prompt', ''),
                custom_prompt=custom_prompt
            )
            
            # 发布朋友圈（自动登录）
            success = await self.publish_moments(post_content, event=event)
            
            if success:
                yield event.plain_result(f"✅ 朋友圈发布成功！\n\n{post_content}")
            else:
                yield event.plain_result("❌ 朋友圈发布失败，请确保QQ客户端正常运行")
                
        except Exception as e:
            logger.error(f"手动发布朋友圈失败: {e}")
            yield event.plain_result(f"❌ 发布失败: {str(e)}")
    
    @filter.command("查看说说")
    async def view_emotions(self, event: AstrMessageEvent, num: int = 10):
        """查看最近的说说"""
        try:
            # 自动获取QQ客户端并登录
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            
            if not isinstance(event, AiocqhttpMessageEvent):
                yield event.plain_result("❌ 仅支持QQ个人号客户端")
                return
            
            client = event.bot
            
            # 获取说说列表
            async with self.qzone_api:
                success = await self.qzone_api.login(client)
                if not success:
                    yield event.plain_result("❌ QQ空间连接失败，请确保QQ客户端正常运行")
                    return
                
                emotions = await self.qzone_api.get_emotions(num)
            
            if not emotions:
                yield event.plain_result("📝 暂无说说记录")
                return
            
            result = "📝 最近说说记录:\n\n"
            for i, emotion in enumerate(emotions[:5], 1):  # 只显示前5条
                content = emotion.get('content', '')
                time_str = emotion.get('createTime', '')
                result += f"{i}. {time_str}\n{content[:100]}{'...' if len(content) > 100 else ''}\n\n"
            
            yield event.plain_result(result.strip())
            
        except Exception as e:
            logger.error(f"查看说说失败: {e}")
            yield event.plain_result(f"❌ 查看失败: {str(e)}")
    
    @filter.command("查看记忆")
    async def view_memories(self, event: AstrMessageEvent, limit: int = 10):
        """查看记忆"""
        try:
            memories = self.memory_manager.get_memories(limit)
            
            if not memories:
                yield event.plain_result("📝 暂无记忆记录")
                return
            
            result = "📝 最近记忆记录:\n\n"
            for i, memory in enumerate(memories, 1):
                time_str = datetime.fromtimestamp(memory.created_at).strftime("%Y-%m-%d %H:%M")
                result += f"{i}. [{time_str}] {memory.content}\n\n"
            
            yield event.plain_result(result.strip())
            
        except Exception as e:
            logger.error(f"查看记忆失败: {e}")
            yield event.plain_result(f"❌ 查看失败: {str(e)}")
    
    @filter.command("总结记忆")
    async def summarize_memory(self, event: AstrMessageEvent, days: int = 1):
        """手动总结记忆"""
        try:
            # 获取指定天数的聊天记录
            chats = self.chat_recorder.get_recent_chats(days)
            
            if not chats:
                yield event.plain_result("📝 暂无聊天记录可总结")
                return
            
            # 生成记忆总结
            memory_content = await self.ai_generator.generate_memory_summary(
                chat_records=chats,
                prompt=self.config.get('memory_prompt', ''),
                summary_type="manual"
            )
            
            # 保存记忆
            self.memory_manager.add_memory(memory_content, "manual")
            
            yield event.plain_result(f"✅ 记忆总结成功！\n\n{memory_content}")
            
        except Exception as e:
            logger.error(f"总结记忆失败: {e}")
            yield event.plain_result(f"❌ 总结失败: {str(e)}")
    
    @filter.command("清理记忆")
    async def clean_memories(self, event: AstrMessageEvent, days: int = 30):
        """清理旧记忆"""
        try:
            self.memory_manager.clear_old_memories(days)
            yield event.plain_result(f"✅ 已清理 {days} 天前的记忆记录")
        except Exception as e:
            logger.error(f"清理记忆失败: {e}")
            yield event.plain_result(f"❌ 清理失败: {str(e)}")
    
    @filter.command("清理聊天")
    async def clean_chats(self, event: AstrMessageEvent, days: int = 7):
        """清理旧聊天记录"""
        try:
            self.chat_recorder.clean_old_chats(days)
            yield event.plain_result(f"✅ 已清理 {days} 天前的聊天记录")
        except Exception as e:
            logger.error(f"清理聊天记录失败: {e}")
            yield event.plain_result(f"❌ 清理失败: {str(e)}")
    
    @filter.command("设置自动")
    async def toggle_auto_post(self, event: AstrMessageEvent, enable: bool):
        """设置自动发布"""
        try:
            self.config['enable_auto_post'] = enable
            self.config.save_config()
            
            if enable:
                if not self.scheduler.running:
                    await self.start_scheduler()
                yield event.plain_result("✅ 自动发布已开启")
            else:
                await self.scheduler.stop_scheduler()
                yield event.plain_result("✅ 自动发布已关闭")
                
        except Exception as e:
            logger.error(f"设置自动发布失败: {e}")
            yield event.plain_result(f"❌ 设置失败: {str(e)}")
    
    @filter.command("查看配置")
    async def view_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        try:
            config_text = "⚙️ 当前配置:\n\n"
            config_text += f"自动发布: {'开启' if self.config.get('enable_auto_post', True) else '关闭'}\n"
            config_text += f"发布时间: {self.config.get('schedule_time', '09:00-22:00')}\n"
            config_text += f"每日最大次数: {self.config.get('max_posts_per_day', 3)}\n"
            config_text += f"总结时间: {self.config.get('memory_summary_time', '23:00')}\n"
            config_text += f"聊天保存天数: {self.config.get('chat_save_duration', 7)}\n"
            
            yield event.plain_result(config_text)
            
        except Exception as e:
            logger.error(f"查看配置失败: {e}")
            yield event.plain_result(f"❌ 查看失败: {str(e)}")
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息并保存聊天记录"""
        try:
            # 创建聊天消息对象
            chat_message = ChatMessage(
                id=f"msg_{int(time.time())}_{event.get_sender_id()}",
                sender_id=event.get_sender_id(),
                sender_name=event.get_sender_name(),
                content=event.message_str,
                timestamp=int(time.time()),
                group_id=event.get_group_id()
            )
            
            # 保存聊天记录
            self.chat_recorder.save_chat_message(chat_message)
            
        except Exception as e:
            logger.error(f"保存聊天记录失败: {e}")
    
    async def terminate(self):
        """插件终止时清理资源"""
        try:
            # 停止调度器
            if hasattr(self, 'scheduler'):
                await self.scheduler.stop_scheduler()
            
            # 保存配置
            if hasattr(self, 'config'):
                self.config.save_config()
            
            logger.info("自动发朋友圈插件已停止")
            
        except Exception as e:
            logger.error(f"插件终止时出错: {e}")