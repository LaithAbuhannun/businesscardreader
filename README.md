````markdown
# 🪪 Business Card Reader

A full-stack pipeline that turns physical business cards into structured digital contacts.

- Detects one or more business cards in an image using a custom-trained YOLO model.
- Crops each detected card.
- Uses vision AI to read each cropped card and extract contact details (name / company / phone / email).
- Lets you review, edit, delete, and approve those results in the browser.
- Saves the final cleaned contacts into a local database for that user.

<p align="center">
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
````

So the pipeline is:
**Upload → Detect → Crop → AI Extract → Review/Edit → Save.**

---

## ✨ Main features

### 🔐 User login & sessions

* You can sign up and log in with email + password.
* The backend tracks who you are in the session.
* Each user only sees and edits their own contacts.

### 🟥 Automatic business card detection

* `/predict` receives an image from the frontend.
* A custom YOLO model (trained to detect "business card" as an object) runs on that image.
* The model returns bounding boxes around each card.
* The backend generates a preview image with boxes drawn, so the frontend can show you “this is what I found.”

### ✂️ Automatic cropping

* After detection, each bounding box is sliced out into its own file:

  * `crop_0.jpg`, `crop_1.jpg`, `crop_2.jpg`, …
* These crops are basically “just the card”, cleaned up so OCR/vision can focus only on the card.

### 🧾 Contact extraction with vision AI

* For each cropped card, the backend calls a vision LLM (for example, `gpt-4o-mini`) and asks it to return a clean JSON with:

  * `name`
  * `company_name`
  * `phone_number`
  * `email`
* The backend normalises that data and stores it temporarily in memory for that logged-in user.

This step is what turns pixels into usable contact info.

### 📝 Human review UI (edit before saving)

* The frontend fetches the extracted contacts from `/extract`.
* You get a table/list of all parsed cards.
* You can:

  * fix spelling,
  * correct numbers,
  * delete a card that you don’t want.
* The frontend calls:

  * `PUT /update_card` to update the stored info for one card.
  * `DELETE /remove_card` to drop a bad card.

### 💾 Save / export

* When you’re satisfied, you click save.
* The frontend calls `POST /save_final`.
* The backend writes all approved contacts into `final_database.json`, linked to your user.
* Now you have a simple persistent “mini CRM” file of contacts you scanned from physical cards.

Later this can become CSV export, vCard export, or automatic CRM import.

---

## 📂 Repository structure

```text
businesscardreader/
├─ README.md                # <-- this file

├─ assets/
│   ├─ demo.mov             # your recorded demo video
│   ├─ bbox-example.png     # (optional) screenshot showing detection box on card
│   └─ architecture.png     # (optional) a simple diagram of the flow

├─ client/                  # frontend (browser UI)
│   ├─ login.html           # login / signup screen
│   ├─ index.html           # main upload / capture / scan screen
│   ├─ upload.html          # optional upload flow variation
│   ├─ image.html           # shows detected bounding boxes / preview
│   ├─ tab.html             # review extracted info for each card (edit/delete before save)
│   ├─ results.html         # shows saved contacts after you confirm/save
│   ├─ edit.html            # focused edit of one contact's fields
│   ├─ style.css            # shared styling for all pages
│   └─ bcrlogo.png          # project logo / branding

├─ server/                  # backend + inference + persistence
│   ├─ server.py            # Flask app (port 5500)
│   │                       # Endpoints include:
│   │                       #   /signup_authorization, /login_authorization, /logout
│   │                       #   /predict  (YOLO detection)
│   │                       #   /confirm  (crop + AI extraction)
│   │                       #   /extract  (get parsed cards for this user)
│   │                       #   /update_card, /remove_card (edit/delete one card)
│   │                       #   /save_final (persist contacts)
│   ├─ final_database.json  # local "mini CRM": saved contacts mapped to each user
│   ├─ crop_0.jpg           # sample cropped card images from detection
│   ├─ crop_1.jpg
│   ├─ crop_2.jpg
│   ├─ lat.jpg              # example raw photo used for testing
│   ├─ runs/
│   │   └─ best.pt          # YOLO weights (custom trained business-card detector)
│   ├─ package.json         # if using Node or tooling around the backend
│   ├─ package-lock.json
│   └─ requirements.txt     # Flask, flask-cors, ultralytics, opencv-python, pillow,
│                           # numpy, albumentations, openai, etc.

└─ model/
    └─ yolo-final.ipynb     # Jupyter notebook that documents how the YOLO model was trained
```

### Notes on structure

* `client/` is the browser UI. It talks to the backend using `fetch()` calls.
* `server/` is the Flask backend + YOLO inference + OpenAI vision extraction.
* `model/` is your training notebook so people can see you actually trained a detector.
* `assets/` is only for README visuals (your `demo.mov`, screenshots, diagrams). The app does not load anything from `assets/` at runtime.

---

## 🔌 Backend details (server/)

### `server.py` responsibilities

**1. Auth / session**

* `POST /signup_authorization`
  Create account (email + password).
* `POST /login_authorization`
  Log in. Stores your email in a Flask session so the server knows “this is you”.
* `POST /logout`
  Clears your session.

**2. Detect cards**

* `POST /predict`

  * Accepts an uploaded image (e.g. from the browser).
  * Loads the trained YOLO model from `server/runs/best.pt`.
  * Runs inference to detect business cards.
  * Returns:

    * bounding box coordinates
    * a preview image with boxes drawn so the UI can show the result

**3. Crop and extract contact info**

* `POST /confirm`

  * Takes the detection results.
  * Crops each detected card into files like `crop_0.jpg`, `crop_1.jpg`, etc.
  * Sends each crop to a vision LLM (for example `gpt-4o-mini`).
  * Asks the model to respond in a strict structured format, for example:

    ```json
    {
      "name": "...",
      "company_name": "...",
      "phone_number": "...",
      "email": "..."
    }
    ```
  * Temporarily stores those extracted records for that logged-in user.

**4. Review / cleanup**

* `GET /extract`
  Returns all pending extracted cards for the current user.
  The frontend uses this to show a table of contacts in `tab.html`.

* `PUT /update_card`
  Update one of the extracted contacts (fix a name, correct a number, etc.).

* `DELETE /remove_card`
  Remove a bad card before saving.

**5. Save final results**

* `POST /save_final`
  Writes all approved contacts for that user into `final_database.json`.

* `GET /final_results` (if you expose it)
  Returns the saved contact list so you can view it later in `results.html`.

### YOLO inference

* The YOLO weights live in `server/runs/best.pt`.
* This model is custom trained to detect “business card” as an object.
* This is not generic COCO; it’s your own card detector.

### Vision LLM extraction

* After cropping, each card image is sent to an AI vision model.
* The prompt basically says: “Extract name / company / email / phone from this business card image and return valid JSON.”
* That result gets associated with the logged-in user session so you can edit it.

---

## 🖥 Frontend details (client/)

All the pages in `client/` are simple HTML/CSS/JS. They talk to `server.py` using `fetch()`.

Typical user flow:

1. `login.html`

   * User signs up or logs in.
   * After login, session is established on the backend.

2. `index.html` / `upload.html`

   * User uploads a photo containing one or more business cards.
   * Frontend calls `/predict` with that image.
   * Backend responds with bounding boxes and a preview.

3. `image.html`

   * Shows the preview with boxes drawn around each detected card.
   * User confirms.

4. `tab.html`

   * Calls `/extract` and displays all the parsed contact info.
   * User can edit fields (via `/update_card`) or delete a card (via `/remove_card`).

5. `results.html`

   * After user presses save, `/save_final` writes those contacts to `final_database.json`.
   * The saved list is shown here, acting like a mini contact book.

6. `edit.html`

   * Page for focused editing of a single contact’s details (useful if you want a clean form view instead of inline edit).

7. `style.css`

   * Shared styling so the UI looks consistent.

8. `bcrlogo.png`

   * Logo / branding for the app header.

---

## 🧪 Model training (model/)

The `model/` directory contains `yolo-final.ipynb`. That notebook documents:

* how the YOLO model was trained,
* what the dataset looks like (images of business cards from different angles / lighting),
* what augmentations you used (rotations, brightness/contrast changes, flips, etc.),
* evaluation / accuracy,
* and how you exported `best.pt`.

The exported weights were then copied into `server/runs/best.pt`, and that’s what the Flask backend uses for live detection.

This is important for credibility: it shows this is not just a hardcoded demo — you actually trained the detector.

---

## 🚀 Running locally

### 1. Backend setup

```bash
cd server
python -m venv venv

# macOS / Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate

pip install -r requirements.txt
python server.py
```

Now the Flask API should be running (default in this project: port 5500).

Make sure:

* `server/runs/best.pt` exists (your YOLO weights).
* Your OpenAI API key is correctly set in `server.py` where the vision extraction calls happen.

### 2. Frontend

Open the HTML files in `client/` in your browser, starting from `login.html` (or `index.html` if you’re skipping auth for testing).

Those pages will call the backend endpoints like `/predict`, `/confirm`, `/extract`, etc. on `http://localhost:5500/`.

---

## 🗺 Roadmap

* [x] Detect multiple cards in one uploaded image
* [x] Auto-crop each card
* [x] Extract structured contact info using a vision LLM
* [x] Per-user session so contacts are private
* [x] Edit / delete contacts before saving
* [x] Save final contact list to `final_database.json`
* [ ] Export to CSV / vCard
* [ ] Responsive mobile UI (scan directly from phone camera)
* [ ] Hosted / deployed version (no local setup required)

---

## ⚠️ Notes

* `final_database.json` right now is acting like a tiny local CRM file keyed by user.
  In production you would replace it with a proper database.
* `crop_*.jpg` files in `server/` are examples from a real run. They’re good to keep in the repo because they prove it actually works.
* `assets/demo.mov` is only for showing the demo in this README. The running app does not depend on it.
* Never commit real API keys or real customer data.

---

```
::contentReference[oaicite:0]{index=0}
```
