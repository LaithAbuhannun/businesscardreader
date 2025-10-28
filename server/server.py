from flask import Flask, send_from_directory, request, jsonify, session
from urllib.parse import urlparse
import os
from ultralytics import YOLO
import base64
import cv2
import numpy as np
from io import BytesIO
import PIL.Image
from flask_cors import CORS
from PIL import Image
import albumentations as A
import requests
from openai import OpenAI
import json
import re

app = Flask(__name__, static_folder='../Client', static_url_path='')
app.secret_key = 'bcr'
CORS(app, supports_credentials=True)

model = YOLO("runs/best.pt")
model.conf = 0.5
model.iou = 0.3

results_data = {}
extracted_data_store = {}
final_database = {}
accounts = {}

client = OpenAI(api_key="api key")

def get_session_email():
    return session.get("current_email")

def parse_response(text):
    try:
        json_str = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_str:
            return json.loads(json_str.group(1))
        return json.loads(text)
    except Exception:
        fields = ['Name', 'Company Name', 'Phone Number', 'Email']
        return {
            f.lower().replace(" ", "_"): re.search(rf"{f}: (.+)", text).group(1).strip() if re.search(rf"{f}: (.+)", text) else None
            for f in fields
        }

def save_base64_image(base64_string, filename):
    img_data = base64.b64decode(base64_string.split(',')[1])
    image = Image.open(BytesIO(img_data)).convert('RGB')
    image.save(filename)
    return image

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/<path:path>')
def serve_static(path):
    protected_pages = ['index.html', 'upload.html', 'image.html', 'tab.html']  
    email = get_session_email()

    if path in protected_pages and not email:
        print("Blocked access to", path, "— no session found.")
        return send_from_directory(app.static_folder, 'login.html')
    
    return send_from_directory(app.static_folder, path)



@app.route('/login_authorization', methods=['POST'])
def login_authorization():
    global accounts, final_database
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if email in accounts and accounts[email] == password:
        session['current_email'] = email
        print("current user:", email)
        print(f"credentials info: {email}: {accounts[email]}")
        if email not in final_database:
            final_database[email] = []
        extracted_data_store[email] = []
        results_data[email] = {'image': None, 'boxes': []}
        return jsonify({"success": True})
    elif email in accounts:
        return jsonify({"success": False, "error": "Incorrect password"}), 401
    else:
        return jsonify({"success": False, "error": "Account does not exist"}), 404

@app.route('/signup_authorization', methods=['POST'])
def signup_authorization():
    global accounts
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if email not in accounts:
        accounts[email] = password
        print(accounts)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Email already exists"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    email = get_session_email()
    if email:
        session.pop('current_email', None)
        results_data.pop(email, None)
        extracted_data_store.pop(email, None)
    return jsonify({"success": True})

@app.route('/predict', methods=['POST'])
def predict():
    email = get_session_email()
    if not email:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        img_data = data['image']
        image = save_base64_image(img_data, 'lat.jpg')
        image = image.resize((1024, 1024))
        img_array_rgb = np.array(image)
        img_array = cv2.cvtColor(img_array_rgb, cv2.COLOR_RGB2BGR)

        prediction = model(img_array)
        annotated = prediction[0].plot()
        results_data[email] = {
            'image': img_array,
            'boxes': prediction[0].boxes.xywh.cpu().tolist()
        }

        print("Detected boxes:", results_data[email]['boxes'])

        output_image = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
        buffer = BytesIO()
        output_image.save(buffer, format="JPEG")
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return jsonify({'image_with_bboxes': 'data:image/jpeg;base64,' + encoded})
    except Exception as e:
        print("Prediction error:", e)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/confirm', methods=['POST'])
def confirm():
    email = get_session_email()
    if not email:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        image = results_data[email]['image']
        boxes = results_data[email]['boxes']
        print("Boxes for confirmation:", boxes)
        crops = []
        extracted_data_store[email] = []

        for idx, box in enumerate(boxes):
            x, y, w, h = box
            x1, y1, x2, y2 = int(x - w / 2), int(y - h / 2), int(x + w / 2), int(y + h / 2)
            cropped = image[y1:y2, x1:x2]
            crop_filename = f"crop_{idx}.jpg"
            cv2.imwrite(crop_filename, cropped)
            with open(crop_filename, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')

            crops.append({ 'id': idx, 'image': 'data:image/jpeg;base64,' + encoded })

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                store=True,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract the name, company name, phone number, and email from this business card. Return the response as a JSON dictionary with keys: name, company_name, phone_number, email."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
                        ]
                    }
                ]
            )

            text_response = completion.choices[0].message.content
            print("card response", text_response)
            parsed = parse_response(text_response)
            print("Parsed data:", parsed)

            extracted_data_store[email].append({
                'id': idx,
                'image': 'data:image/jpeg;base64,' + encoded,
                'details': parsed
            })
        return jsonify({'crops': crops})
    except Exception as e:
        print("Confirm error:", e)
        return jsonify({'error': 'Crop error'}), 500

@app.route('/extract', methods=['GET'])
def extract():
    email = get_session_email()
    return jsonify(extracted_data_store.get(email, []))

@app.route('/update_card', methods=['PUT'])
def update_card():
    email = get_session_email()
    data = request.get_json()
    card_id = data.get("id")
    new_details = data.get("details")
    for item in extracted_data_store.get(email, []):
        if item['id'] == card_id:
            item['details'] = new_details
    for item in extracted_data_store.get(email, []):
        print("Updated card details:", item['details'])
    return jsonify({"success": True})

@app.route('/remove_card', methods=['DELETE'])
def remove_card():
    email = get_session_email()
    data = request.get_json()
    card_id = data.get("id")
    extracted_data_store[email] = [item for item in extracted_data_store.get(email, []) if item['id'] != card_id]
    for item in extracted_data_store.get(email, []):
        print("Remaining card:", item['details'])
    return jsonify({"success": True})

@app.route('/save_final', methods=['POST'])
def save_final():
    email = get_session_email()
    if not email:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        if email not in final_database:
            final_database[email] = []

        for detail in extracted_data_store.get(email, []):
            if not any(entry['details'] == detail['details'] for entry in final_database[email]):
                final_database[email].append(detail)
        
        for i, data in enumerate(final_database[email]):
            final_database[email][i]["id"] = i

        with open("final_database.json", "w") as f:
            json.dump(final_database, f, indent=2)

        for info in final_database[email]:
            print("Final saved detail:", info['details'])

        print("finished successfully")
        return jsonify({"success": True})
    except Exception as e:
        print("Save Final Error:", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/final_results', methods=['GET'])
def final_results():
    email = get_session_email()
    try:
        with open('final_database.json', 'r') as f:
            data = json.load(f)
        return jsonify(data.get(email, []))
    except Exception as e:
        print("Error reading final results:", e)
        return jsonify([]), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5500))
    app.run(host='0.0.0.0', port=port)
