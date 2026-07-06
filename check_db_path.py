# -*- coding: utf-8 -*-
"""检查数据库路径配置"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

print(f"BASE_DIR: {BASE_DIR}")
print(f"INSTANCE_DIR: {INSTANCE_DIR}")
print(f"INSTANCE_DIR exists: {INSTANCE_DIR.exists()}")

db_path = INSTANCE_DIR / "app.db"
db_uri = f"sqlite:///{db_path.as_posix()}"
print(f"DB path: {db_path}")
print(f"DB path exists: {db_path.exists()}")
print(f"DB URI: {db_uri}")

# Windows 下 SQLite URI 格式需要特别注意
# 正确格式应该是 sqlite:///E:/path/to/db.db (三个斜杠)
# 或者使用 as_posix() 后的结果

print(f"\nCorrect Windows SQLite URI formats:")
print(f"  sqlite:///{db_path}")  # 四个斜杠，Windows 绝对路径
print(f"  sqlite:///{db_path.as_posix()}")  # 使用 as_posix()