from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import atexit
from alpaca_trade_api import REST, TimeFrame  # Import Alpaca API client
import stripe

app = Flask(__name__)
CORS(app, supports_credentials=True)

uri = "mongodb+srv://michael:michaelchuang@cluster0.r9ljm0v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

stripe.api_key = "sk_test_51PlbBbJZFpZ3kJxXocbnkyGcmjhIE8IoBwc49QGolVnZSqLjQT7lEapXwoU0jY7UsQYJZM3xK1xIsFqgtrBUpBOd002ajzjaxU"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Use the appropriate database and collection
db = client["Juny"]
collection = db["users"]  # Assuming a collection named "users" for user data
news_collection = db["news"]  # Collection for storing news

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    try:
        data = request.json
        username = data.get("username")

        if not username:
            return jsonify({"status": "error", "message": "Username is required"}), 400

        # Optionally, you can check if the user is already a premium user
        user = collection.find_one({"username": username})
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        if user.get("premium_user"):
            return jsonify({"status": "error", "message": "User is already a premium user"}), 400

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Juny+ Subscription",
                        },
                        "unit_amount": 1000,  # $10.00
                    },
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url="https://www.junyapp.com/shop",  # Redirect URL on success
            cancel_url="https://www.junyapp.com/shop",  # Redirect URL on cancel
        )

        return jsonify({"id": session.id})
    except Exception as e:
        return jsonify(error=str(e)), 500

def ask_gpt(pretext, prompt):
    response = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": pretext + prompt,
            }
        ],
        model="gpt-3.5-turbo",
    )
    return response.choices[0].message.content

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "nouser"})
    if user["password"] == password:
        response = jsonify({"status": "works"})
        response.set_cookie("username", username)
        return response
    else:
        return jsonify({"status": "wrong"})

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username") 
    password = data.get("password")
    alpaca_key = data.get("alpaca_key")
    alpaca_secret = data.get("alpaca_secret")

    if not username or not password or not alpaca_key or not alpaca_secret:
        return jsonify({"status": "error", "message": "Username, password, Alpaca API key, and Alpaca API secret are required"}), 400

    if collection.find_one({"username": username}):
        return jsonify({"status": "error", "message": "Username already exists"}), 400

    collection.insert_one({
        "username": username,
        "password": password,
        "alpaca_key": alpaca_key,
        "alpaca_secret": alpaca_secret,
        "premium_user": False,
        "level": 0
    })

    response = jsonify({"status": "success", "message": "User registered successfully"})
    response.set_cookie("username", username)
    return response, 201

@app.route("/portfolio_leaderboard", methods=["GET"])
def portfolio_leaderboard():
    users = collection.find()
    leaderboard = []

    for user in users:
        alpaca_key = user.get("alpaca_key")
        alpaca_secret = user.get("alpaca_secret")
        username = user.get("username")

        if not alpaca_key or not alpaca_secret:
            continue  # Skip users without valid API keys

        alpaca = REST(
            alpaca_key,
            alpaca_secret,
            base_url='https://paper-api.alpaca.markets'
        )

        try:
            # Get the account details
            account = alpaca.get_account()
            equity = float(account.equity)
            last_equity = float(account.last_equity)
            
            # Calculate the daily percentage change
            if last_equity != 0:
                daily_change_pct = ((equity - last_equity) / last_equity) * 100
            else:
                daily_change_pct = 0

            leaderboard.append({
                "username": username,
                "daily_change_pct": daily_change_pct
            })

        except Exception as e:
            print(f"Error fetching data for user {username}: {str(e)}")
            continue  # Skip users with errors

    # Sort the leaderboard by daily percentage change in descending order
    leaderboard.sort(key=lambda x: x["daily_change_pct"], reverse=True)

    return jsonify({"status": "success", "leaderboard": leaderboard})

@app.route('/weaknesses/<input>')
def weaknesses(input):
    response = ask_gpt("Here are the questions asked by us, then the answers the user suggested. You're an expert teacher. Provide insightful feedback on the weaknesses of the student's learning style.", input)
    return response

@app.route('/checkanswer/<question>/<answer>/<id>')
def checkanswer(question, answer, id):
    qindex = problems.index(question)
    if answers[qindex] == answer:
        mydict = {"id": id, "question": question, "correct": "T"}
        collection.insert_one(mydict)
        return("Correct!")
    else:
        mydict = {"id": id, "question": question, "correct": "F"}
        collection.insert_one(mydict)
        return("Incorrect")
    
@app.route("/get_premium_status", methods=["GET"])
def get_premium_status():
    username = request.args.get("username")

    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    premium_user = user.get("premium_user", False)
    return jsonify({"status": "success", "premium_user": premium_user})

@app.route("/get_user_level", methods=["GET"])
def get_user_level():
    username = request.args.get("username")

    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    level = user.get("level", 1)
    return jsonify({"status": "success", "level": level})

@app.route("/increment_level", methods=["POST"])
def increment_level():
    username = request.args.get("username")

    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    new_level = user.get("level", 1) + 1
    collection.update_one({"username": username}, {"$set": {"level": new_level}})
    
    return jsonify({"status": "success", "new_level": new_level})

@app.route("/upgrade_premium", methods=["POST"])
def upgrade_premium():
    data = request.json
    username = data.get("username")

    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    collection.update_one({"username": username}, {"$set": {"premium_user": True}})
    
    return jsonify({"status": "success", "new_premium_status": True})

@app.route("/live_wallstreetbets", methods=["GET"])
def live_wallstreetbets():
    quiver_api_key = "a7f488dbb045a1805275bc5b109cdcdaa3c3fab8"
    headers = {"Authorization": f"Bearer {quiver_api_key}"}
    url = "https://api.quiverquant.com/beta/live/wallstreetbets"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return jsonify({"status": "success", "data": data})
    except requests.exceptions.RequestException as e:
        print(e)
        return jsonify({"status": "error", "message": "Failed to fetch data from Quiver API"}), 500

def fetch_news():
    alpha_vantage_api_key = "SGNSNG70ZU9IAWW9"
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={alpha_vantage_api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        if 'feed' in data:
            news_list = data['feed']
            for news_item in news_list:
                news_collection.insert_one(news_item)
        else:
            print("No news found in the response")
    except requests.exceptions.RequestException as e:
        print(e)

@app.route("/news", methods=["GET"])
def get_news():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        skip = (page - 1) * limit

        news_data = list(news_collection.find().sort("time_published", -1).skip(skip).limit(limit))
        for news in news_data:
            news["_id"] = str(news["_id"])
        return jsonify({"status": "success", "data": news_data})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": "Failed to fetch news from database"}), 500

@app.route("/trade", methods=["POST"])
def trade():
    data = request.json
    username = data.get("username")
    action = data.get("action")
    symbol = data.get("symbol")
    quantity = data.get("quantity")
    time_in_force = data.get("timeInForce")

    if not all([username, action, symbol, quantity, time_in_force]):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    alpaca_key = user.get("alpaca_key")
    alpaca_secret = user.get("alpaca_secret")
    if not alpaca_key or not alpaca_secret:
        return jsonify({"status": "error", "message": "API keys not found"}), 404

    alpaca = REST(
        alpaca_key,
        alpaca_secret,
        base_url='https://paper-api.alpaca.markets'
    )

    try:
        order = alpaca.submit_order(
            symbol=symbol,
            qty=int(quantity),
            side=action,
            type='market',
            time_in_force='day',
        )
        return jsonify({"status": "success", "data": order._raw})
    except Exception as e:
        print(f"Error creating order: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route("/get_api_keys/<username>", methods=["GET"])
def get_api_keys(username):
    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    api_keys = {
        "alpaca_key": user.get("alpaca_key"),
        "alpaca_secret": user.get("alpaca_secret")
    }

    return jsonify({"status": "success", "alpaca_key": api_keys["alpaca_key"], "alpaca_secret": api_keys["alpaca_secret"]})

# Add a simple route to verify HTTPS setup
@app.route("/hello")
def hello():
    return "Hello, world!"

# Schedule the news fetching function to run 10 times a day
scheduler = BackgroundScheduler()
scheduler.add_job(func=fetch_news, trigger="interval", hours=2.4)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    context = ('/etc/letsencrypt/live/michaelape.site/fullchain.pem', '/etc/letsencrypt/live/michaelape.site/privkey.pem')  # Update paths to your SSL certificate and key
    app.run(host='0.0.0.0', port=443, ssl_context=context)
