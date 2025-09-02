from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os

@dataclass
class ChatMessage:
    """聊天消息数据模型"""
    id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: int
    group_id: Optional[str] = None
    images: List[str] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []

@dataclass
class Memory:
    """记忆数据模型"""
    id: str
    content: str
    created_at: int
    updated_at: int
    summary_type: str  # daily, weekly, monthly
    
class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.memory_file = os.path.join(data_dir, "memories.json")
        self.memories: List[Memory] = []
        self._load_memories()
    
    def _load_memories(self):
        """加载记忆数据"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories = [Memory(**item) for item in data]
            except Exception as e:
                print(f"加载记忆失败: {e}")
                self.memories = []
    
    def save_memories(self):
        """保存记忆数据"""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                data = [memory.__dict__ for memory in self.memories]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存记忆失败: {e}")
    
    def add_memory(self, content: str, summary_type: str = "daily") -> Memory:
        """添加新记忆"""
        memory = Memory(
            id=f"mem_{int(datetime.now().timestamp())}",
            content=content,
            created_at=int(datetime.now().timestamp()),
            updated_at=int(datetime.now().timestamp()),
            summary_type=summary_type
        )
        self.memories.append(memory)
        self.save_memories()
        return memory
    
    def get_memories(self, limit: int = 10) -> List[Memory]:
        """获取最近的记忆"""
        return sorted(self.memories, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def get_memories_by_type(self, summary_type: str) -> List[Memory]:
        """根据类型获取记忆"""
        return [m for m in self.memories if m.summary_type == summary_type]
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        self.memories = [m for m in self.memories if m.id != memory_id]
        self.save_memories()
        return True
    
    def clear_old_memories(self, days: int = 30):
        """清理旧记忆"""
        cutoff_time = int(datetime.now().timestamp()) - (days * 24 * 60 * 60)
        self.memories = [m for m in self.memories if m.created_at > cutoff_time]
        self.save_memories()

class ChatRecorder:
    """聊天记录管理器"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.temp_dir = os.path.join(data_dir, "temp_chats")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def save_chat_message(self, message: ChatMessage):
        """保存聊天消息到临时文件"""
        date_str = datetime.fromtimestamp(message.timestamp).strftime("%Y-%m-%d")
        file_path = os.path.join(self.temp_dir, f"chats_{date_str}.json")
        
        # 加载现有数据
        chats = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    chats = json.load(f)
            except Exception:
                chats = []
        
        # 添加新消息
        chats.append(message.__dict__)
        
        # 保存数据
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(chats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存聊天记录失败: {e}")
    
    def get_today_chats(self) -> List[ChatMessage]:
        """获取今日聊天记录"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.temp_dir, f"chats_{date_str}.json")
        
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [ChatMessage(**item) for item in data]
        except Exception:
            return []
    
    def get_recent_chats(self, days: int = 7) -> List[ChatMessage]:
        """获取最近几天的聊天记录"""
        all_chats = []
        cutoff_time = int(datetime.now().timestamp()) - (days * 24 * 60 * 60)
        
        for filename in os.listdir(self.temp_dir):
            if filename.startswith("chats_") and filename.endswith(".json"):
                file_path = os.path.join(self.temp_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        chats = [ChatMessage(**item) for item in data 
                                if item.get('timestamp', 0) > cutoff_time]
                        all_chats.extend(chats)
                except Exception:
                    continue
        
        return sorted(all_chats, key=lambda x: x.timestamp, reverse=True)
    
    def clean_old_chats(self, days: int = 7):
        """清理旧的聊天记录"""
        cutoff_time = int(datetime.now().timestamp()) - (days * 24 * 60 * 60)
        
        for filename in os.listdir(self.temp_dir):
            if filename.startswith("chats_") and filename.endswith(".json"):
                file_path = os.path.join(self.temp_dir, filename)
                
                # 检查文件是否有过期数据
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 过滤有效数据
                    valid_data = [item for item in data if item.get('timestamp', 0) > cutoff_time]
                    
                    if valid_data:
                        # 重写文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(valid_data, f, ensure_ascii=False, indent=2)
                    else:
                        # 删除空文件
                        os.remove(file_path)
                except Exception:
                    # 删除损坏的文件
                    try:
                        os.remove(file_path)
                    except:
                        pass