#!/data/data/com.termux/files/usr/bin/bash
# Termux 一键安装：bash setup-termux.sh
set -e

echo "==> 更新包索引"
pkg update -y

echo "==> 安装 Python"
pkg install -y python

echo "==> 创建虚拟环境"
python -m venv .venv
. .venv/bin/activate

echo "==> 安装依赖（优先完整版，失败回退轻量版）"
pip install --upgrade pip
if pip install -r requirements.txt; then
  echo "   -> FastAPI 安装成功（含 /docs）"
else
  echo "   -> FastAPI 安装失败，回退轻量版 Starlette"
  pip install -r requirements-minimal.txt
fi

# .env 不存在就生成一份默认的（不依赖 .env.example 是否被上传）
if [ ! -f .env ]; then
  cat > .env <<'EOF'
APP_NAME=Termux WebUI
HOST=0.0.0.0
PORT=8000
RELOAD=0
DATA_DIR=./data
MAX_UPLOAD_MB=50
APP_TOKEN=
EOF
  echo "==> 已生成 .env"
fi

echo
echo "==> 完成。启动："
echo "    . .venv/bin/activate && python run.py"
