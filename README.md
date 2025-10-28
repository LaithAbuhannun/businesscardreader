# 🪪 Business Card Reader

A full-stack pipeline that turns physical business cards into structured digital contacts.

- Detects one or more business cards in an image using a custom-trained YOLO model.
- Crops each detected card.
- Uses vision AI to read each cropped card and extract contact details (name / company / phone / email).
- Lets you review, edit, delete, and approve those results in the browser.
- Saves the final cleaned contacts into a local database for that user.

<p align="center">
  <!-- You already created assets/demo.mov. GitHub will either show a player or a link -->
  <video src="assets/demo.mov" width="600" controls muted playsinline></video>
</p>

---

## 📌 Problem this solves

Manually typing business card info into your phone or into a CRM is annoying and easy to forget.

This project makes that automatic:
1. Take a photo / upload a photo that contains one or more business cards.
2. The system finds and crops each card on its own.
3. It reads text on those cards and pulls out structured info.
4. You quickly confirm/fix it.
5. It saves those contacts for you.

The core idea: **scan → approve → done.**  
No more typing names, phone numbers, and emails from paper.

---

## 🧠 How it works (end-to-end flow)

```text
[ client/ (browser) ]
    |
    | 1. User logs in / signs up
    | 2. User uploads an image with one or more business cards
    v
[ server/ (Flask API) ]
    |
    | /predict
    |   - Loads YOLO weights from runs/best.pt
    |   - Detects business cards in the uploaded image
    |   - Returns bounding boxes + a preview
    |
    | /confirm
    |   - Crops each detected card (crop_0.jpg, crop_1.jpg, ...)
    |   - Sends each crop to a vision LLM
    |   - Extracts: { name, company_name, phone_number, email }
    |
    | /extract
    |   - Returns the extracted cards + fields for the current logged-in user
    |
    | /update_card
    | /remove_card
    |   - User can edit or delete any card's info before saving
    |
    | /save_final
    |   - Saves approved contacts to final_database.json
    |
    v
[ final_database.json ]
    - Becomes your personal contact list (per user session)
So the pipeline is:
Upload → Detect → Crop → AI Extract → Review/Edit → Save.

✨ Main features
🔐 User login & sessions
You can sign up and log in with email + password.

The backend tracks who you are in the session.

Each user only sees and edits their own contacts.

🟥 Automatic business card detection
/predict receives an image from the frontend.

A custom YOLO model (trained to detect "business card") runs on that image.

The model returns bounding boxes around each card.

The backend generates a preview image with boxes drawn, so the frontend can show you “this is what I found.”

✂️ Automatic cropping
After detection, each bounding box is sliced out into its own file:

crop_0.jpg, crop_1.jpg, crop_2.jpg, …

These crops are basically “just the card,” cleaned up so OCR/vision can focus only on the card.

🧾 Contact extraction with vision AI
For each cropped card, the backend calls a vision LLM (for example, gpt-4o-mini) and asks it to return structured JSON with:

name

company_name

phone_number

email

The backend normalises that data and stores it temporarily in memory for that logged-in user.

This step is what turns pixels into usable contact info.

📝 Human review UI (edit before saving)
The frontend calls /extract to display all parsed contacts.

You can:

fix spelling,

correct numbers,

delete a card you don’t want.

The frontend calls:

PUT /update_card to update the stored info for one card.

DELETE /remove_card to drop a bad card.

💾 Save / export
When you’re satisfied, you click save.

The frontend calls POST /save_final.

The backend writes all approved contacts into final_database.json, linked to your user.

Now you have a simple persistent “mini CRM” file of contacts you scanned from physical cards.

Later this can become CSV export, vCard export, or automatic CRM import.

📂 Repository structure
text
Copy code
businesscardreader/
├─ README.md                # <-- this file

├─ assets/
│   ├─ demo.mov             # your recorded demo video
│   ├─ bbox-example.png     # (optional) screenshot showing detection box on card
│   └─ architecture.png     # (optional) block diagram of the flow

├─ client/                  # frontend (browser UI)
│   ├─ login.html           # login / signup screen
│   ├─ index.html           # main upload / capture / scan screen
│   ├─ upload.html          # optional upload flow variation
│   ├─ image.html           # shows detected bounding boxes / preview
│   ├─ tab.html             # review extracted info for each card (edit/delete before save)
│   ├─ results.html         # shows saved contacts after you confirm/save
│   ├─ edit.html            # focused edit of one contact's details
│   ├─ style.css            # shared styling for all pages
│   └─ bcrlogo.png          # project branding / logo

├─ server/                  # backend + inference + persistence
│   ├─ server.py            # Flask app (port 5500)
│   │                       # Endpoints include:
│   │                       #   /signup_authorization, /login_authorization, /logout
│   │                       #   /predict       (YOLO detection)
│   │                       #   /confirm       (crop + AI extraction)
│   │                       #   /extract       (get parsed cards for this user)
│   │                       #   /update_card   (edit one card)
│   │                       #   /remove_card   (delete one card)
│   │                       #   /save_final    (persist contacts)
│   ├─ final_database.json  # local "mini CRM": saved contacts mapped to each user
│   ├─ crop_0.jpg           # sample cropped card images from detection
│   ├─ crop_1.jpg
│   ├─ crop_2.jpg
│   ├─ lat.jpg              # example raw photo used for testing
│   ├─ runs/
│   │   └─ best.pt          # YOLO weights (custom trained business-card detector)
│   ├─ package.json         # if you're using any Node/tooling in backend workflow
│   ├─ package-lock.json
│   └─ requirements.txt     # Flask, flask-cors, ultralytics, opencv-python, pillow,
│                           # numpy, albumentations, openai, etc.

└─ model/
    └─ yolo-final.ipynb     # Jupyter notebook showing how the YOLO model was trained
Notes on structure
client/ is the browser-facing UI. It talks to the backend using fetch().

server/ is Flask + YOLO inference + OpenAI vision extraction + session logic + saving.

model/ is your training notebook so people can see your detector isn’t just copy/paste.

assets/ is only for the README visuals (your demo video, screenshots, diagrams). The runtime code does not use assets/.

🔌 Backend: how it behaves
server.py does:
1. Auth / session

POST /signup_authorization
Create account (email + password).

POST /login_authorization
Log in. Stores your email in the Flask session so the server knows which user is active.

POST /logout
Clears session.

2. Detect cards

POST /predict

Accepts an uploaded image from the frontend.

Loads YOLO weights from server/runs/best.pt.

Detects each business card in the image.

Returns:

bounding box coordinates

a preview image with boxes drawn (so the UI can show “I found these cards”).

**3. Crop







You said:
where is the full explanation markdown I wnat it ll in one black block



ChatGPT said:
markdown
Copy code
# 🪪 Business Card Reader

A full-stack pipeline that turns physical business cards into structured digital contacts.

- Detects one or more business cards in an image using a custom-trained YOLO model.
- Crops each detected card.
- Uses vision AI to read each cropped card and extract contact details (name / company / phone / email).
- Lets you review, edit, delete, and approve those results in the browser.
- Saves the final cleaned contacts into a local database for that user.

<p align="center">
  <!-- You already created assets/demo.mov. GitHub will either show a player or a download link for this file. -->
  <video src="assets/demo.mov" width="600" controls muted playsinline></video>
</p>

---

## 📌 Problem this solves

Manually typing business card info into your phone or into a CRM is annoying and easy to forget.

This project makes that automatic:
1. Take a photo / upload a photo that contains one or more business cards.
2. The system finds and crops each card on its own.
3. It reads text on those cards and pulls out structured info.
4. You quickly confirm/fix it.
5. It saves those contacts for you.

The core idea: **scan → approve → done.**  
No more typing names, phone numbers, and emails from paper.

---

## 🧠 How it works (end-to-end flow)

```text
[ client/ (browser) ]
    |
    | 1. User logs in / signs up
    | 2. User uploads an image with one or more business cards
    v
[ server/ (Flask API) ]
    |
    | /predict
    |   - Loads YOLO weights from runs/best.pt
    |   - Detects business cards in the uploaded image
    |   - Returns bounding boxes + a preview
    |
    | /confirm
    |   - Crops each detected card (crop_0.jpg, crop_1.jpg, ...)
    |   - Sends each crop to a vision LLM
    |   - Extracts: { name, company_name, phone_number, email }
    |
    | /extract
    |   - Returns the extracted cards + fields for the current logged-in user
    |
    | /update_card
    | /remove_card
    |   - User can edit or delete any card's info before saving
    |
    | /save_final
    |   - Saves approved contacts to final_database.json
    |
    v
[ final_database.json ]
    - Becomes your personal contact list (per user session)
So the pipeline is:
Upload → Detect → Crop → AI Extract → Review/Edit → Save.

✨ Main features
🔐 User login & sessions
You can sign up and log in with email + password.

The backend tracks who you are in the session.

Each user only sees and edits their own contacts.

🟥 Automatic business card detection
Endpoint: POST /predict

The frontend sends an uploaded image (which can contain multiple cards).

A custom YOLO model (trained specifically to detect “business card”) runs on that image.

The model returns bounding boxes around each card.

The backend also generates a preview image with those boxes drawn, so the UI can show







