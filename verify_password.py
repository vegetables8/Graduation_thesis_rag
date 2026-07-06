# -*- coding: utf-8 -*-
"""验证用户密码是否正确设置"""
import os
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash

db_path = os.path.join(os.path.dirname(__file__), "instance", "app.db")

# 预期密码
expected_passwords = {
    "student": "Stu@123",
    "topic_admin": "TopicAdmin@123",
    "academic_admin": "AcadAdmin@123",
    "audit_admin": "Audit@123",
}

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT username, password_hash FROM users")
users = cursor.fetchall()
conn.close()

print("Password verification:")
all_ok = True
for username, password_hash in users:
    expected = expected_passwords.get(username, "")
    if password_hash and check_password_hash(password_hash, expected):
        print(f"  {username}: OK (password '{expected}' matches)")
    else:
        print(f"  {username}: FAILED (password '{expected}' does NOT match)")
        print(f"    hash in DB: {password_hash[:50] if password_hash else 'NULL'}...")
        all_ok = False

if not all_ok:
    print("\nSome passwords are incorrect. Need to reset.")