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
    | /export/contacts.csv, /export/contacts.vcf
    |   - Downloads your saved contacts as a spreadsheet or for your phone / address book
    |
    v
[ server/data/contacts.json ]
    - Becomes your personal contact list (per user session)
```

So the pipeline is:
**Upload → Detect → Crop → AI Extract → Review/Edit → Save → Export.**

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
* On the **My Cards** page, **Download CSV** gives a spreadsheet (opens in Excel, Numbers or Google Sheets) and **Download vCard** gives a `.vcf` file you can import into Apple Contacts, Google Contacts or Outlook.

### ⚠️ Clear error messages

* Every page shows problems in a message box at the top instead of failing silently: server not running, camera blocked or missing, no cards found in the photo, AI extraction failed, session expired (you're sent back to login), upload too large, too many login attempts.

---

## 📂 Repository structure

```text
businesscardreader/
├─ README.md                # <-- this file

├─ client/                  # frontend (browser UI)
│   ├─ login.html           # login / signup screen
│   ├─ upload.html          # scan screen: live camera or "Take or choose photo"
│   ├─ edit.html            # review / edit / remove extracted cards before saving
│   ├─ results.html         # saved contacts, with CSV / vCard download
│   ├─ index.html           # forwards to upload.html (old entry point)
│   ├─ js/
│   │   ├─ common.js        # shared API helper, on-page messages, log-out button
│   │   └─ login.js, upload.js, edit.js, results.js, index.js   # one script per page
│   ├─ app.css              # all styling, mobile first
│   └─ bcrlogo.png, bcrlogo-small.png   # logo (small one is used in the UI)

├─ server/                  # backend + inference + persistence
│   ├─ server.py            # Flask app (port 5500); `--phone` serves HTTPS on your Wi-Fi
│   │                       # Endpoints include:
│   │                       #   /signup_authorization, /login_authorization, /logout
│   │                       #   /predict  (YOLO detection)
│   │                       #   /confirm  (crop + AI extraction)
│   │                       #   /extract  (get parsed cards for this user)
│   │                       #   /update_card, /remove_card (edit/delete one card)
│   │                       #   /save_final, /final_results (persist and list contacts)
│   │                       #   /export/contacts.csv, /export/contacts.vcf (download)
│   ├─ runs/
│   │   └─ best.pt          # YOLO weights (custom trained business-card detector)
│   ├─ tests/
│   │   ├─ test_app.py      # feature tests (model and LLM are faked, no API key needed)
│   │   ├─ test_security.py # attack tests: auth, sessions, brute force, uploads, XSS, CSRF…
│   │   ├─ test_phone.py    # phone mode (HTTPS certificate) and small-screen layout
│   │   ├─ conftest.py      # shared fixtures
│   │   └─ helpers.py       # fake detector / extractor and request helpers
│   ├─ data/                # created at runtime: accounts.json + contacts.json (git-ignored)
│   ├─ certs/               # created by --phone: self-signed HTTPS certificate (git-ignored)
│   ├─ requirements.txt     # runtime dependencies
│   └─ requirements-dev.txt # test + security-scan dependencies (no PyTorch needed)

├─ .env.example             # copy to .env and fill in (the real .env is git-ignored)

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
  The frontend uses this to show the cards for review in `edit.html`.

* `PUT /update_card`
  Update one of the extracted contacts (fix a name, correct a number, etc.).

* `DELETE /remove_card`
  Remove a bad card before saving.

**5. Save final results**

* `POST /save_final`
  Writes all approved contacts for that user into `server/data/contacts.json` (atomic write, duplicates skipped).

* `GET /final_results`
  Returns the saved contact list so you can view it later in `results.html`.

**6. Export**

* `GET /export/contacts.csv`
  Your saved contacts as CSV (Name, Company, Phone, Email). UTF-8 with a BOM so Excel shows accents correctly.
* `GET /export/contacts.vcf`
  Your saved contacts as vCard 3.0, one card per contact.

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

2. `upload.html`

   * User captures a photo with the live camera, or taps **Take or choose photo** to use the phone's camera app or photo library.
   * Photos are shrunk to at most 2048 px in the browser first, so uploads are quick on mobile data.
   * Frontend calls `/predict`.
   * Backend responds with bounding boxes and a preview image.

3. The same page shows the preview with boxes drawn, and a **Confirm** button.

4. `edit.html`

   * Calls `/extract` and displays all the parsed contact info.
   * User can edit fields (`/update_card`) or delete bad cards (`/remove_card`), then **Save all**.

5. `results.html`

   * After the user presses save, `/save_final` writes those contacts to `server/data/contacts.json`.
   * The saved list is shown here, acting like a mini contact book.
   * **Download CSV** / **Download vCard** export the list.

6. `app.css`

   * One mobile-first stylesheet for every page: single column on phones, large buttons, no fixed widths.

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

# Secrets live in a .env file in the repo root, never in the code.
cp ../.env.example ../.env
python -c "import secrets; print(secrets.token_hex(32))"   # paste as BCR_SECRET_KEY in .env
# then put your OpenAI key after OPENAI_API_KEY= in .env

python server.py
```

`server.py` loads `.env` automatically (with `python-dotenv`). Variables already set in your
shell take priority over the file. `.env` is in `.gitignore`, and CI fails if one is ever committed.

Make sure `server/runs/best.pt` exists (your YOLO weights).
Detection keeps boxes scoring at least `0.25` (override with `BCR_CONFIDENCE`), and merges overlapping boxes at IoU `0.5`, the value used in training.

### 2. Frontend

The Flask server also serves the UI. Open **http://127.0.0.1:5500** and sign up, then log in.
(The camera works on `localhost`/`127.0.0.1`; anywhere else it needs HTTPS.)

### 📱 Using it on your phone

Phones can't use `127.0.0.1` (that's the phone itself), and browsers only allow the live
camera over HTTPS. Phone mode handles both:

```bash
cd server
source venv/bin/activate
python server.py --phone
```

It prints an address like `https://192.168.1.101:5500`. With the phone on the **same Wi-Fi**:

1. Open that address on the phone.
2. The browser warns that the connection isn't private. That's because the certificate was
   made on your computer, not by a public authority. Tap **Show Details → visit this website**
   (Safari) or **Advanced → Proceed** (Chrome). You only do this once; the certificate is saved
   in `server/certs/` and reused until your computer's IP address changes.
3. Sign up / log in, allow camera access, and scan.

If the live camera still won't start, tap **Take or choose photo**: it opens the phone's
own camera app and works even without HTTPS.

While phone mode runs, anyone on the same Wi-Fi can reach the login page, so use it on a
network you trust and stop it (Ctrl+C) when you're done. If the phone can't connect at all,
check that both are on the same network and that the computer's firewall allows incoming
connections for Python.

### 3. Tests and security scans

```bash
cd server
pip install -r requirements-dev.txt
python -m pytest -q                         # feature + security tests

cd ..
bandit -r server -x server/tests,server/venv,server/certs   # static security scan of the code
pip-audit -r server/requirements.txt -r server/requirements-dev.txt   # known-vulnerable dependencies
```

The tests replace YOLO and the vision model with fakes, so they run in seconds without
PyTorch or an API key. `tests/test_security.py` tries the attacks directly: missing, forged,
tampered, expired and replayed session cookies on every endpoint; brute-force lockout and
password spraying; path traversal; oversized, malformed and decompression-bomb uploads;
XSS payloads in card fields and CSV/vCard injection; cross-site request forgery; and one user
reading or changing another user's cards.

GitHub Actions runs the tests, bandit and pip-audit on every push and pull request.

---

## 🔒 Security

* **Passwords** are hashed with Werkzeug's salted scrypt and never logged. Accounts persist in `server/data/accounts.json`.
* **Login** gives the same answer for an unknown email and a wrong password, runs a hash check either way so timing doesn't leak which emails exist, and locks an email out for 5 minutes after 5 failed attempts.
* **Brute force:** besides the per-email lockout, each client address is limited to 30 login/sign-up attempts a minute, which stops one password being tried across many emails. (Behind a reverse proxy every request has the proxy's address, so put the limit in the proxy instead.)
* **Sessions** are signed with `BCR_SECRET_KEY` from the environment, cleared on login (no session fixation), expire after 12 hours (`BCR_SESSION_HOURS`), and use `HttpOnly` + `SameSite=Lax` cookies (`Secure` with `BCR_COOKIE_SECURE=1`). Logging out invalidates the cookie on the server, so a copied cookie stops working too. (This logs that account out on every device.)
* **Cross-site request forgery:** every request that changes something must be JSON, which an HTML form on another site can't send.
* **Every data endpoint requires login**, and each user can only read or change their own cards.
* **Uploads** are capped at 10 MB and 25 megapixels (checked before decoding), and must actually be JPEG, PNG or WebP: other formats Pillow can read are refused even if labelled as one of those. Crop boxes are clamped to the image.
* **AI cost:** at most 10 cards are read per scan, and each scan can be confirmed only once, so repeated requests can't run up OpenAI charges.
* **AI output is treated as untrusted.** The prompt tells the model card text is data, not instructions; the response is reduced to the four expected string fields with a length cap; and the UI inserts it with `textContent`, never `innerHTML`, so a card can't inject script. The CSP allows no inline scripts or styles. CSV export prefixes formula-like cells with `'` so spreadsheets don't run them, and vCard export escapes values so a card can't add extra fields.
* **Privacy:** card images are sent with `store=False`, user data lives in a git-ignored folder, and errors return generic messages while details go to the server log.
* **Headers:** Content-Security-Policy, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`.
* The server binds to `127.0.0.1` by default. Only `--phone` listens on the network, and only over HTTPS with `Secure` cookies; its private key is saved readable only by you. Working state is kept in memory, so run a single process.

---

## 🗺 Roadmap

* [x] Detect multiple cards in one uploaded image
* [x] Auto-crop each card
* [x] Extract structured contact info using a vision LLM
* [x] Per-user session so contacts are private
* [x] Edit / delete contacts before saving
* [x] Save final contact list per user
* [x] Hashed passwords, input validation, security headers and a test suite
* [x] Export to CSV / vCard
* [x] Security test suite, bandit and pip-audit in CI
* [x] Responsive mobile UI (scan directly from phone camera)
* [ ] Hosted / deployed version (no local setup required)
