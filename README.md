# Termux WebUI

在安卓手机上（Termux）跑一个本地 WebUI。FastAPI / Starlette 双后端 + SQLite，前端零依赖、零 CDN。

包含四个模块：**笔记**、**文件上传下载**、**AI 绘图**（手动接入任意图片生成 API）、**系统信息**。

界面为紫蓝液态玻璃风格，移动端优先，支持 iOS/Android 安全区。

---

## 目录

- [特点](#特点)
- [完整部署流程（Termux）](#完整部署流程termux)
- [启动与停止](#启动与停止)
- [日常维护](#日常维护)
- [配置说明](#配置说明)
- [绘图模块配置](#绘图模块配置)
- [接口一览](#接口一览)
- [目录结构](#目录结构)
- [常见问题](#常见问题)
- [其他部署方式](#其他部署方式)

---

## 特点

- **双后端自动降级**：`import fastapi` 成功就用 FastAPI（额外送 `/docs` 交互文档）；失败自动退到 Starlette，**业务代码一行都不用改**。
  这条是为 Termux 准备的：`fastapi → pydantic → pydantic-core` 是 Rust 写的，官方不提供 bionic 预编译包，Termux 上装它会进入源码编译，常常几十分钟后失败。
- **零外部前端依赖**：没有 npm、没有打包、没有 CDN，只有 `index.html` + `style.css` + `app.js` 三个文件。
- **零额外 Python 依赖**：除了 uvicorn / starlette / python-multipart，图片生成用标准库 `urllib` + 线程池实现，不引入 httpx / aiohttp / Pillow。
- **SQLite 存储**：只用标准库 `sqlite3`。数据全在 `data/` 一个目录里，拷走即迁移。
- **手机适配**：移动优先布局、安全区内边距、大点击区域、`<input type=file>` 直连相册与文件管理器。

---

## 完整部署流程（Termux）

### 0. 前置说明

- 需要能联网，且 GitHub 可访问（国内网络可能需要代理）。
- 全程在 Termux 里操作，不需要 root。
- 下面的命令**逐条执行**，不要整段粘贴（Termux 粘贴多行容易乱）。

### 1. 安装基础工具

```bash
pkg update -y
```

```bash
pkg install -y git python
```

> `python` 在 Termux 上是 bionic 版本，不要和系统 Python 混用。

### 2. 克隆仓库

```bash
cd ~
git clone https://github.com/wenbo-ux/-ui.git
```

⚠️ **仓库名以 `-` 开头**，直接 `cd -ui` 会被 shell 当成命令选项。必须这样进：

```bash
cd -- -ui
```

> 嫌麻烦可以克隆时改名：`git clone https://github.com/wenbo-ux/-ui.git webui`，之后就是干净的 `cd ~/webui`。

### 3. 创建虚拟环境

```bash
python -m venv .venv
```

```bash
. .venv/bin/activate
```

激活后提示符前面会出现 `(.venv)`。**之后所有命令都必须在这个虚拟环境里执行**，否则找不到依赖。

### 4. 安装依赖

先升级 pip：

```bash
pip install --upgrade pip
```

然后**安装轻量版**（推荐，纯 Python 轮子，几十秒装完）：

```bash
pip install -r requirements-minimal.txt
```

这会装上：`starlette` + `uvicorn` + `python-multipart`。

---

<details>
<summary><b>如果你想试完整版（带 /docs 接口文档）</b></summary>

```bash
pip install -r requirements.txt
```

会开始编译 `pydantic-core`，输出类似：

```
Collecting pydantic-core==2.50.1
  Downloading pydantic_core-2.50.1.tar.gz (513 kB)
  Installing build dependencies ... /
```

这一步要下载并编译 Rust 工具链，**通常 20 分钟以上，且大概率失败**。

**不要等，直接 `Ctrl+C` 中断**，然后执行：

```bash
pip install -r requirements-minimal.txt
```

功能完全一样，只是少了 `/docs` 那个自动生成的接口文档页面。启动时后端会显示 `starlette` 而不是 `fastapi`。

</details>

### 5. 生成配置文件

```bash
cp .env.example .env
```

### 6. 启动

```bash
python run.py
```

看到这样的输出就成功了：

```
====================================================
  Termux WebUI
  后端     : starlette
  本机访问 : http://127.0.0.1:8000
  局域网   : http://192.168.x.x:8000
  数据目录 : data
====================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 7. 访问

- **手机自己浏览器**：`http://127.0.0.1:8000`
- **同一 Wi-Fi 的其他设备**：`http://<手机局域网IP>:8000`
  （IP 在启动日志的「局域网」那行已经打印出来了）

---

## 启动与停止

### 停止

在终端按 `Ctrl+C`。

> Termux 里按 `Ctrl`：先点键盘工具条上的 `CTRL` 键，或从屏幕左侧边缘滑出键盘工具条。

### 重新启动

**Termux 大退后再进来，`.venv` 不会自动激活**，必须重新激活，否则会报 `ModuleNotFoundError: No module named 'uvicorn'`。

```bash
cd -- -ui
. .venv/bin/activate
python run.py
```

### 更省事的写法（不用激活）

```bash
cd -- -ui && .venv/bin/python run.py
```

### 做成命令别名

```bash
echo "alias webui='cd -- ~/-ui && .venv/bin/python run.py'" >> ~/.bashrc
source ~/.bashrc
```

以后任何目录下输入 `webui` 即可启动。

### 后台常驻

```bash
termux-wake-lock
```

阻止系统休眠导致进程被杀。取消用 `termux-unlock`。

真正开机自启需要装 [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) 插件，然后：

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-webui.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
cd -- ~/-ui && .venv/bin/python run.py
EOF
chmod +x ~/.termux/boot/start-webui.sh
```

---

## 日常维护

### 更新到最新代码

```bash
cd -- -ui
git pull
python run.py
```

依赖没变的话，**不需要重装任何东西**，`.venv` 会一直保留。

### 如果依赖也变了

不确定就把这条顺手跑一遍，没变化时它秒结束：

```bash
. .venv/bin/activate && pip install -r requirements-minimal.txt
```

### 什么情况需要重来

| 操作 | 要重来吗 |
|---|---|
| 改业务代码 | ❌ 只重启 |
| 改前端 HTML/CSS/JS | ❌ 只重启（浏览器需刷新） |
| `git pull` 拉更新 | ❌ 只重启 |
| 新增 Python 依赖 | ✅ 补 `pip install` |
| 删掉 `.venv` | ✅ 重建 venv + 装依赖 |
| 换手机 / 重装 Termux | ✅ 全部重来 |

### 更新时本地有改动

```bash
git stash        # 暂存
git pull
git stash pop    # 取回
```

无条件跟远程、丢弃本地改动：

```bash
git checkout -- .
git pull
```

### 不会被覆盖的东西

`data/`（数据库和上传的文件）、`.env`（端口和 token）都在 `.gitignore` 里，`git pull` 不会动它们。

---

## 配置说明

编辑 `.env`：

```bash
cd -- -ui
nano .env          # 或 micro / vim
```

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_NAME` | Termux WebUI | 页面标题 |
| `HOST` | `0.0.0.0` | 监听地址。`0.0.0.0` 才能被局域网访问；改 `127.0.0.1` 则只有本机能连 |
| `PORT` | `8000` | 端口 |
| `RELOAD` | `0` | `1` = 改代码自动重载（开发用，略耗性能） |
| `DATA_DIR` | `./data` | 数据目录（SQLite + 上传文件 + 生成图片） |
| `MAX_UPLOAD_MB` | `50` | 单文件上传上限 |
| `APP_TOKEN` | 空 | 填了就要求鉴权 |

### 改端口

**关键**：酒馆（SillyTavern）默认也是 8000 端口，两个同时开会冲突，报：

```
ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8000): address already in use
```

改掉本项目的端口即可：

```bash
sed -i 's/^PORT=.*/PORT=8080/' .env
```

或者临时指定不写进文件：

```bash
PORT=8080 .venv/bin/python run.py
```

推荐分配：

| 服务 | 端口 |
|---|---|
| 酒馆 SillyTavern | 8000 |
| 本项目 | 8080 |

### 设访问密码

手机接公共 Wi-Fi 时必做，否则同网段任何人都能读写你的文件和笔记：

```bash
echo "APP_TOKEN=$(head -c 16 /dev/urandom | base64)" >> .env
```

重启后访问一次 `http://<IP>:8080/?token=你的token`，前端会把 token 存进 localStorage，之后自动带上。

接口层面也支持 `X-Token` 请求头。首页 `/` 不鉴权（它只是静态页面，数据都靠带 token 的 API 拿）。

---

## 绘图模块配置

「绘图」标签 → 点开「⚙️ API 配置」→ 填四个字段 → 保存。

可以存多个 provider，生成时下拉切换。`api_key` 加密不了（本地 SQLite 明文存储），但接口返回和列表里始终是掩码 `****abcd`，不会回显完整 key。

### 四种接口格式

| 类型 | 说明 | 什么时候用 |
|---|---|---|
| `openai_images` | `POST /v1/images/generations` | OpenAI、硅基流动、**绝大多数中转站** |
| `openai_chat` | `POST /v1/chat/completions` + `modalities:["image","text"]` | Gemini 系中转、多模态模型出图 |
| `gemini` | 原生 `generateContent` + `responseModalities` | 直连 Google |
| `dashscope` | 阿里万相异步任务（自动 3 秒轮询） | 直连阿里百炼 |

### Base URL 填法

| 服务 | Base URL | 类型 | 模型名 |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `openai_images` | `gpt-image-1` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `openai_images` | `Kwai-Kolors/Kolors` |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4` | `openai_images` | `cogview-4` |
| 阿里万相 | `https://dashscope.aliyuncs.com/api/v1` | `dashscope` | `wanx2.1-t2i-turbo` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta` | `gemini` | `gemini-2.5-flash-image` |
| New API 类中转 | `https://你的域名/v1` | `openai_images` | 见下方「查模型」 |

⚠️ **中转站的 Base URL 必须带 `/v1`**。少了会打到它的网页首页，你会收到：

```
⚠ 返回的不是 JSON: <!doctype html>... <title>New API</title>
```

### 怎么查站点支持哪些图片模型

在 Termux 里跑（换成你的域名和 key）：

```bash
curl -s https://你的域名/v1/models \
  -H "Authorization: Bearer 你的key" \
  | python3 -c "
import json,sys
ids=[m['id'] for m in json.load(sys.stdin)['data']]
kw=('image','dall','flux','seedream','cogview','qwen-image','stable','sdxl','kolors','hunyuan','wanx','imagen')
hit=[i for i in ids if any(k in i.lower() for k in kw)]
print('图片模型：')
[print(' ',i) for i in hit] or print('  （一个都没有，这家站没开图像接口）')
"
```

挑一个填进「模型名」，**原样照抄，包括大小写和斜杠**。

### 常见报错对照

| 报错 | 原因 | 解决 |
|---|---|---|
| `返回的不是 JSON: <!doctype html>` | Base URL 少了 `/v1`，打到网页首页 | 补上 `/v1` |
| `503 model_not_found` / `No available channel` | 分组下没有这个模型 | 换模型名，或站点没开该权限 |
| `400 images endpoint requires an image model` | 拿聊天模型调图片接口 | 换图片模型，如 `gpt-image-1` / `flux-schnell` |
| `401 unauthorized` | key 错或过期 | 重新生成 key |
| `生成失败：轮询超时` | dashscope 任务太久 | 稍后重试；复杂提示词更慢 |

失败也会写一条记录进画廊（显示红色错误），不会静默丢掉，方便排查。

### 关于图片的存储

生成的图片存在 `data/images/`，记录在 SQLite 的 `images` 表。扩展名靠**魔数嗅探**（PNG/JPEG/WEBP），不信任 API 返回值。

---

## 接口一览

响应统一格式：成功 `{"ok": true, "data": ...}`，失败 `{"ok": false, "error": "..."}`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回后端类型与运行时长 |
| GET | `/api/sysinfo` | 系统信息（CPU/磁盘/平台） |
| GET | `/api/notes` | 笔记列表 |
| POST | `/api/notes` | 新建笔记 `{title, body}` |
| PUT | `/api/notes/{id}` | 更新笔记 |
| DELETE | `/api/notes/{id}` | 删除笔记 |
| GET | `/api/uploads` | 文件列表 |
| POST | `/api/uploads` | 上传（multipart，字段名 `files`，可多个） |
| GET | `/api/uploads/{name}/download` | 下载 |
| DELETE | `/api/uploads/{name}` | 删除 |
| GET | `/api/providers/kinds` | 支持的 provider 类型 |
| GET | `/api/providers` | 列出图片 API 配置（key 掩码） |
| POST | `/api/providers` | 新增配置 |
| PUT | `/api/providers/{id}` | 修改配置 |
| DELETE | `/api/providers/{id}` | 删除配置 |
| GET | `/api/images` | 生成记录（含失败的） |
| POST | `/api/images` | 生成图片 `{provider_id, prompt, size, n}` |
| GET | `/api/images/file/{name}` | 查看图片 |
| DELETE | `/api/images/{id}` | 删除图片 |

装了 FastAPI 时，`/docs` 有可交互的完整文档。

---

## 目录结构

```
termux-webui/
├── run.py                    # 启动入口（薄封装）
├── app/
│   ├── main.py               # ASGI 装配，打印启动横幅
│   ├── compat.py             # ★ FastAPI / Starlette 双后端兼容层
│   ├── config.py             # 配置 + 极简 .env 解析（不依赖 python-dotenv）
│   ├── db.py                 # SQLite 存储层
│   ├── api.py                # 全部路由 + ROUTES 表
│   ├── providers.py          # ★ 四种图片 API 适配器
│   ├── templates/index.html
│   └── static/
│       ├── style.css         # 紫蓝液态玻璃主题
│       └── app.js            # 原生 JS，无框架
├── requirements.txt          # 完整版（FastAPI）
├── requirements-minimal.txt  # 轻量版（Starlette，推荐）
├── setup-termux.sh           # 一键安装脚本
├── .env.example
└── data/                     # 运行时生成，已在 .gitignore
    ├── app.db
    ├── uploads/
    └── images/
```

### 怎么加新模块

1. `app/db.py` 里加表和读写方法
2. `app/api.py` 里写 handler，往 `ROUTES` 列表加一行 `compat.Route(...)`
3. `app/templates/index.html` 加一个 `<button class="tab" data-tab="xxx">` 和一个 `<section class="panel" id="panel-xxx">`
4. `app/static/app.js` 里写加载逻辑（照着现有的抄）

---

## 常见问题

### 启动报 `ModuleNotFoundError: No module named 'uvicorn'`

虚拟环境没激活。先 `. .venv/bin/activate`，或直接用 `.venv/bin/python run.py`。

### 启动报 `address already in use`（errno 98）

端口被占。八成是酒馆。改 `.env` 里的 `PORT`，或先 `pkill -f run.py`。

查谁占了：

```bash
pkg install net-tools
netstat -tuln | grep 8000
```

### 局域网其他设备连不上

1. 确认 `.env` 里是 `HOST=0.0.0.0`（不是 `127.0.0.1`）
2. 确认两台设备在**同一个 Wi-Fi**（手机热点和路由器网段不同会连不上）
3. 有些路由器开了「AP 隔离」，会挡住内网互访，需要在路由器设置里关掉
4. 用启动日志里打印的「局域网」那个 IP，不要用 `127.0.0.1`

### `pip install` 卡在 `Building wheel for pydantic-core`

正常现象，Termux 在编译 Rust。`Ctrl+C` 中断，改用 `requirements-minimal.txt`。

### 页面打开是空白 / 只有顶栏

浏览器缓存了旧 CSS。强制刷新：下拉刷新，或在浏览器设置里清除该站点数据。

### 前端改完没反应

`RELOAD=1` 只重载 Python 后端，前端文件要**刷新浏览器**才生效。CSS 缓存强的话加个 `?v=2` 参数。

### Termux 后台一会儿就断了

系统杀了进程。先 `termux-wake-lock`，再去系统设置里给 Termux 关掉电池优化。

### 数据怎么备份

整个 `data/` 目录拷走就行：

```bash
cd -- -ui
tar -czf ~/webui-backup-$(date +%m%d).tar.gz data/
```

恢复到新环境时，把 `data/` 放回项目根目录即可。

### 公网访问怎么办

**不要**直接在路由器上把端口映射出去。用内网穿透：

```bash
pkg install cloudflared
cloudflared tunnel --url http://127.0.0.1:8000
```

会给你一个临时公网地址。长期用建议配 Tailscale 或自建 frp。

---

## 其他部署方式

### 普通 Linux / macOS / Windows

```bash
git clone https://github.com/wenbo-ux/-ui.git termux-webui
cd termux-webui
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt   # 这里可以直接用完整版，不会编译痛苦
cp .env.example .env
python run.py
```

### 直接跑 uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 用 setup-termux.sh 一键装

```bash
bash setup-termux.sh
```

它会依次执行：`pkg update` → 装 python → 建 venv → 装依赖（完整版失败自动回退轻量版）→ 生成 `.env`。适合全新环境。

---

## 已知限制

- **无多用户**：单 token 或完全开放，没有账号体系。
- **无 HTTPS**：本地跑不需要；公网请用隧道工具。
- **API key 明文存储**：存在本地 SQLite，仅做接口回显掩码。手机丢了别人能读。
- **图片生成是同步等待**：请求会挂住直到出图（超时 180 秒）。长任务建议后续改成任务队列。
- **`backdrop-filter` 在低端机有开销**：觉得卡就把 `style.css` 里 `.glass` 的 `backdrop-filter` 改小或去掉。

---

## License

MIT
