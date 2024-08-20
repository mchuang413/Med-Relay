from flask import Flask, jsonify, request, redirect, url_for
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import atexit
from alpaca_trade_api import REST, TimeFrame  # Import Alpaca API client

app = Flask(__name__)
CORS(app, supports_credentials=True)

uri = "mongodb+srv://michael:michaelchuang@cluster0.r9ljm0v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

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

problems = [
    "What is bullish meaning?",
    "What is bearish meaning?",
    "What is the main purpose of investing? a. To buy and sell assets quickly b. To build wealth and reach financial goals c. To keep money in a savings account d. To avoid financial markets",
    "Which of the following is an example of an asset you can invest in? a. Groceries b. Clothes c. Stocks d. Vacations",
    "Where was the first modern stock market established? a. New York b. London c. Amsterdam d. Tokyo",
    "Scenario: Juny wants to build wealth and reach her financial goals. Based on the text, which of the following should she consider investing in? a. Clothes b. Stocks c. Groceries d. Vacations",
    "Investing guarantees growth in value over time. True False",
    "In ancient times, people invested in tangible assets like land, livestock, and trade goods. True False"
]
answers = [
    "Bullish is a buying trend that indicates that the price is rising.",
    "Bearish is a selling trend that indicates that the price is falling.",
    "b",
    "c",
    "c",
    "b",
    "f",
    "t"
]

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
        "premium_user": False
    })

    response = jsonify({"status": "success", "message": "User registered successfully"})
    response.set_cookie("username", username)
    return response, 201

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

@app.route("/get_api_keys/<username>", methods=["GET"])
def get_api_keys(username):
    print(f"Username parameter: {username}")
    print(" hi")
    if not username:
        return jsonify({"status": "error", "message": "Username parameter not found"}), 400

    user = collection.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    alpaca_key = user.get("alpaca_key")
    alpaca_secret = user.get("alpaca_secret")

    if not alpaca_key or not alpaca_secret:
        return jsonify({"status": "error", "message": "API keys not found"}), 404
    print(alpaca_key + " " + alpaca_secret)
    return jsonify({"status": "success", "alpaca_key": alpaca_key, "alpaca_secret": alpaca_secret})

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

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get('code')
    client_id = "dcd9816d13f11fb6b7d63366b844216a"
    client_secret = "cc3f314b13ef1a016dbaf7815ec6255544166f4e"
    redirect_uri = "https://www.junyapp.com/"
    
    if not code:
        return jsonify({"status": "error", "message": "Authorization code not found"}), 400

    token_url = 'https://api.alpaca.markets/oauth/token'
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
    }
    headers = {
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(token_url, json=payload, headers=headers)
        data = response.json()
        
        if 'access_token' in data:
            access_token = data['access_token']
            # Store the access token in the database or session
            return redirect(url_for('dashboard'))  # Redirect to your dashboard or another page
        else:
            return jsonify({"status": "error", "message": "Failed to obtain access token"}), 400
    except requests.exceptions.RequestException as e:
        print(f"Token fetch error: {str(e)}")
        return jsonify({"status": "error", "message": "An error occurred while fetching the token"}), 500

@app.route("/dashboard")
def dashboard():
    return "Dashboard"

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
