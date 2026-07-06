# -*- coding: utf-8 -*-
"""直接测试登录逻辑"""
import sys
sys.path.insert(0, r"E:\课程设计内容\大三下_计算三\计算三_mj")

from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    # 测试每个账号的密码验证
    test_cases = [
        ("student", "Stu@123"),
        ("topic_admin", "TopicAdmin@123"),
        ("academic_admin", "AcadAdmin@123"),
        ("audit_admin", "Audit@123"),
    ]

    print("Testing login logic directly:")
    for username, password in test_cases:
        user = User.query.filter_by(username=username).first()
        if user:
            result = user.check_password(password)
            print(f"  {username}/{password}: {'SUCCESS' if result else 'FAILED'}")
            if not result:
                # 测试错误密码
                print(f"    Testing wrong password 'wrong': {user.check_password('wrong')}")
        else:
            print(f"  {username}: USER NOT FOUND")

    # 检查数据库连接是否正常
    print(f"\nDatabase URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Users count: {User.query.count()}")