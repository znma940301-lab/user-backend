import os
import re
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# ========== 配置 ==========
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret')
# CloudBase 云托管用 SQLite（文件存储在 /tmp，重启会清空，适合学习）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/users.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)


# ========== 数据库模型 ==========
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_active': self.is_active
        }


# ========== 初始化数据库 ==========
with app.app_context():
    db.create_all()


# ========== 校验函数 ==========
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    if len(password) < 6:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True


# ========== API 接口 ==========

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'user-backend'})


@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()

    if not data:
        return jsonify({'code': 400, 'msg': '请求体不能为空'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # 校验必填
    if not all([username, email, password]):
        return jsonify({'code': 400, 'msg': '用户名、邮箱、密码均为必填项'}), 400

    if len(username) < 3 or len(username) > 20:
        return jsonify({'code': 400, 'msg': '用户名长度需在 3-20 位之间'}), 400

    if not validate_email(email):
        return jsonify({'code': 400, 'msg': '邮箱格式不正确'}), 400

    if not validate_password(password):
        return jsonify({'code': 400, 'msg': '密码至少6位，且需同时包含字母和数字'}), 400

    # 查重
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 409, 'msg': '用户名已被注册'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'code': 409, 'msg': '邮箱已被注册'}), 409

    # 创建用户
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'code': 201,
        'msg': '注册成功',
        'data': user.to_dict()
    }), 201


@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()

    if not data:
        return jsonify({'code': 400, 'msg': '请求体不能为空'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not all([username, password]):
        return jsonify({'code': 400, 'msg': '用户名和密码均为必填项'}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({'code': 401, 'msg': '用户名或密码错误'}), 401

    if not user.is_active:
        return jsonify({'code': 403, 'msg': '账号已被禁用'}), 403

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'code': 200,
        'msg': '登录成功',
        'data': {
            'token': access_token,
            'user': user.to_dict()
        }
    })


@app.route('/api/profile', methods=['GET'])
@jwt_required()
def profile():
    """获取个人信息（需要登录）"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    return jsonify({
        'code': 200,
        'msg': 'success',
        'data': user.to_dict()
    })


@app.route('/api/users/count', methods=['GET'])
def user_count():
    """统计用户总数"""
    count = User.query.count()
    return jsonify({'code': 200, 'data': {'total_users': count}})


# ========== 错误处理 ==========
@app.errorhandler(404)
def not_found(e):
    return jsonify({'code': 404, 'msg': '接口不存在'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'code': 500, 'msg': '服务器内部错误'}), 500


# ========== 启动 ==========
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)