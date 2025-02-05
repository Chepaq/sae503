import os
import csv
from flask import Flask, request, jsonify
from redis import Redis
from functools import wraps

# Configuration des variables d'environnement
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
APP_PORT = int(os.getenv("QUOTES_SERVICE_PORT", 5002))
ADMIN_KEY = os.getenv("ADMIN_KEY", "default_key")
CSV_FILE_QUOTES = os.getenv("CSV_FILE_QUOTES", "initial_data_quotes.csv")

# Initialisation de Flask
app = Flask(__name__)
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_key = request.headers.get("Authorization")
        if not auth_key or auth_key != ADMIN_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# Chargement initial des données
if not redis_client.exists("quotes:1"):
    if os.path.exists(CSV_FILE_QUOTES):
        with open(CSV_FILE_QUOTES, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                quote = row['quote']
                quote_id = redis_client.incr("quote_id")
                redis_client.hset(f"quotes:{quote_id}", mapping={"quote": quote})
                redis_client.sadd("quotes", f"quotes:{quote_id}")

# Endpoints
@app.route('/quotes', methods=['GET'])
@require_auth
def get_quotes():
    quotes = redis_client.smembers("quotes")
    quote_list = [redis_client.hgetall(quote) for quote in quotes]
    return jsonify(quote_list), 200

@app.route('/quotes', methods=['POST'])
@require_auth
def add_quote():
    data = request.get_json()
    user_id = data.get("user_id")
    quote = data.get("quote")

    if not user_id or not quote:
        return jsonify({"error": "user_id et quote sont requis"}), 400

    quote_id = redis_client.incr("quote_id")
    redis_client.hset(f"quotes:{quote_id}", mapping={"user_id": user_id, "quote": quote})
    redis_client.sadd("quotes", f"quotes:{quote_id}")
    return jsonify({"message": "Citation ajoutée", "id": quote_id}), 201

@app.route('/quotes/<int:quote_id>', methods=['DELETE'])
@require_auth
def delete_quote(quote_id):
    if not redis_client.exists(f"quotes:{quote_id}"):
        return jsonify({"error": "Citation non trouvée"}), 404

    redis_client.delete(f"quotes:{quote_id}")
    redis_client.srem("quotes", f"quotes:{quote_id}")
    return jsonify({"message": "Citation supprimée"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT)
