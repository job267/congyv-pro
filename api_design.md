
---

# `api_design.md`

# API Design - 基于蒸馏 Skill 的多入口智能对话系统

## 1. 文档目标

本文档用于定义系统的核心接口、请求结构、返回结构、模块通信方式和主要数据流，便于前后端联调和后端服务开发。

---

## 2. 设计原则

### 2.1 统一入口协议
Web 与微信入口都应尽量复用同一套核心对话逻辑，避免重复实现。

### 2.2 Skill 注入统一处理
所有聊天请求都应通过统一的对话服务进行 skill 加载、上下文拼接和模型调用。

### 2.3 会话优先
接口设计应围绕 `conversation_id` 展开，以支持多轮对话与历史管理。

### 2.4 预留扩展能力
接口应便于后续扩展：

- 多 skill
- 多渠道
- 多模型
- 流式输出
- 后台管理

---

## 3. 模块划分

系统后端建议分为以下核心模块：

- Skill 管理模块
- 会话管理模块
- 对话服务模块
- Web API 模块
- 微信接入模块
- 日志与健康检查模块

---

## 4. 核心数据对象

## 4.1 Skill 对象

```json
{
  "skill_id": "my_skill",
  "name": "我的Skill",
  "description": "某类风格化对话能力",
  "system_prompt": "系统提示内容",
  "style_rules": ["规则1", "规则2"],
  "thinking_rules": ["规则1", "规则2"],
  "boundary_rules": ["规则1", "规则2"],
  "version": "1.0.0",
  "status": "enabled"
}
```
---

## 4.2 Conversation 对象

```json
{
  "conversation_id": "c001",
  "user_id": "u001",
  "skill_id": "my_skill",
  "title": "默认会话",
  "channel": "web",
  "created_at": "2026-04-10T10:00:00",
  "updated_at": "2026-04-10T10:00:00"
}
```

## 4.3 Message 对象

```json
{
  "message_id": "m001",
  "conversation_id": "c001",
  "role": "user",
  "content": "你好",
  "token_count": 10,
  "created_at": "2026-04-10T10:00:00"
}
```

## 4.4 User 对象
```json
{
  "user_id": "u001",
  "nickname": "demo_user",
  "source_channel": "web",
  "external_id": "external_xxx"
}
```

## 5. API 列表总览
    Skill 相关
        GET /api/skills
        GET /api/skills/{skill_id}
    会话相关
        POST /api/conversations
        GET /api/conversations
        GET /api/conversations/{conversation_id}/messages
    聊天相关
        POST /api/chat
    微信相关
        POST /api/wechat/callback
    系统相关
        GET /api/health
## 6. Skill 接口设计
### 6.1 获取 Skill 列表
    接口

        GET /api/skills

    作用

        返回所有可用 skill 的简要信息。

    请求参数

        无

    返回示例

    ```json
    [
    {
        "skill_id": "my_skill",
        "name": "我的Skill",
        "description": "某种风格化对话能力",
        "avatar": "",
        "enabled": true
    }
    ]
    ```

### 6.2 获取 Skill 详情
    接口

        GET /api/skills/{skill_id}

    作用

        返回指定 skill 的详细信息。

    路径参数
        skill_id: skill 唯一标识
    返回示例
    ```json
    {
    "skill_id": "my_skill",
    "name": "我的Skill",
    "description": "某种风格化对话能力",
    "welcome_message": "你好，我可以帮你分析问题。",
    "enabled": true
    }
    ```

## 7. 会话接口设计
## 7.1 创建会话
    接口

        POST /api/conversations

    作用

        创建新的对话会话。

    请求体
```json
{
  "user_id": "u001",
  "skill_id": "my_skill",
  "channel": "web"
}
返回示例
{
  "conversation_id": "c001",
  "created_at": "2026-04-10T10:00:00"
}
```

## 7.2 获取用户会话列表
    接口

        GET /api/conversations?user_id=u001

    作用

        返回某个用户的全部会话记录。

    查询参数
        user_id: 用户 ID
    返回示例
```json
[
  {
    "conversation_id": "c001",
    "title": "职业规划咨询",
    "skill_id": "my_skill",
    "last_message": "这是最近一次回复摘要",
    "updated_at": "2026-04-10T10:00:03"
  }
]
```

## 7.3 获取会话历史消息
    接口

        GET /api/conversations/{conversation_id}/messages

    作用

        获取指定会话下的历史消息。

    路径参数
        conversation_id: 会话 ID
    返回示例
```json
[
  {
    "message_id": "m001",
    "role": "user",
    "content": "你好",
    "created_at": "2026-04-10T10:00:00"
  },
  {
    "message_id": "m002",
    "role": "assistant",
    "content": "你好，请问我可以帮你做什么？",
    "created_at": "2026-04-10T10:00:02"
  }
]
```
## 8. 聊天接口设计
### 8.1 发送消息
    接口

    POST /api/chat

    作用

    发起一次聊天请求，是系统的核心接口。

    请求体
```json
{
  "conversation_id": "c001",
  "user_id": "u001",
  "skill_id": "my_skill",
  "channel": "web",
  "message": "请帮我分析这个问题"
}
```
    字段说明
    conversation_id: 会话 ID，可为空；为空时可由系统自动创建
    user_id: 用户 ID
    skill_id: 当前使用的 skill
    channel: 请求来源，如 web 或 wechat
    message: 用户输入内容
    返回示例
```json
{
  "message_id": "m002",
  "conversation_id": "c001",
  "reply": "这是根据 skill 风格生成的回复。",
  "usage_info": {
    "prompt_tokens": 100,
    "completion_tokens": 200
  },
  "created_at": "2026-04-10T10:00:03"
}
```

## 9. 微信接口设计
### 9.1 微信回调接口
    接口

    POST /api/wechat/callback

    作用

    接收微信平台推送消息，并将其转化为系统内部对话请求。

    说明

    首期版本以接口预留为主，后续逐步补充：

    签名校验
    URL 验证
    XML 解析
    用户映射
    回复格式适配
    处理逻辑
    接收微信消息
    → 验证来源
    → 解析 external_id 和消息内容
    → 映射系统 user_id
    → 获取或创建 conversation
    → 调用 chat service
    → 返回微信格式响应

## 10. 系统接口设计
### 10.1 健康检查接口
    接口

    GET /api/health

    作用

    用于服务监控、部署检查和简单运维诊断。

    返回示例
```json
{
  "service_status": "ok",
  "model_status": "ok",
  "db_status": "ok"
}
```

## 11. 核心内部服务逻辑
### 11.1 Chat Service
    输入
    user_id
    conversation_id
    skill_id
    message
    channel
    处理流程
    接收请求
    → 参数校验
    → 获取或创建会话
    → 加载 skill
    → 获取历史消息
    → 裁剪上下文
    → 构造 prompt
    → 调用模型
    → 保存用户消息与回复
    → 返回结果
    输出
    reply
    conversation_id
    message_id
    usage_info
### 11.2 Skill Service
    输入
        skill_id
    处理流程
        读取 skill 元信息
        → 读取 skill.md
        → 解析配置
        → 生成结构化 skill 对象
        → 返回给 chat service
    输出
        skill 对象
### 11.3 Conversation Service
    输入
        user_id
        conversation_id
        skill_id
    处理流程
        检查会话是否存在
        → 不存在则创建
        → 存在则获取历史消息
        → 返回当前会话信息与上下文
    输出
        conversation 对象
        message history
## 12. 错误处理建议

    系统建议至少统一以下错误类型：

    参数错误
    会话不存在
    skill 不存在
    模型调用失败
    渠道回调格式错误
    系统内部异常

    推荐返回格式
```json
{
  "error_code": "MODEL_CALL_FAILED",
  "error_message": "模型调用失败，请稍后重试"
}
```
## 13. 数据存储建议

    建议至少有以下核心表或集合：

    skills
    users
    conversations
    messages
    logs
    关系说明
    一个 user 可以有多个 conversations
    一个 conversation 属于一个 skill
    一个 conversation 包含多条 messages
## 14. 后续扩展建议

    本文档设计时已预留以下扩展方向：

    多 skill 管理后台
    流式输出接口
    长期记忆
    RAG 检索增强
    多模型切换
    多渠道接入
    用户权限体系

