# AstrBot 自动发朋友圈插件

## 概述

这是一个功能强大的AstrBot插件，能够自动保存聊天记录，使用AI智能生成朋友圈文案，并定时发布到QQ空间。插件还具备记忆管理功能，能够自动总结和保存重要信息。

## 🚀 核心功能

### 1. 智能聊天记录管理
- 自动保存所有聊天记录到临时文件
- 按日期组织存储，便于检索和管理
- 自动清理过期的聊天记录

### 2. AI文案生成
- 基于聊天记录和记忆信息生成个性化朋友圈文案
- 支持自定义提示词，让AI生成符合个人风格的文案
- 集成多种AI服务提供商，确保文案质量

### 3. 智能记忆系统
- AI自动总结聊天记录，形成结构化记忆
- 支持不同类型的记忆（日常、周记、月记等）
- 记忆持久化存储，避免信息丢失

### 4. 定时自动发布
- 在设定的时间范围内随机时间点发布朋友圈
- 支持设置每日最大发布次数
- 智能调度，避免频繁发布

### 5. QQ空间集成
- 无缝集成QQ空间API
- 支持文本和图片发布
- 自动获取QQ客户端Cookie，实现隐形登录

## 📋 系统要求

- **AstrBot**: >= 3.4.0
- **Python**: >= 3.8
- **依赖库**: aiohttp, aiosqlite, pydantic, aiocqhttp
- **QQ客户端**: 支持aiocqhttp的QQ个人号

## 🛠️ 安装和配置

### 1. 安装插件

```bash
# 克隆插件仓库
git clone https://github.com/yourusername/astrbot_plugin_auto_moments.git

# 将插件放置到AstrBot插件目录
cp -r astrbot_plugin_auto_moments /path/to/astrbot/data/plugins/

# 安装依赖
cd /path/to/astrbot/data/plugins/astrbot_plugin_auto_moments
pip install -r requirements.txt
```

### 2. 配置插件

插件提供了丰富的配置选项，可以通过AstrBot管理面板进行配置：

#### 基础配置
- **自动发布**: 是否启用自动发朋友圈功能
- **发布时间**: 设置每日发布时间段（格式：HH:MM-HH:MM）
- **最大次数**: 每日最大发布次数
- **总结时间**: 每日记忆总结时间

#### AI配置
- **文案提示词**: 自定义AI生成朋友圈文案的提示词
- **记忆提示词**: 自定义AI总结记忆的提示词

#### 数据管理
- **聊天保存天数**: 聊天记录保存天数
- **管理员列表**: 管理员QQ号列表

### 3. 启动插件

1. 在AstrBot WebUI中找到"自动发朋友圈"插件
2. 点击"启用"按钮
3. 确保QQ客户端正常运行（插件会自动登录）

## 📖 使用指南

### 基础命令

#### 朋友圈管理
```
/主动动态 [提示词]   # 手动发布朋友圈
/查看说说 [数量]    # 查看最近的说说
```

#### 记忆管理
```
/查看记忆 [数量]    # 查看最近记忆
/总结记忆 [天数]    # 手动总结记忆
/清理记忆 [天数]    # 清理旧记忆
```

#### 聊天记录管理
```
/清理聊天 [天数]    # 清理旧聊天记录
```

#### 配置管理
```
/设置自动 [true/false]  # 开启/关闭自动发布
/查看配置          # 查看当前配置
```

### 高级功能

#### 1. 自定义提示词

可以通过配置面板设置个性化的AI提示词：

**朋友圈文案提示词示例**：
```
请根据以下聊天记录和记忆信息，生成一条适合发朋友圈的文案。要求：
1. 语言风格要活泼有趣，带点小幽默
2. 可以适当使用emoji表情
3. 内容要积极向上，传递正能量
4. 长度控制在100-200字之间
```

**记忆总结提示词示例**：
```
请总结以下聊天记录，提取重要信息形成记忆。要求：
1. 重点关注情感变化和重要事件
2. 提取关键的人名、地点、时间等信息
3. 按时间顺序组织内容
4. 保持简洁明了，便于后续回顾
```

#### 2. 定时策略

插件支持灵活的定时发布策略：

- **时间范围**: 可以设置每天的有效发布时间段
- **随机发布**: 在时间范围内随机选择发布时间
- **频率控制**: 可以设置每日最大发布次数

#### 3. 记忆管理

记忆系统支持多种类型：

- **日常记忆**: 每日自动总结的重要信息
- **周记记忆**: 每周的生活和工作总结
- **月记记忆**: 每月的成长和变化记录
- **手动记忆**: 用户主动创建的重要记录

## 🏗️ 架构设计

### 核心模块

```
astrbot_plugin_auto_moments/
├── main.py                 # 主插件入口
├── core/                   # 核心功能模块
│   ├── __init__.py
│   ├── memory.py          # 记忆和聊天记录管理
│   ├── ai_generator.py    # AI文案生成和调度
│   └── qzone_api.py       # QQ空间API接口
├── metadata.yaml           # 插件元数据
├── requirements.txt       # 依赖库列表
└── _conf_schema.json      # 配置模式定义
```

### 数据流架构

```
聊天消息 → 聊天记录管理 → AI记忆总结 → 记忆存储
    ↓
AI文案生成 ← 调度器 ← 配置管理
    ↓
QQ空间API → 朋友圈发布
```

### 关键组件

#### 1. MemoryManager
- 负责记忆数据的存储和检索
- 支持多种记忆类型
- 自动清理过期记忆

#### 2. ChatRecorder
- 管理聊天记录的保存和清理
- 按日期组织数据
- 支持临时文件存储

#### 3. AIGenerator
- 集成AI服务提供商
- 生成朋友圈文案和记忆总结
- 支持自定义提示词

#### 4. PostScheduler
- 管理定时发布任务
- 支持随机时间选择
- 智能调度策略

#### 5. QzoneAPI
- 封装QQ空间接口
- 支持Cookie认证
- 处理图片上传和发布

## 🔧 配置详解

### _conf_schema.json

```json
{
  "post_prompt": {
    "description": "生成朋友圈文案的提示词",
    "type": "text",
    "default": "请根据以下聊天记录和记忆信息，生成一条适合发朋友圈的文案..."
  },
  "memory_prompt": {
    "description": "总结记忆的提示词", 
    "type": "text",
    "default": "请总结以下聊天记录，提取重要信息形成记忆..."
  },
  "schedule_time": {
    "description": "每日自动发朋友圈的时间段",
    "type": "string",
    "default": "09:00-22:00"
  },
  "max_posts_per_day": {
    "description": "每日最大发朋友圈次数",
    "type": "int",
    "default": 3
  },
  "memory_summary_time": {
    "description": "每日总结记忆的时间",
    "type": "string", 
    "default": "23:00"
  },
  "chat_save_duration": {
    "description": "聊天记录保存天数",
    "type": "int",
    "default": 7
  },
  "enable_auto_post": {
    "description": "是否启用自动发朋友圈",
    "type": "bool",
    "default": true
  },
  "admins_id": {
    "description": "管理员QQ号列表",
    "type": "list",
    "default": []
  }
}
```

## 🚨 注意事项

### 1. 隐私保护
- 聊天记录仅保存在本地，不会上传到外部服务器
- 支持自动清理过期数据
- 管理员可以手动清理敏感数据

### 2. 使用限制
- 仅支持QQ个人号客户端
- 需要保持QQ客户端在线
- 遵守QQ空间的使用规则

### 3. 性能考虑
- 合理设置发布频率，避免过于频繁
- 定期清理过期数据，节省存储空间
- 监控API调用次数，避免触发限制

## 🐛 常见问题

### Q: QQ空间连接失败怎么办？
A: 请确保：
1. 使用的是QQ个人号客户端
2. QQ客户端正常运行
3. 网络连接正常
4. QQ账号有权限访问QQ空间

### Q: AI生成文案质量不佳？
A: 可以：
1. 调整AI提示词
2. 确保有足够的聊天记录
3. 检查AI服务配置
4. 尝试不同的AI模型

### Q: 自动发布不工作？
A: 请检查：
1. 是否启用了自动发布功能
2. 时间设置是否正确
3. QQ客户端是否正常运行
4. 调度器是否正常运行

### Q: 记忆总结不准确？
A: 可以：
1. 优化记忆提示词
2. 增加聊天记录数量
3. 调整总结频率
4. 手动修正重要记忆

## 🔄 更新日志

### v1.0.0 (2025-09-02)
- 初始版本发布
- 实现基本功能：聊天记录保存、AI文案生成、记忆管理
- 集成QQ空间API
- 支持定时自动发布
- 提供丰富的配置选项

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个插件！

### 开发环境设置
```bash
# 克隆仓库
git clone https://github.com/yourusername/astrbot_plugin_auto_moments.git
cd astrbot_plugin_auto_moments

# 安装开发依赖
pip install -r requirements.txt
```

### 代码规范
- 遵循PEP 8 Python代码规范
- 添加适当的注释和文档
- 编写测试用例
- 确保代码安全性和稳定性

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 📞 联系方式

- **问题反馈**: [GitHub Issues](https://github.com/yourusername/astrbot_plugin_auto_moments/issues)
- **功能建议**: [GitHub Discussions](https://github.com/yourusername/astrbot_plugin_auto_moments/discussions)
- **作者邮箱**: your.email@example.com

---

**感谢使用AstrBot自动发朋友圈插件！** 🎉