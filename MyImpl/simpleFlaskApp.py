import json
from flask import Flask, jsonify

"""
Tests and Prompts in test_simpleFlaskApp.py
"""
# === Replace this with an import of your real app if available ===
def create_test_app():
    app = Flask(__name__)

    @app.route('/api/greet/<name>', methods=['GET'])
    def greet(name):
        return jsonify(message=f"Hello, {name}!")

    return app
# ================================================================