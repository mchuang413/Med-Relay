from flask import Flask, Response, render_template, jsonify, request, make_response, session, redirect, url_for, stream_with_context, send_file
import pyaudio
import wave
import os
from dotenv import load_dotenv
import openai
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask_cors import CORS
import wave
from datetime import datetime
from threading import Lock
from io import BytesIO
import gridfs
import zipfile

app = Flask(__name__)

app.secret_key = "eut3grbifu32r83gibfejiijohughuijokkijhugvhjiokjbhvghbjkmjhgvfccgvhbygtfdrxcgfhvy3r9eonvj"
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

CORS(app, resources={r"/*": {"origins": "*"}})

app.config['SESSION_TYPE'] = 'filesystem'

recording_states = {}
recording_states_lock = Lock()

uri1 = "mongodb+srv://michael:lxsquid@cluster0.ruhmegq.mongodb."
uri2 = "net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient((uri1 + uri2), server_api=ServerApi('1'))
db = client.get_database('MedRelay')
fs = gridfs.GridFS(db)

openai.api_key = os.getenv("OPENAI_API_KEY")

audio1 = pyaudio.PyAudio()

for i in range(audio1.get_device_count()):
    device_info = audio1.get_device_info_by_index(i)
    print(f"Device {i}: {device_info['name']}")
    print(f"  Max Input Channels: {device_info['maxInputChannels']}")
    print(f"  Default Sample Rate: {device_info['defaultSampleRate']}\n")

desired_device_index = 1

device_info = audio1.get_device_info_by_index(desired_device_index)
max_channels = device_info['maxInputChannels']

CHANNELS = min(max_channels, 2)

FORMAT = pyaudio.paInt16
RATE = int(device_info['defaultSampleRate'])
CHUNK = 1024
TOTAL_CHUNKS = 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files or 'code' not in request.form:
        return jsonify({'message': 'No file part or code provided'}), 400
    
    file = request.files['file']
    code = request.form['code']
    
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    # Determine the file extension
    file_extension = file.filename.split('.')[-1].lower()
    mime_type = f'image/{file_extension}'

    # Find the number of images associated with this code to determine the next number
    count = db.fs.files.count_documents({'filename': {'$regex': f'^{code}_'}})
    file_number = count + 1

    # Set the filename to be code_number.extension
    filename = f"{code}_{file_number}.{file_extension}"
    
    # Store the file in GridFS
    file_id = fs.put(file, filename=filename, content_type=mime_type)
    return jsonify({'file_id': str(file_id), 'filename': filename, 'message': 'Image uploaded successfully'}), 201

@app.route('/get_image/<file_id>', methods=['GET'])
def get_image(file_id):
    try:
        file = fs.get(file_id)
        mime_type = file.content_type if file.content_type else 'application/octet-stream'
        return send_file(BytesIO(file.read()), attachment_filename=file.filename, mimetype=mime_type)
    except gridfs.NoFile:
        return jsonify({'message': 'File not found'}), 404
    
@app.route('/download_images/<code>', methods=['GET'])
def download_images_by_code(code):
    try:
        # Find all files with filenames starting with the given code
        files = list(db.fs.files.find({'filename': {'$regex': f'^{code}_'}}))
        if not files:
            return jsonify({'message': 'No images found for this code'}), 404

        # Create a zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file in files:
                # Retrieve the file data from GridFS
                file_data = fs.get(file['_id']).read()
                # Add file to the zip file
                zip_file.writestr(file['filename'], file_data)

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"{code}_images.zip",
            mimetype='application/zip'
        )
    except gridfs.NoFile:
        return jsonify({'message': 'File not found in GridFS'}), 404
    except Exception as e:
        app.logger.error(f'An error occurred: {str(e)}')
        return jsonify({'message': f'An error occurred: {str(e)}'}), 500

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    existing_user = db.users.find_one({'$or': [{'email': data['email']}, {'username': data['username']}]})
    if existing_user:
        return jsonify({'message': 'Email or username already exists'}), 400
    db.users.insert_one({
        'email': data['email'],
        'username': data['username'],
        'password': data['password']
    })
    return jsonify({'message': 'User registered successfully!'}), 201

@app.route("/login", methods=["POST"])
def login():
    session["recording"] = False
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required"}), 400

    user = db.users.find_one({"username": username})
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    if user["password"] == password:
        response = jsonify({"status": "success", "token": "dummy-token"})
        session["username"] = username
        return response
    else:
        return jsonify({"status": "error", "message": "Incorrect password"}), 401
    