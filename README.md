# Termux WebUI

在安卓手机上（Termux）跑一个本地 WebUI。FastAPI + SQLite，前端零依赖。

## 特点

- **双后端自动降级**：装了 FastAPI 就用（额外送 `/docs`）；装不上（Termux 上 `pydantic-core` 需要 Rust 编译）自动退到 Starlette，**业务代码一行都不用改**。
- **零外部前端依赖**：没有 npm、没有 CDN，一个 HTML + 一个 CSS + 一个 JS。
- **SQLite 存储**：只用标准库 `sqlite3`，数据全在 `data/` 里，直接拷走即可迁移。
- **手机适配**：移动优先布局、支持安全区、大点击区域、files input 直连相册/文件。

## 快速开始

### 在 Termux 上

```bash
pkg install git python
git clone <你的仓库地址> termux-webui
cd termux-webui
bash setup-termux.sh
. .venv/bin/activate
python run.py
```

浏览器打开 `http://127.0.0.1:8000`，同一 Wi-Fi 下其他设备用 `http://<手机IP>:8000`。

### 手动安装（任何平台）

```bash
pip install -r requirements.txt     # 或 requirements-minimal.txt
cp .env.example .env
python run.py
```

## 目录结构

```
termux-webui/
├── run.py                    # 启动入口
├── app/
│   ├── main.py               # ASGI 装配（uvicorn 目标 app.main:app）
│   ├── compat.py             # FastAPI / Starlette 兼容层
│   ├── config.py             # 配置（自带极简 .env 解析）
│   ├── db.py                 # SQLite 存储
│   ├── api.py                # 路由
│   ├── templates/index.html
│   └── static/{style.css,app.js}
├── data/                     # 运行时生成：app.db + uploads/
└── requirements*.txt
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回后端类型与运行时长 |
| GET | `/api/sysinfo` | 系统信息（CPU/磁盘/平台） |
| GET | `/api/notes` | 笔记列表 |
| POST | `/api/notes` | 新建笔记 `{title, body}` |
| PUT | `/api/notes/{id}` | 更新笔记 |
| DELETE | `/api/notes/{id}` | 删除笔记 |
| GET | `/api/uploads` | 文件列表 |
| POST | `/api/uploads` | 上传（multipart，字段名 `files`，支持多个） |
| GET | `/api/uploads/{name}/download` | 下载 |
| DELETE | `/api/uploads/{name}` | 删除 |

响应统一格式：成功 `{"ok": true, "data": ...}`，失败 `{"ok": false, "error": "..."}`。

## 配置（.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_NAME` | Termux WebUI | 标题 |
| `HOST` | 0.0.0.0 | 监听地址，`0.0.0.0` 才能局域网访问 |
| `PORT` | 8000 | 端口 |
| `RELOAD` | 0 | 1 = 改代码自动重载（开发用） |
| `DATA_DIR` | ./data | 数据目录 |
| `MAX_UPLOAD_MB` | 50 | 单文件上限 |
| `APP_TOKEN` | 空 | 填了就要求鉴权 |

### 关于访问密码

如果手机接的是公共 Wi-Fi，建议设一个 token：

```bash
echo "APP_TOKEN=$(head -c 16 /dev/urandom | base64)" >> .env
```

之后访问 `http://<IP>:8000/?token=xxx` 一次，前端会存在 localStorage 里，后续自动带上。

## 在手机上做开发

`HOST=127.0.0.1` + `RELOAD=1`，用手机浏览器访问即可，不用每次重启。

Termux 里改代码推荐装：

```bash
pkg install vim        # 或者
pkg install micro      # 更接近 VS Code 的操作方式
```

## 注意事项

- Termux 的 `pkg` 装的 Python 是 bionic 版本，**不要**混用 `pip install` 编译的轮子从其他架构拷过来，会 segfault。
- 手机后台管理很激进，Termux 容易被杀。要常驻可以：
  ```bash
  pkg install termux-services
  # 或者用 termux-wake-lock 防止休眠
  termux-wake-lock
  ```
- 想开机自启需要装 Termux:Boot（同作者 F-Droid 插件），把启动脚本放 `~/.termux/boot/`。
- 公网访问别直接开端口，用 `cloudflared tunnel` 或 `tailscale` 这类方案。

## 后续可以加什么

- 认证改成 JWT / 多用户
- 笔记加 markdown 渲染和搜索
- 加 WebSocket 做实时日志面板
- 用 `app/api.py` 里的 `ROUTES` 列表继续挂新模块，前端复制一个 tab 即可
