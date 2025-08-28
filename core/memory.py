import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from astrbot.api import logger


class MemorySystem:
    """记忆系统 - 负责保存和管理用户聊天记录"""
    
    def __init__(self, data_dir: str, config: dict):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.config = config
        
        # 数据库文件路径
        self.db_path = self.data_dir / "memory.db"
        self.init_database()
        
    def init_database(self):
        """初始化数据库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    message_content TEXT NOT NULL,
                    message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    platform TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    summary_date DATE NOT NULL,
                    summary_content TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, summary_date)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_user_time 
                ON chat_records(user_id, message_time)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_summary_user_date 
                ON daily_summaries(user_id, summary_date)
            ''')
            
            conn.commit()
            logger.info("记忆系统数据库初始化完成")
    
    def is_user_in_whitelist(self, user_id: str) -> bool:
        """检查用户是否在白名单中"""
        whitelist = self.config.get('memory_config', {}).get('user_whitelist', [])
        return str(user_id) in [str(uid) for uid in whitelist]
    
    async def save_message(self, user_id: str, message: str, session_id: str = "", platform: str = ""):
        """保存用户消息"""
        if not self.config.get('memory_config', {}).get('enable_memory', True):
            return
            
        if not self.is_user_in_whitelist(user_id):
            return
            
        # 检查今日消息数量限制
        today = datetime.now().strftime('%Y-%m-%d')
        daily_count = await self.get_daily_message_count(user_id, today)
        max_daily = self.config.get('memory_config', {}).get('max_daily_messages', 100)
        
        if daily_count >= max_daily:
            logger.debug(f"用户 {user_id} 今日消息数量已达上限 ({max_daily})")
            return
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute('''
                    INSERT INTO chat_records (user_id, message_content, session_id, platform)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, message, session_id, platform))
                conn.commit()
                
            logger.debug(f"保存用户 {user_id} 的消息记录")
        except Exception as e:
            logger.error(f"保存消息记录失败: {e}")
    
    async def get_daily_message_count(self, user_id: str, date: str) -> int:
        """获取用户某日的消息数量"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM chat_records 
                    WHERE user_id = ? AND DATE(message_time) = ?
                ''', (user_id, date))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取日消息数量失败: {e}")
            return 0
    
    async def get_recent_messages(self, user_id: str, days: int = 1) -> List[Dict]:
        """获取用户最近几天的消息"""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute('''
                    SELECT message_content, message_time, platform 
                    FROM chat_records 
                    WHERE user_id = ? AND DATE(message_time) >= ?
                    ORDER BY message_time ASC
                ''', (user_id, start_date))
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'content': row[0],
                        'time': row[1],
                        'platform': row[2]
                    })
                return messages
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            return []
    
    async def generate_daily_summary(self, user_id: str, llm_client, date: str = None) -> Optional[str]:
        """生成用户的每日总结"""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 检查是否已有当日总结
        existing_summary = await self.get_daily_summary(user_id, date)
        if existing_summary:
            logger.debug(f"用户 {user_id} 在 {date} 的总结已存在")
            return existing_summary['summary_content']
        
        # 获取当日消息
        messages = await self.get_messages_by_date(user_id, date)
        if not messages:
            logger.debug(f"用户 {user_id} 在 {date} 没有消息记录")
            return None
        
        # 构建总结提示词
        message_texts = [msg['content'] for msg in messages]
        messages_text = '\n'.join([f"[{msg['time']}] {msg['content']}" for msg in messages])
        
        summary_prompt = f'''
请为以下用户的聊天记录生成一份简洁的日常总结：

日期：{date}
消息条数：{len(messages)}

聊天记录：
{messages_text}

请生成一份100字以内的总结，重点关注：
1. 用户的心情状态
2. 主要话题和关注点  
3. 生活状态和变化
4. 值得记住的重要信息

总结要客观、简洁，便于后续生成个性化动态内容时参考。
'''
        
        try:
            # 调用LLM生成总结
            summary = await self._call_llm_for_summary(llm_client, summary_prompt)
            
            if summary:
                # 保存总结
                await self.save_daily_summary(user_id, date, summary, len(messages))
                logger.info(f"生成用户 {user_id} 在 {date} 的日常总结")
                return summary
            
        except Exception as e:
            logger.error(f"生成日常总结失败: {e}")
        
        return None
    
    async def _call_llm_for_summary(self, llm_client, prompt: str) -> Optional[str]:
        """调用LLM生成总结"""
        try:
            if hasattr(llm_client, '_call_llm_unified'):
                # 使用主插件的统一LLM接口
                return await llm_client._call_llm_unified(
                    prompt=prompt,
                    system_prompt="你是一个善于总结和分析的助手，能够从对话中提取关键信息并生成简洁的总结。",
                    contexts=[]
                )
            elif hasattr(llm_client, 'text_chat'):
                # 直接调用LLM
                response = await llm_client.text_chat(
                    prompt=prompt,
                    system_prompt="你是一个善于总结和分析的助手，能够从对话中提取关键信息并生成简洁的总结。",
                    contexts=[],
                    session_id=None
                )
                
                # 统一处理响应格式
                if response is None:
                    return None
                
                # 处理dict格式响应
                if isinstance(response, dict):
                    if response.get('role') == 'assistant':
                        return response.get('completion_text', '').strip()
                    elif 'content' in response:
                        return response['content'].strip()
                
                # 处理对象格式响应
                if hasattr(response, 'completion_text'):
                    return response.completion_text.strip()
                elif hasattr(response, 'content'):
                    return response.content.strip()
                elif hasattr(response, 'role') and response.role == 'assistant':
                    if hasattr(response, 'completion_text'):
                        return response.completion_text.strip()
                
                return str(response).strip() if response else None
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
        
        return None
    
    async def get_messages_by_date(self, user_id: str, date: str) -> List[Dict]:
        """获取指定日期的消息"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute('''
                    SELECT message_content, message_time, platform 
                    FROM chat_records 
                    WHERE user_id = ? AND DATE(message_time) = ?
                    ORDER BY message_time ASC
                ''', (user_id, date))
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'content': row[0],
                        'time': row[1],
                        'platform': row[2]
                    })
                return messages
        except Exception as e:
            logger.error(f"获取指定日期消息失败: {e}")
            return []
    
    async def save_daily_summary(self, user_id: str, date: str, summary: str, message_count: int):
        """保存日常总结"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO daily_summaries 
                    (user_id, summary_date, summary_content, message_count)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, date, summary, message_count))
                conn.commit()
        except Exception as e:
            logger.error(f"保存日常总结失败: {e}")
    
    async def get_daily_summary(self, user_id: str, date: str) -> Optional[Dict]:
        """获取日常总结"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute('''
                    SELECT summary_content, message_count, created_at
                    FROM daily_summaries 
                    WHERE user_id = ? AND summary_date = ?
                ''', (user_id, date))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'summary_content': row[0],
                        'message_count': row[1],
                        'created_at': row[2]
                    }
        except Exception as e:
            logger.error(f"获取日常总结失败: {e}")
        
        return None
    
    async def get_recent_summaries(self, user_id: str, days: int = 7) -> List[Dict]:
        """获取最近几天的总结"""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute('''
                    SELECT summary_date, summary_content, message_count
                    FROM daily_summaries 
                    WHERE user_id = ? AND summary_date >= ?
                    ORDER BY summary_date DESC
                ''', (user_id, start_date))
                
                summaries = []
                for row in cursor.fetchall():
                    summaries.append({
                        'date': row[0],
                        'summary': row[1],
                        'message_count': row[2]
                    })
                return summaries
        except Exception as e:
            logger.error(f"获取近期总结失败: {e}")
            return []
    
    async def cleanup_old_data(self):
        """清理过期数据"""
        try:
            memory_days = self.config.get('memory_config', {}).get('memory_days', 30)
            cutoff_date = (datetime.now() - timedelta(days=memory_days)).strftime('%Y-%m-%d')
            
            with sqlite3.connect(str(self.db_path)) as conn:
                # 清理旧的聊天记录
                cursor = conn.execute('''
                    DELETE FROM chat_records WHERE DATE(message_time) < ?
                ''', (cutoff_date,))
                deleted_messages = cursor.rowcount
                
                # 清理旧的总结（保留时间稍长一些）
                summary_cutoff = (datetime.now() - timedelta(days=memory_days * 2)).strftime('%Y-%m-%d')
                cursor = conn.execute('''
                    DELETE FROM daily_summaries WHERE summary_date < ?
                ''', (summary_cutoff,))
                deleted_summaries = cursor.rowcount
                
                conn.commit()
                
                if deleted_messages > 0 or deleted_summaries > 0:
                    logger.info(f"清理过期数据完成: 消息 {deleted_messages} 条, 总结 {deleted_summaries} 条")
                    
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")
    
    async def get_memory_stats(self) -> Dict:
        """获取记忆系统统计信息"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 总消息数
                cursor = conn.execute('SELECT COUNT(*) FROM chat_records')
                total_messages = cursor.fetchone()[0]
                
                # 总用户数
                cursor = conn.execute('SELECT COUNT(DISTINCT user_id) FROM chat_records')
                total_users = cursor.fetchone()[0]
                
                # 总结数
                cursor = conn.execute('SELECT COUNT(*) FROM daily_summaries')
                total_summaries = cursor.fetchone()[0]
                
                # 今日消息数
                today = datetime.now().strftime('%Y-%m-%d')
                cursor = conn.execute('SELECT COUNT(*) FROM chat_records WHERE DATE(message_time) = ?', (today,))
                today_messages = cursor.fetchone()[0]
                
                return {
                    'total_messages': total_messages,
                    'total_users': total_users,
                    'total_summaries': total_summaries,
                    'today_messages': today_messages,
                    'database_size': self.db_path.stat().st_size if self.db_path.exists() else 0
                }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}