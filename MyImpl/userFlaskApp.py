"""
This is a simple Flask application for user management with basic CRUD operations. This application is designed to demonstrate 
potential vulnerabilities and how to test against them. The application uses SQLAlchemy for database interactions 
and Marshmallow for input validation.

To start -- 'flask --app userFlaskApp.py run'
Test using these commands 
- curl -X GET http://127.0.0.1:5000/users
- curl -X POST http://127.0.0.1:5000/user -H "Content-Type: application/json" -d '{"username":"testuser","password":"securepassword"}'
- curl -X DELETE http://localhost:5000/user/1

*** PROMPT 1 ***
You are an expert in web security and in penetration testing. With the following code in userFlaskApp, can you create 
some pytest test cases that test against vulnerabilities here?
"""
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields, validate, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
import threading

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=6))

user_schema = UserSchema()
users_schema = UserSchema(many=True)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return "Welcome to the Security Testing Demo!"

@app.route('/users', methods=['GET'])
def get_users():
    try:
        users = User.query.all()
        result =  users_schema.dump(users)
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": "An error occurred while fetching users", "error": str(e)}), 500


@app.route('/user/<int:id>', methods=['GET'])
def get_user(id):
    user = User.query.get(id)
    if user:
      result = user_schema.dump(user)
      return jsonify(result)
    return jsonify({"message": "User not found"}), 404

@app.route('/user', methods=['POST'])
def add_user():
    data = request.get_json()
    errors = user_schema.validate(data)
    if errors:
        return jsonify(errors), 400

    hashed_password = generate_password_hash(data['password'])
    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User added successfully"}), 201

@app.route('/user/<int:id>', methods=['PUT'])
def update_user(id):
    data = request.get_json()
    errors = user_schema.validate(data)
    if errors:
        return jsonify(errors), 400

    user = User.query.get(id)
    if user:
        user.username = data['username']
        user.password = generate_password_hash(data['password'])
        db.session.commit()
        return jsonify({"message": "User updated successfully"})
    return jsonify({"message": "User not found"}), 404

@app.route('/user/<int:id>', methods=['DELETE'])
def delete_user(id):
    user = User.query.get(id)
    if user:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"})
    return jsonify({"message": "User not found"}), 404

threading.Thread(target=app.run, kwargs={'host':'0.0.0.0','port':5000}).start()