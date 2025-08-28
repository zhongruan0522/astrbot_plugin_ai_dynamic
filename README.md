# AI智能动态助手

一个基于聊天记忆的个性化QQ动态发布插件，让AI帮你管理社交动态！

## ✨ 核心特性

### 🧠 智能记忆系统
- **自动记录**：实时保存白名单用户的聊天记录
- **智能总结**：每日自动生成聊天内容的总结分析
- **长期记忆**：可配置的记忆保存周期，支持数据自动清理

### 🤖 AI动态生成
- **个性化内容**：基于用户聊天记忆生成符合个人风格的动态
- **多种模式**：支持纯文本、图文混合等多种动态类型
- **智能文案**：为图片自动生成合适的描述文案

### ⏰ 智能调度系统
- **定时发布**：可配置每日发布次数和时间范围
- **智能间隔**：防止过于频繁发布，保持自然的发布节奏
- **随机性**：增加发布时间的随机性，避免机械化

### 💬 自动评论功能
- **好友互动**：自动评论指定好友的最新动态
- **智能回复**：根据动态内容生成合适的评论
- **可控概率**：可配置评论的触发概率

## 🚀 快速开始

### 安装插件

1. 将插件文件复制到 AstrBot 的 `data/plugins/` 目录
2. 重启 AstrBot 或在插件管理中重载插件

### 基础配置

#### 1. QQ空间配置
```yaml
qzone_config:
  qq_cookies: "你的QQ空间登录Cookies"
  user_agent: "浏览器User-Agent"
```

#### 2. 记忆系统配置
```yaml
memory_config:
  enable_memory: true
  user_whitelist: ["12345678", "87654321"]  # 要记录的用户QQ号
  memory_days: 30  # 记忆保存天数
  summary_time: "00:00"  # 每日总结时间
```

#### 3. 自动发布配置
```yaml
dynamic_config:
  enable_auto_post: true
  daily_post_count: 2  # 每日发布次数
  post_time_range:
    start_time: "09:00"
    end_time: "22:00"
  min_interval_hours: 3  # 最小发布间隔
```

### 获取QQ空间Cookies

1. 使用Chrome浏览器登录QQ空间
2. 按F12打开开发者工具
3. 切换到Network标签页
4. 刷新QQ空间页面
5. 找到任意请求，复制Request Headers中的Cookie值

## 📖 使用指南

### 基础命令

```bash
# 查看插件状态
/ai动态 状态

# 测试各项连接
/ai动态 测试连接

# 手动发布动态（基于记忆自动生成）
/ai动态 发布

# 发布指定内容的动态
/ai动态 发布 今天天气真不错！

# 发布带图片的动态（需要在消息中包含图片）
/ai动态 带图发布 分享一张美图
```

### 记忆管理

```bash
# 查看记忆系统状态
/ai动态 记忆

# 查看最近7天的总结
/ai动态 查看总结 7

# 手动生成昨天的总结
/ai动态 生成总结

# 生成指定日期的总结
/ai动态 生成总结 2024-01-01
```

## ⚙️ 高级配置

### 自定义提示词

插件支持自定义AI提示词，可在配置文件中修改：

```yaml
prompts:
  dynamic_prompt: "你是一个富有创意的社交媒体内容创作者..."
  comment_prompt: "你是一个善于社交的朋友..."
```

### 自定义API

支持使用自定义的OpenAI兼容API：

```yaml
api_config:
  enable_custom_api: true
  api_url: "https://api.openai.com/v1/chat/completions"
  api_key: "your-api-key"
  model_name: "gpt-3.5-turbo"
```

### 自动评论设置

```yaml
comment_config:
  enable_auto_comment: true
  target_users: ["12345678", "87654321"]  # 要评论的用户QQ号
  comment_probability: 30  # 评论概率(0-100)
  check_interval_minutes: 30  # 检查间隔
```

## 🛡️ 安全与隐私

- **数据安全**：所有聊天记录仅保存在本地数据库
- **隐私保护**：仅记录白名单用户的消息，不会泄露他人隐私
- **敏感信息**：Cookies等敏感信息请妥善保管
- **访问控制**：建议定期检查和更新白名单配置

## 🔧 故障排除

### 常见问题

**Q: 动态发布失败怎么办？**
A: 请检查QQ空间Cookies是否过期，可以重新获取并更新配置。

**Q: 自动总结没有生成？**
A: 确认用户在白名单中，且当天有足够的聊天记录（建议至少5条消息）。

**Q: LLM调用失败？**
A: 检查是否正确配置了AstrBot的LLM或自定义API配置。

### 日志调试

启用调试模式可以查看详细的运行日志：

```yaml
advanced_config:
  enable_debug: true
```

## 📊 数据管理

### 自动清理

插件会自动清理过期数据：
- 聊天记录：根据`memory_days`配置自动删除
- 总结数据：保留时间为记忆天数的2倍
- 定时执行：每天凌晨2点自动清理

### 数据备份

```yaml
advanced_config:
  data_backup: true
  backup_interval_days: 7
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个插件！

### 开发环境

1. Clone项目到本地
2. 安装依赖：`pip install -r requirements.txt`
3. 将项目链接到AstrBot插件目录
4. 启动AstrBot进行测试

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- 感谢 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 项目提供的优秀框架
- 感谢所有为这个项目做出贡献的开发者

---

**注意**：本插件仅供学习和个人使用，请遵守相关平台的服务条款。使用过程中产生的任何问题与本插件作者无关。