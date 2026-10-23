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

echo "==> 安装依赖（优先轻量版，避免 pydantic-core 需要 Rust 编译）"
pip install --upgrade pip
if pip install -r requirements.txt; then
  echo "   -> FastAPI 安装成功（含 /docs）"
else
  echo "   -> FastAPI 安装失败，回退轻量版 Starlette"
  pip install -r requirements-minimal.txt
fi

[ -f .env ] || cp .env.example .env

echo
echo "==> 完成。启动："
echo "    . .venv/bin/activate && python run.py"
