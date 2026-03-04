# FatieBot — Telegram 消息模板管理机器人

一个功能完整的 Telegram 机器人，支持消息模板创建、AI 改写去同质化、内联查询发送等核心功能。

---

## 功能列表

| 功能 | 说明 |
|------|------|
| ➕ 创建新消息 | 手动填写文字、图片、按钮，自动生成唯一密钥 |
| 🤖 AI 创建 | 输入产品描述，AI 自动生成宣传文案 + 配图 |
| 📋 我的消息 | 查看所有消息，支持分页，可预览/编辑/删除 |
| ✏️ 编辑消息 | 修改文字、图片或按钮 |
| 🗑️ 删除消息 | 二次确认后删除 |
| 🤖 AI 改写 | 一键生成最多 10 条变体，保留原意但表述不同 |
| 🚀 Inline 发送 | 在任意聊天输入 `@机器人 密钥` 即可一键发送 |

---

## 安装步骤

### 前置要求

- Python 3.10+
- pip

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/fatiebot.git
cd fatiebot
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_PATH=./data/bot.db
LOG_LEVEL=INFO
```

---

## 配置说明

### 如何获取 Bot Token

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot`
3. 按提示填写机器人名称和用户名
4. BotFather 会返回 Bot Token，复制到 `.env` 中

### 开启 Inline 模式

1. 找到 `@BotFather`，发送 `/mybots`
2. 选择你的机器人 → Bot Settings → Inline Mode → Turn on

---

## 运行方法

### 本地运行

```bash
cd fatiebot
python bot.py
```

看到 `机器人启动成功，开始轮询...` 表示运行正常。

---

## 使用示例

### 创建消息

1. 向机器人发送 `/start`
2. 点击「➕ 创建新消息」
3. 按提示发送文字、图片（可选）、按钮（可选）
4. 确认后机器人生成密钥，如 `abc123`

### 发送消息（Inline 模式）

在任意聊天的输入框中输入：

```
@你的机器人用户名 abc123
```

点击弹出的预览卡片即可发送。

### AI 改写

1. 进入「📋 我的消息」，选择一条消息
2. 点击「🤖 AI 改写」
3. AI 自动生成最多 10 条变体并随机展示一条
4. 每次 Inline 调用时随机返回一条变体

---

## 常见问题

**Q: AI 改写/AI 创建失败怎么办？**
A: Pollinations.AI 为免费公共服务，偶尔会超时。请稍等片刻后重试。

**Q: Inline 模式不显示结果？**
A: 请确认已在 BotFather 中开启 Inline Mode，并且消息密钥输入正确。

**Q: 图片在 Inline 模式下不显示？**
A: Telegram inline 模式不支持本地上传的图片（file_id），仅支持公开 HTTP/HTTPS 图片 URL。AI 创建的图片可在 Inline 中正常显示。

---

## 技术架构

```
fatiebot/
├── bot.py              # 主程序入口，注册所有 Handler
├── config.py           # 配置（读取环境变量）
├── database.py         # SQLite 数据库操作
├── ai_service.py       # Pollinations.AI 接口封装
├── requirements.txt
├── .env.example
├── handlers/
│   ├── start.py        # /start、主菜单
│   ├── create.py       # 创建消息（ConversationHandler）
│   ├── ai_create.py    # AI 创建（ConversationHandler）
│   ├── list.py         # 消息列表与详情
│   ├── edit.py         # 编辑消息（ConversationHandler）
│   ├── delete.py       # 删除消息、AI 改写
│   └── inline.py       # Inline 查询
├── utils/
│   ├── keyboards.py    # 所有 InlineKeyboardMarkup 定义
│   ├── helpers.py      # 密钥生成、按钮解析等工具函数
│   └── validators.py   # 输入验证
└── models/
    └── message.py      # Message 数据类
```

**数据库表：**

- `messages`：存储消息模板（text、image_url、buttons JSON、唯一 key）
- `message_variants`：存储 AI 改写生成的变体，外键关联 messages

**AI 服务：**

- 文本生成：`https://text.pollinations.ai/{prompt}`（免费，无需 API Key）
- 图片生成：`https://image.pollinations.ai/prompt/{description}`（免费，无需 API Key）

---

## 部署说明

### Linux 服务器（systemd）

创建服务文件 `/etc/systemd/system/fatiebot.service`：

```ini
[Unit]
Description=FatieBot Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/fatiebot
ExecStart=/usr/bin/python3 bot.py
Restart=on-failure
EnvironmentFile=/path/to/fatiebot/.env

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable fatiebot
sudo systemctl start fatiebot
sudo systemctl status fatiebot
```

### Docker 部署

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

构建并运行：

```bash
docker build -t fatiebot .
docker run -d --env-file .env --name fatiebot fatiebot
```
