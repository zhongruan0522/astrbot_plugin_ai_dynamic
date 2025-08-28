import asyncio
import random
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict
from astrbot.api import logger


class TaskScheduler:
    """任务调度器 - 负责定时发布动态和自动评论"""
    
    def __init__(self, config: dict, memory_system, qzone_api, llm_client):
        self.config = config
        self.memory_system = memory_system
        self.qzone_api = qzone_api
        self.llm_client = llm_client
        
        self.running = False
        self.tasks = []
        
        # 定时任务状态
        self.last_summary_date = None
        self.last_post_times = []  # 记录最近的发布时间
        self.last_comment_check = datetime.now()
    
    async def start(self):
        """启动任务调度器"""
        if self.running:
            return
        
        self.running = True
        logger.info("任务调度器启动")
        
        # 启动各种定时任务
        self.tasks = [
            asyncio.create_task(self._daily_summary_task()),
            asyncio.create_task(self._auto_post_task()),
            asyncio.create_task(self._auto_comment_task()),
            asyncio.create_task(self._cleanup_task())
        ]
    
    async def stop(self):
        """停止任务调度器"""
        self.running = False
        
        # 取消所有任务
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        logger.info("任务调度器停止")
    
    async def _daily_summary_task(self):
        """每日总结任务"""
        while self.running:
            try:
                # 检查是否启用记忆功能
                if not self.config.get('memory_config', {}).get('enable_memory', True):
                    await asyncio.sleep(3600)  # 1小时后再检查
                    continue
                
                # 获取配置的总结时间
                summary_time_str = self.config.get('memory_config', {}).get('summary_time', '00:00')
                summary_time = datetime.strptime(summary_time_str, '%H:%M').time()
                
                now = datetime.now()
                today_str = now.strftime('%Y-%m-%d')
                
                # 检查是否到了总结时间且今天还没有总结过
                if (now.time() >= summary_time and 
                    self.last_summary_date != today_str):
                    
                    await self._perform_daily_summary()
                    self.last_summary_date = today_str
                
                # 计算下次检查的时间
                await asyncio.sleep(300)  # 5分钟检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"每日总结任务异常: {e}")
                await asyncio.sleep(300)
    
    async def _perform_daily_summary(self):
        """执行每日总结"""
        try:
            whitelist = self.config.get('memory_config', {}).get('user_whitelist', [])
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            for user_id in whitelist:
                try:
                    summary = await self.memory_system.generate_daily_summary(
                        user_id, self.llm_client, yesterday
                    )
                    if summary:
                        logger.info(f"生成用户 {user_id} 的每日总结完成")
                    
                    # 避免频率过高
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"为用户 {user_id} 生成总结失败: {e}")
            
            logger.info("每日总结任务完成")
            
        except Exception as e:
            logger.error(f"执行每日总结失败: {e}")
    
    async def _auto_post_task(self):
        """自动发布动态任务"""
        while self.running:
            try:
                # 检查是否启用自动发布
                if not self.config.get('dynamic_config', {}).get('enable_auto_post', False):
                    await asyncio.sleep(3600)
                    continue
                
                if await self._should_post_dynamic():
                    await self._generate_and_post_dynamic()
                
                # 每30分钟检查一次
                await asyncio.sleep(1800)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动发布任务异常: {e}")
                await asyncio.sleep(1800)
    
    async def _should_post_dynamic(self) -> bool:
        """判断是否应该发布动态"""
        dynamic_config = self.config.get('dynamic_config', {})
        
        # 检查今日发布次数
        daily_count = dynamic_config.get('daily_post_count', 2)
        today = datetime.now().date()
        today_posts = [t for t in self.last_post_times if t.date() == today]
        
        if len(today_posts) >= daily_count:
            return False
        
        # 检查时间范围
        time_range = dynamic_config.get('post_time_range', {})
        start_time = datetime.strptime(time_range.get('start_time', '09:00'), '%H:%M').time()
        end_time = datetime.strptime(time_range.get('end_time', '22:00'), '%H:%M').time()
        
        current_time = datetime.now().time()
        if not (start_time <= current_time <= end_time):
            return False
        
        # 检查最小间隔
        min_interval = dynamic_config.get('min_interval_hours', 3)
        if self.last_post_times:
            last_post = max(self.last_post_times)
            if datetime.now() - last_post < timedelta(hours=min_interval):
                return False
        
        # 添加随机性，避免太机械化
        return random.random() < 0.3  # 30%的概率发布
    
    async def _generate_and_post_dynamic(self):
        """生成并发布动态"""
        try:
            if not self.qzone_api.is_configured():
                logger.warning("QQ空间未配置，跳过自动发布")
                return
            
            # 获取白名单用户的最近总结
            whitelist = self.config.get('memory_config', {}).get('user_whitelist', [])
            if not whitelist:
                logger.warning("没有配置记忆白名单用户，无法生成个性化动态")
                return
            
            # 随机选择一个用户的记忆作为创作素材
            user_id = random.choice(whitelist)
            recent_summaries = await self.memory_system.get_recent_summaries(user_id, 7)
            
            if not recent_summaries:
                logger.info(f"用户 {user_id} 没有近期总结，使用通用动态")
                content = await self._generate_general_dynamic()
            else:
                content = await self._generate_personalized_dynamic(recent_summaries)
            
            if content:
                success = await self.qzone_api.publish_dynamic(content)
                if success:
                    self.last_post_times.append(datetime.now())
                    # 只保留最近的发布记录
                    self.last_post_times = self.last_post_times[-10:]
                    logger.info(f"自动发布动态成功: {content[:50]}...")
                else:
                    logger.warning("自动发布动态失败")
            
        except Exception as e:
            logger.error(f"生成并发布动态异常: {e}")
    
    async def _generate_personalized_dynamic(self, summaries: List[Dict]) -> Optional[str]:
        """基于用户记忆生成个性化动态"""
        try:
            # 整理最近的总结内容
            summary_text = "\n".join([f"[{s['date']}] {s['summary']}" for s in summaries[:5]])
            
            dynamic_prompt = self.config.get('prompts', {}).get('dynamic_prompt', '')
            
            user_prompt = f"""基于以下最近的生活记录，创作一条QQ动态：

最近生活记录：
{summary_text}

请创作一条真实、自然的动态内容，要求：
1. 基于记录中的真实情况，但不要完全复制
2. 语言要自然贴近生活
3. 可以加入一些情感表达和emoji
4. 长度控制在100字以内
5. 避免过于正式或商业化的表达"""

            # 调用LLM生成内容
            if hasattr(self.llm_client, '_call_llm_unified'):
                # 使用主插件的统一LLM接口
                return await self.llm_client._call_llm_unified(
                    prompt=user_prompt,
                    system_prompt=dynamic_prompt,
                    contexts=[]
                )
            elif hasattr(self.llm_client, 'text_chat'):
                response = await self.llm_client.text_chat(
                    prompt=user_prompt,
                    system_prompt=dynamic_prompt,
                    contexts=[],
                    session_id=None
                )
                
                # 统一处理响应格式
                if response is None:
                    return None
                
                if isinstance(response, dict):
                    if response.get('role') == 'assistant':
                        return response.get('completion_text', '').strip()
                    elif 'content' in response:
                        return response['content'].strip()
                
                if hasattr(response, 'completion_text'):
                    return response.completion_text.strip()
                elif hasattr(response, 'content'):
                    return response.content.strip()
                elif hasattr(response, 'role') and response.role == 'assistant':
                    if hasattr(response, 'completion_text'):
                        return response.completion_text.strip()
                
                return str(response).strip() if response else None
            
        except Exception as e:
            logger.error(f"生成个性化动态失败: {e}")
        
        return None
    
    async def _generate_general_dynamic(self) -> Optional[str]:
        """生成通用动态内容"""
        general_topics = [
            "今天的天气真不错，心情也跟着好起来了☀️",
            "突然想起一些美好的回忆，感觉生活还是很有意思的😊",
            "最近在学习新的东西，虽然有点累但很充实💪",
            "和朋友聊天总是能得到很多启发，真好👥",
            "有时候放慢脚步，会发现生活中很多小美好🌸",
            "今天完成了一些小目标，给自己点个赞👍",
            "音乐真是治愈的良药，瞬间心情就好了🎵"
        ]
        
        return random.choice(general_topics)
    
    async def _auto_comment_task(self):
        """自动评论任务"""
        while self.running:
            try:
                # 检查是否启用自动评论
                if not self.config.get('comment_config', {}).get('enable_auto_comment', False):
                    await asyncio.sleep(3600)
                    continue
                
                await self._check_and_comment_dynamics()
                
                # 根据配置的检查间隔
                interval = self.config.get('comment_config', {}).get('check_interval_minutes', 30)
                await asyncio.sleep(interval * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动评论任务异常: {e}")
                await asyncio.sleep(1800)
    
    async def _check_and_comment_dynamics(self):
        """检查并评论动态"""
        try:
            if not self.qzone_api.is_configured():
                return
            
            comment_config = self.config.get('comment_config', {})
            target_users = comment_config.get('target_users', [])
            probability = comment_config.get('comment_probability', 30) / 100
            
            for qq_id in target_users:
                try:
                    # 获取用户最近的动态
                    dynamics = await self.qzone_api.get_recent_dynamics(qq_id, 5)
                    
                    for dynamic in dynamics:
                        # 检查是否已经评论过或随机决定是否评论
                        if (not dynamic.get('has_comment', False) and 
                            random.random() < probability):
                            
                            comment = await self._generate_comment(dynamic['content'])
                            if comment:
                                success = await self.qzone_api.comment_dynamic(
                                    dynamic['tid'], qq_id, comment
                                )
                                if success:
                                    logger.info(f"自动评论成功: {qq_id} - {comment}")
                                
                                # 避免评论过于频繁
                                await asyncio.sleep(random.randint(10, 30))
                    
                    # 用户间隔
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"为用户 {qq_id} 评论动态失败: {e}")
            
        except Exception as e:
            logger.error(f"检查并评论动态异常: {e}")
    
    async def _generate_comment(self, dynamic_content: str) -> Optional[str]:
        """生成评论内容"""
        try:
            comment_prompt = self.config.get('prompts', {}).get('comment_prompt', '')
            
            user_prompt = f"""对以下动态内容生成一条友好的评论：

动态内容：{dynamic_content}

请生成一条自然、友好的评论回复，要求：
1. 语言要自然不做作
2. 体现出朋友之间的关心
3. 可以使用合适的emoji
4. 长度控制在50字以内
5. 避免重复性的回复"""

            # 调用LLM生成评论
            if hasattr(self.llm_client, '_call_llm_unified'):
                # 使用主插件的统一LLM接口
                return await self.llm_client._call_llm_unified(
                    prompt=user_prompt,
                    system_prompt=comment_prompt,
                    contexts=[]
                )
            elif hasattr(self.llm_client, 'text_chat'):
                response = await self.llm_client.text_chat(
                    prompt=user_prompt,
                    system_prompt=comment_prompt,
                    contexts=[],
                    session_id=None
                )
                
                # 统一处理响应格式
                if response is None:
                    return None
                
                if isinstance(response, dict):
                    if response.get('role') == 'assistant':
                        return response.get('completion_text', '').strip()
                    elif 'content' in response:
                        return response['content'].strip()
                
                if hasattr(response, 'completion_text'):
                    return response.completion_text.strip()
                elif hasattr(response, 'content'):
                    return response.content.strip()
                elif hasattr(response, 'role') and response.role == 'assistant':
                    if hasattr(response, 'completion_text'):
                        return response.completion_text.strip()
                
                return str(response).strip() if response else None
            
        except Exception as e:
            logger.error(f"生成评论失败: {e}")
        
        return None
    
    async def _cleanup_task(self):
        """清理任务 - 定期清理过期数据"""
        while self.running:
            try:
                # 每天凌晨2点执行清理
                now = datetime.now()
                if now.hour == 2 and now.minute < 10:
                    await self.memory_system.cleanup_old_data()
                    logger.info("执行数据清理完成")
                
                await asyncio.sleep(600)  # 10分钟检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务异常: {e}")
                await asyncio.sleep(600)