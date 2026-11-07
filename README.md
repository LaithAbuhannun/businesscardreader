# 🪪 Business Card Reader

A full-stack pipeline that turns physical business cards into structured digital contacts.

* Detects one or more business cards in an image using a custom-trained YOLO model.
* Crops each detected card.
* Uses vision AI to read each cropped card and extract contact details (name / company / phone / email).
* Lets you review, edit, delete, and approve those results in the browser.
* Saves the final cleaned contacts into a local database for that user.

---

## 🔴 Live Demo

### 1. Scan & detect business cards

https://github.com/user-attachments/assets/e0fdaea9-2890-4a9c-8a1a-bc6291a3ce8f

### 2. Review + edit extracted contact info

https://github.com/user-attachments/assets/4dfaaf35-2d6c-4ba5-9d7f-4880a0c20896
### 3. Saved contacts view

https://github.com/user-attachments/assets/5726adfd-5aa7-4b21-b039-2d4d73a8e052

---

## 📌 Problem this solves

Typing business card info into your phone or into a CRM is slow and annoying.

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
    |   - Crops each detected card (in memory)
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
    |   - Saves approved contacts to data/contacts.json
    |
    v
[ server/data/contacts.json ]
    - Becomes your personal contact list (per user session)
```

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

* After detection, each bounding box is clamped to the image and sliced out in memory (no files on disk).
* These crops are basically “just the card,” cleaned up so OCR/vision can focus only on the card.

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
  * delete a card you don’t want.
* The frontend calls:

  * `PUT /update_card` to update the stored info for one card.
  * `DELETE /remove_card` to drop a bad card.

### 💾 Save / export

* When you’re satisfied, you click save.
* The frontend calls `POST /save_final`.
* The backend writes all approved contacts into `server/data/contacts.json`, linked to your user.
* Now you have a simple persistent “mini CRM” file of contacts you scanned from physical cards.

Later this can become CSV export, vCard export, or automatic CRM import.

---

## 📂 Repository structure

```text
businesscardreader/
├─ README.md                # <-- this file

├─ client/                  # frontend (browser UI)
│   ├─ login.html           # login / signup screen
│   ├─ index.html           # main upload / capture / scan screen
│   ├─ upload.html          # optional upload flow variation
│   ├─ image.html           # shows detected bounding boxes / preview
│   ├─ tab.html             # review extracted info for each card (edit/delete before save)
│   ├─ results.html         # shows saved contacts after you confirm/save
│   ├─ edit.html            # focused edit of one contact's fields
│   ├─ style.css            # shared styling for all pages
│   └─ bcrlogo.png          # project branding / logo

├─ server/                  # backend + inference + persistence
│   ├─ server.py            # Flask app (port 5500)
│   │                       # Endpoints include:
│   │                       #   /signup_authorization, /login_authorization, /logout
│   │                       #   /predict  (YOLO detection)
│   │                       #   /confirm  (crop + AI extraction)
│   │                       #   /extract  (get parsed cards for this user)
│   │                       #   /update_card, /remove_card (edit/delete one card)
│   │                       #   /save_final, /final_results (persist and list contacts)
│   ├─ runs/
│   │   └─ best.pt          # YOLO weights (custom trained business-card detector)
│   ├─ tests/
│   │   └─ test_app.py      # pytest suite (model and LLM are faked, no API key needed)
│   ├─ data/                # created at runtime: accounts.json + contacts.json (git-ignored)
│   ├─ requirements.txt     # runtime dependencies
│   └─ requirements-dev.txt # test dependencies (no PyTorch needed)

└─ model/
    └─ yolo-final.ipynb     # Jupyter notebook that documents how the YOLO model was trained
```

### Notes on structure

* `client/` is the browser UI. It talks to the backend using `fetch()`.
* `server/` is Flask + YOLO inference + OpenAI vision extraction + session logic + saving.
* `model/` is your YOLO training notebook so people can see you actually trained the model.


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

  * Accepts an uploaded image (from the browser).
  * Loads the trained YOLO model from `server/runs/best.pt`.
  * Runs inference to detect business cards.
  * Returns:

    * bounding box coordinates
    * a preview image with boxes drawn so the UI can show the result.

**3. Crop and extract contact info**

* `POST /confirm`

  * Takes the detection results.
  * Crops each detected card in memory (no temp files, so users never overwrite each other's scans).
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
  Writes all approved contacts for that user into `server/data/contacts.json` (atomic write, duplicates skipped).

* `GET /final_results`
  Returns the saved contact list so you can view it later in `results.html`.

### YOLO inference

* The YOLO weights live in `server/runs/best.pt`.
* This model is custom trained to detect “business card” as an object.
* This is not a generic COCO model — it’s specialized for cards.

### Vision LLM extraction

* After cropping, each card image is sent to an AI vision model.
* The prompt says basically:
  “Extract name / company / phone / email from this business card image and return valid JSON.”
* That result is stored for the logged-in session so the UI can show/edit it.

---

## 🖥 Frontend details (client/)

All the pages in `client/` are static HTML/CSS/JS. They call the Flask backend.

Typical user flow:

1. `login.html`

   * User signs up or logs in.
   * After login, session is established on the backend.

2. `index.html` / `upload.html`

   * User uploads a photo with one or more cards.
   * Frontend calls `/predict`.
   * Backend responds with bounding boxes and a preview image.

3. `image.html`

   * Shows that preview with drawn boxes so user can confirm detection.

4. `tab.html`

   * Calls `/extract` and displays all the parsed contact info.
   * User can edit fields (`/update_card`) or delete bad cards (`/remove_card`).

5. `results.html`

   * After the user presses save, `/save_final` writes those contacts to `server/data/contacts.json`.
   * The saved list is shown here, acting like a mini contact book.

6. `edit.html`

   * Focused edit screen for one contact's details.

7. `style.css`

   * Shared styling.

8. `bcrlogo.png`

   * Branding / logo.

---

## 🧪 Model training (model/)

The `model/` directory contains `yolo-final.ipynb`. That notebook shows:

* how the YOLO model was trained,
* what data/augmentations were used (angles, lighting, rotations, brightness/contrast),
* evaluation/accuracy,
* exporting the final weights.

Those final weights were copied into `server/runs/best.pt`, which is what `server.py` loads for live detection.

This proves the detector is truly trained, not just downloaded.

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

# Secrets come from the environment, never from the code (see ../.env.example)
export BCR_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export OPENAI_API_KEY=sk-your-key

python server.py
```

Make sure `server/runs/best.pt` exists (your YOLO weights).
Detection keeps boxes scoring at least `0.25` (override with `BCR_CONFIDENCE`), and merges overlapping boxes at IoU `0.5`, the value used in training.

### 2. Frontend

The Flask server also serves the UI. Open **http://127.0.0.1:5500** and sign up, then log in.
(The camera works on `localhost`/`127.0.0.1`; anywhere else it needs HTTPS.)

### 3. Tests

```bash
cd server
pip install -r requirements-dev.txt
python -m pytest -q
```

The tests replace YOLO and the vision model with fakes, so they run in seconds without
PyTorch or an API key. GitHub Actions runs them on every push.

---

## 🔒 Security

* **Passwords** are hashed with Werkzeug's salted scrypt and never logged. Accounts persist in `server/data/accounts.json`.
* **Login** gives the same answer for an unknown email and a wrong password, runs a hash check either way so timing doesn't leak which emails exist, and locks an email out for 5 minutes after 5 failed attempts.
* **Sessions** are signed with `BCR_SECRET_KEY` from the environment, cleared on login (no session fixation), and use `HttpOnly` + `SameSite=Lax` cookies (`Secure` with `BCR_COOKIE_SECURE=1`).
* **Every data endpoint requires login**, and each user can only read or change their own cards.
* **Uploads** are capped at 10 MB, must be real JPEG/PNG/WebP images, and are checked against decompression bombs. Crop boxes are clamped to the image.
* **AI output is treated as untrusted.** The prompt tells the model card text is data, not instructions; the response is reduced to the four expected string fields with a length cap; and the UI inserts it with `textContent`, never `innerHTML`, so a card can't inject script.
* **Privacy:** card images are sent with `store=False`, user data lives in a git-ignored folder, and errors return generic messages while details go to the server log.
* **Headers:** Content-Security-Policy, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`.
* The server binds to `127.0.0.1` by default. Working state is kept in memory, so run a single process.

---

## 🗺 Roadmap

* [x] Detect multiple cards in one uploaded image
* [x] Auto-crop each card
* [x] Extract structured contact info using a vision LLM
* [x] Per-user session so contacts are private
* [x] Edit / delete contacts before saving
* [x] Save final contact list per user
* [x] Hashed passwords, input validation, security headers and a test suite
* [ ] Export to CSV / vCard
* [ ] Responsive mobile UI (scan directly from phone camera)
* [ ] Hosted / deployed version (no local setup required)
