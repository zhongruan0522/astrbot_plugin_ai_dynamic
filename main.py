import os
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

from .core.memory import MemorySystem
from .core.api_client import CustomAPIClient
from .core.qzone_api import QZoneAPI
from .core.scheduler import TaskScheduler


@register("ai_dynamic", "AIDynamic", "AI智能动态助手 - 基于聊天记忆的个性化QQ动态发布", "1.0.0", "https://github.com/user/astrbot_plugin_ai_dynamic")
class AIDynamicPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        
        # 初始化数据目录
        self.data_dir = Path("data/plugins/ai_dynamic")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化核心模块
        self.memory_system = MemorySystem(str(self.data_dir), self.config)
        self.custom_api = CustomAPIClient(self.config)
        self.qzone_api = QZoneAPI(self.config)
        
        # LLM客户端（优先使用自定义API）
        self.llm_client = None
        self._init_llm_client()
        
        # 任务调度器
        self.scheduler = TaskScheduler(
            self.config, 
            self.memory_system, 
            self.qzone_api, 
            self.llm_client
        )
        
        # 启动后台任务
        asyncio.create_task(self._start_background_tasks())
        
        logger.info("AI动态插件初始化完成")
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.custom_api.is_enabled():
            self.llm_client = self.custom_api
            logger.info("使用自定义API客户端")
        else:
            self.llm_client = self.context.get_using_provider()
            if self.llm_client:
                logger.info("使用AstrBot内置LLM")
            else:
                logger.warning("未配置LLM，部分功能将无法使用")
    
    async def _call_llm_unified(self, prompt: str, system_prompt: str = "", contexts: list = None) -> str:
        """统一的LLM调用接口"""
        if not self.llm_client:
            return ""
        
        if contexts is None:
            contexts = []
        
        try:
            # 调用LLM
            response = await self.llm_client.text_chat(
                prompt=prompt,
                system_prompt=system_prompt,
                contexts=contexts,
                session_id=None
            )
            
            # 统一处理响应格式
            if response is None:
                return ""
            
            # 处理自定义API客户端的响应（dict格式）
            if isinstance(response, dict):
                if response.get('role') == 'assistant':
                    return response.get('completion_text', '').strip()
                elif 'content' in response:
                    return response['content'].strip()
            
            # 处理AstrBot LLM的响应（对象格式）
            if hasattr(response, 'completion_text'):
                return response.completion_text.strip()
            elif hasattr(response, 'content'):
                return response.content.strip()
            elif hasattr(response, 'role') and response.role == 'assistant':
                if hasattr(response, 'completion_text'):
                    return response.completion_text.strip()
            
            # 如果都不匹配，尝试转换为字符串
            return str(response).strip()
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return ""
    
    async def _start_background_tasks(self):
        """启动后台任务"""
        try:
            await asyncio.sleep(2)  # 等待初始化完成
            await self.scheduler.start()
        except Exception as e:
            logger.error(f"启动后台任务失败: {e}")
    
    # ==================== 事件监听器 ====================
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，用于记忆系统"""
        try:
            user_id = event.get_sender_id()
            message = event.message_str
            platform = event.get_platform_name()
            session_id = event.unified_msg_origin
            
            # 保存消息到记忆系统
            await self.memory_system.save_message(
                user_id=str(user_id),
                message=message,
                session_id=session_id,
                platform=platform
            )
            
        except Exception as e:
            logger.error(f"保存消息记忆失败: {e}")
    
    # ==================== 主命令组 ====================
    
    @filter.command_group("aidynamic", alias={"ai动态", "动态"})
    def ai_dynamic_group(self):
        """AI动态管理命令组"""
        pass
    
    # ==================== 动态发布相关命令 ====================
    
    @ai_dynamic_group.command("post", alias={"发布", "发动态"})
    async def manual_post(self, event: AstrMessageEvent, content: str = ""):
        """手动发布动态
        
        用法: /aidynamic post [内容]
        如果不提供内容，将基于记忆自动生成
        """
        if not self.qzone_api.is_configured():
            yield event.plain_result("❌ 请先在插件配置中设置QQ空间登录信息")
            return
        
        try:
            # 如果没有提供内容，则自动生成
            if not content.strip():
                if not self.llm_client:
                    yield event.plain_result("❌ 未配置LLM，无法自动生成内容")
                    return
                
                yield event.plain_result("🤔 正在基于您的聊天记忆生成个性化动态内容...")
                content = await self._generate_dynamic_for_user(event.get_sender_id())
                
                if not content:
                    yield event.plain_result("❌ 生成动态内容失败，请手动提供内容或检查记忆数据")
                    return
            
            # 发布动态
            yield event.plain_result("📤 正在发布动态...")
            success = await self.qzone_api.publish_dynamic(content)
            
            if success:
                yield event.plain_result(f"✅ 动态发布成功！\n\n内容：{content}")
            else:
                yield event.plain_result(f"❌ 动态发布失败\n\n生成的内容：{content}")
                
        except Exception as e:
            logger.error(f"手动发布动态失败: {e}")
            yield event.plain_result("❌ 发布动态时出现异常，请检查配置")
    
    @ai_dynamic_group.command("postimg", alias={"带图发布", "图片动态"})
    async def post_with_images(self, event: AstrMessageEvent, content: str = ""):
        """发布带图片的动态（需要在消息中包含图片）"""
        if not self.qzone_api.is_configured():
            yield event.plain_result("❌ 请先配置QQ空间登录信息")
            return
        
        # 提取消息中的图片
        images = []
        for component in event.message_obj.message:
            if isinstance(component, Comp.Image):
                if hasattr(component, 'url') and component.url:
                    images.append(component.url)
                elif hasattr(component, 'file') and component.file:
                    images.append(component.file)
        
        if not images:
            yield event.plain_result("❌ 请在消息中包含图片")
            return
        
        try:
            # 如果没有内容，生成图片相关的文案
            if not content.strip():
                if self.llm_client:
                    content = await self._generate_image_caption()
                else:
                    content = "分享一张图片 📸"
            
            yield event.plain_result("📤 正在发布图片动态...")
            success = await self.qzone_api.publish_dynamic(content, images)
            
            if success:
                yield event.plain_result(f"✅ 图片动态发布成功！\n\n内容：{content}\n图片数量：{len(images)}")
            else:
                yield event.plain_result("❌ 图片动态发布失败")
                
        except Exception as e:
            logger.error(f"发布图片动态失败: {e}")
            yield event.plain_result("❌ 发布图片动态时出现异常")
    
    async def _generate_dynamic_for_user(self, user_id: str) -> str:
        """为特定用户生成个性化动态"""
        try:
            # 检查用户是否在白名单中
            if not self.memory_system.is_user_in_whitelist(str(user_id)):
                return await self._generate_general_dynamic()
            
            # 获取用户最近的总结
            summaries = await self.memory_system.get_recent_summaries(str(user_id), 7)
            
            if not summaries:
                return await self._generate_general_dynamic()
            
            # 基于总结生成动态
            summary_text = "\n".join([f"[{s['date']}] {s['summary']}" for s in summaries[:3]])
            
            dynamic_prompt = self.config.get('prompts', {}).get('dynamic_prompt', '')
            
            user_prompt = f"""基于以下最近的生活记录，创作一条个性化的QQ动态：

{summary_text}

请创作一条符合当前心情和状态的动态内容。"""
            
            content = await self._call_llm_unified(user_prompt, dynamic_prompt, [])
            return content if content else await self._generate_general_dynamic()
            
        except Exception as e:
            logger.error(f"生成个性化动态失败: {e}")
        
        return await self._generate_general_dynamic()
    
    async def _generate_general_dynamic(self) -> str:
        """生成通用动态"""
        general_topics = [
            "今天心情不错，和大家分享一下好心情 😊",
            "生活就是这样，有起有落，但总要向前看 ✨",
            "最近学到了一些新东西，感觉很有收获 📚",
            "和朋友们聊天总是很开心，友谊万岁 👥",
            "有时候停下来看看周围，会发现很多美好 🌸",
            "今天完成了一些小目标，继续加油 💪"
        ]
        
        import random
        return random.choice(general_topics)
    
    async def _generate_image_caption(self) -> str:
        """生成图片文案"""
        captions = [
            "分享一张喜欢的图片 📸",
            "记录生活中的美好瞬间 ✨",
            "今天拍到了不错的照片 📷",
            "这个画面很有感觉 🎨",
            "用图片记录此刻的心情 💭"
        ]
        
        import random
        return random.choice(captions)
    
    # ==================== 记忆管理相关命令 ====================
    
    @ai_dynamic_group.command("memory", alias={"记忆", "记忆状态"})
    async def memory_info(self, event: AstrMessageEvent):
        """查看记忆系统状态"""
        try:
            stats = await self.memory_system.get_memory_stats()
            user_id = str(event.get_sender_id())
            
            # 检查用户是否在白名单
            is_whitelisted = self.memory_system.is_user_in_whitelist(user_id)
            
            # 获取用户的记忆统计
            recent_summaries = await self.memory_system.get_recent_summaries(user_id, 7)
            
            info_text = f"""📊 记忆系统状态

全局统计：
• 总消息数：{stats.get('total_messages', 0)}
• 记录用户数：{stats.get('total_users', 0)}
• 生成总结数：{stats.get('total_summaries', 0)}
• 今日新增：{stats.get('today_messages', 0)} 条

您的状态：
• 白名单状态：{"✅ 已加入" if is_whitelisted else "❌ 未加入"}
• 近7天总结：{len(recent_summaries)} 份

数据库大小：{stats.get('database_size', 0) / 1024:.1f} KB"""

            yield event.plain_result(info_text)
            
        except Exception as e:
            logger.error(f"获取记忆信息失败: {e}")
            yield event.plain_result("❌ 获取记忆信息失败")
    
    @ai_dynamic_group.command("summary", alias={"查看总结", "总结"})
    async def view_summaries(self, event: AstrMessageEvent, days: int = 7):
        """查看最近的总结
        
        用法: /aidynamic summary [天数]
        """
        user_id = str(event.get_sender_id())
        
        if not self.memory_system.is_user_in_whitelist(user_id):
            yield event.plain_result("❌ 您不在记忆白名单中，无法查看总结")
            return
        
        try:
            summaries = await self.memory_system.get_recent_summaries(user_id, days)
            
            if not summaries:
                yield event.plain_result(f"📝 最近{days}天没有生成总结")
                return
            
            summary_text = f"📝 最近{days}天的生活总结：\n\n"
            
            for summary in summaries:
                summary_text += f"📅 {summary['date']}\n"
                summary_text += f"💬 消息数：{summary['message_count']}\n"
                summary_text += f"📄 总结：{summary['summary']}\n\n"
            
            if len(summary_text) > 2000:
                summary_text = summary_text[:1900] + "\n\n... (总结过长，已截断)"
            
            yield event.plain_result(summary_text.strip())
            
        except Exception as e:
            logger.error(f"查看总结失败: {e}")
            yield event.plain_result("❌ 获取总结失败")
    
    @ai_dynamic_group.command("generate", alias={"生成总结", "生成"})
    async def generate_summary(self, event: AstrMessageEvent, date: str = ""):
        """手动生成指定日期的总结
        
        用法: /aidynamic generate [日期YYYY-MM-DD]
        不指定日期则为昨天
        """
        user_id = str(event.get_sender_id())
        
        if not self.memory_system.is_user_in_whitelist(user_id):
            yield event.plain_result("❌ 您不在记忆白名单中，无法生成总结")
            return
        
        if not self.llm_client:
            yield event.plain_result("❌ 未配置LLM，无法生成总结")
            return
        
        # 处理日期
        if not date:
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD 格式")
                return
        
        try:
            yield event.plain_result(f"🤔 正在生成 {date} 的总结...")
            
            summary = await self.memory_system.generate_daily_summary(
                user_id, self, date
            )
            
            if summary:
                yield event.plain_result(f"✅ 总结生成完成\n\n📅 {date}\n📄 {summary}")
            else:
                yield event.plain_result(f"❌ 生成总结失败，可能是当天没有足够的聊天记录")
                
        except Exception as e:
            logger.error(f"生成总结失败: {e}")
            yield event.plain_result("❌ 生成总结时出现异常")
    
    # ==================== 系统管理相关命令 ====================
    
    @ai_dynamic_group.command("status", alias={"状态", "插件状态"})
    async def plugin_status(self, event: AstrMessageEvent):
        """查看插件状态"""
        try:
            # 检查各模块状态
            qzone_status = "✅ 已配置" if self.qzone_api.is_configured() else "❌ 未配置"
            llm_status = "✅ 已配置" if self.llm_client else "❌ 未配置"
            custom_api_status = "✅ 已启用" if self.custom_api.is_enabled() else "❌ 未启用"
            
            # 获取配置状态
            memory_enabled = self.config.get('memory_config', {}).get('enable_memory', True)
            auto_post_enabled = self.config.get('dynamic_config', {}).get('enable_auto_post', False)
            auto_comment_enabled = self.config.get('comment_config', {}).get('enable_auto_comment', False)
            
            # 获取白名单信息
            whitelist = self.config.get('memory_config', {}).get('user_whitelist', [])
            
            status_text = f"""🤖 AI动态插件状态

核心模块：
• QQ空间API：{qzone_status}
• LLM服务：{llm_status}
• 自定义API：{custom_api_status}

功能状态：
• 记忆系统：{"✅ 已启用" if memory_enabled else "❌ 已禁用"}
• 自动发布：{"✅ 已启用" if auto_post_enabled else "❌ 已禁用"}
• 自动评论：{"✅ 已启用" if auto_comment_enabled else "❌ 已禁用"}

记忆白名单：{len(whitelist)} 个用户
任务调度器：{"✅ 运行中" if self.scheduler.running else "❌ 已停止"}"""

            yield event.plain_result(status_text)
            
        except Exception as e:
            logger.error(f"获取插件状态失败: {e}")
            yield event.plain_result("❌ 获取状态失败")
    
    @ai_dynamic_group.command("test", alias={"测试连接", "测试"})
    async def test_connection(self, event: AstrMessageEvent):
        """测试各项连接"""
        try:
            results = []
            
            # 测试自定义API
            if self.custom_api.is_enabled():
                yield event.plain_result("🔄 正在测试自定义API连接...")
                api_result = await self.custom_api.test_connection()
                if api_result.get('success'):
                    results.append("✅ 自定义API连接正常")
                else:
                    results.append(f"❌ 自定义API连接失败: {api_result.get('error')}")
            else:
                results.append("⚪ 自定义API未启用")
            
            # 测试AstrBot LLM
            if self.context.get_using_provider():
                results.append("✅ AstrBot LLM可用")
            else:
                results.append("❌ AstrBot LLM未配置")
            
            # 测试QQ空间配置
            if self.qzone_api.is_configured():
                results.append("✅ QQ空间配置完整")
            else:
                results.append("❌ QQ空间配置不完整")
            
            # 测试记忆系统
            try:
                stats = await self.memory_system.get_memory_stats()
                results.append("✅ 记忆系统数据库正常")
            except Exception:
                results.append("❌ 记忆系统数据库异常")
            
            result_text = "🔍 连接测试结果：\n\n" + "\n".join(results)
            yield event.plain_result(result_text)
            
        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            yield event.plain_result("❌ 连接测试失败")
    
    # ==================== 生命周期管理 ====================
    
    async def terminate(self):
        """插件卸载时调用"""
        try:
            # 停止任务调度器
            await self.scheduler.stop()
            
            # 关闭QQ空间会话
            await self.qzone_api.close_session()
            
            logger.info("AI动态插件已停止")
            
        except Exception as e:
            logger.error(f"插件停止异常: {e}")