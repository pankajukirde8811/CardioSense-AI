# ❤️ CardioSense AI

**An AI-based cardiovascular risk prediction web app.**
Enter your health details or upload a blood test report, and get a clear heart-risk percentage, the main risk factors, and an optional PDF report, in seconds.

> **Final-year project** · Python · Flask · scikit-learn · Tesseract OCR

> ⚠️ **Guidance, not diagnosis.** CardioSense AI gives a risk *estimate* for learning and screening purposes. It is not a medical device and does not replace a doctor.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔐 **Secure login & register** | Passwords are stored hashed (never in plain text). Each user only sees their own data. |
| ✍️ **Manual entry** | Age, gender, height, weight, blood pressure, cholesterol, glucose, smoking, alcohol and physical activity. |
| 📄 **Blood report upload (OCR)** | Upload a PDF or a photo of a lab report. The app reads cholesterol, glucose, blood pressure, age, gender, height and weight automatically. |
| ✅ **Human-in-the-loop** | Extracted values are always shown back to the user, who must confirm them before any prediction is made. |
| 🧠 **AI risk prediction** | A Random Forest model trained on 68,000+ patient records returns a risk percentage and a level (Low / Moderate / Moderate–High / High). |
| 🚩 **Key risk factors** | Highlights warning signs such as elevated BP, high cholesterol, high glucose, obesity, smoking and low activity. |
| 🧾 **PDF report** | One-click downloadable report with a report ID, local date & time, the result and all input values. |
| 🕓 **History** | Every check is saved privately so users can track their risk over time. |
| 📱 **Mobile-friendly** | Responsive design that works on phones, tablets and desktops. |

---

## 🔄 How it works

```
Register / Login
       │
       ▼
Choose an input method ──► Manual entry ──────────────┐
       │                                              │
       └──► Upload blood report ─► OCR ─► Confirm ────┤
                                                      ▼
                                       Random Forest model
                                                      │
                                                      ▼
                                 Risk % + key factors + PDF report
```

Both input methods feed the **same prediction engine**.

---

## 🧠 Machine learning

### Dataset
- **Cardiovascular Disease dataset**, 70,000 patient records ([Kaggle](https://www.kaggle.com/datasets/sulianova/cardiovascular-disease-dataset))
- Features: age, gender, height, weight, systolic & diastolic BP, cholesterol, glucose, smoking, alcohol, physical activity
- Target: presence of cardiovascular disease (0 / 1), almost perfectly balanced (50 / 50)

### Data cleaning
The raw data contains impossible values (e.g. blood pressure of −150 or 16020). Records outside realistic ranges were removed:

| Field | Kept range |
|---|---|
| Systolic BP | 80 – 250 mm Hg |
| Diastolic BP | 40 – 150 mm Hg (and lower than systolic) |
| Height | 120 – 220 cm |
| Weight | 30 – 200 kg |
| BMI | 12 – 60 |

**Result:** 68,581 records kept, 1,419 removed (2.0%), still balanced.

### Model
- **Random Forest classifier** (300 trees, max depth 10, min 20 samples per leaf)
- 80 / 20 stratified train-test split

| Metric | Score |
|---|---|
| **Accuracy** | **73.3%** |
| Precision (disease) | 0.76 |
| Recall (disease) | 0.67 |
| F1-score (macro avg) | 0.73 |

72–74% is the typical range reported for this dataset.

### Most important factors

| Rank | Factor | Importance |
|---|---|---|
| 1 | Systolic blood pressure | 50.4% |
| 2 | Diastolic blood pressure | 18.2% |
| 3 | Age | 13.8% |
| 4 | Cholesterol | 9.5% |
| 5 | BMI | 5.4% |

### Unit conversion
The dataset stores cholesterol and glucose as levels (1 = normal, 2 = above normal, 3 = well above). The app converts real lab values automatically:

| | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| Cholesterol (mg/dl) | < 200 | 200 – 239 | ≥ 240 |
| Glucose (mg/dl) | < 100 | 100 – 125 | ≥ 126 |

Reports in **mmol/l** (common in Europe) are converted too: cholesterol × 38.67, glucose × 18.

---

## 🛠️ Tech stack

| Part | Technology |
|---|---|
| Backend & auth | Python, Flask, SQLite, Werkzeug password hashing |
| Machine learning | scikit-learn (Random Forest), pandas, NumPy, joblib |
| Report reading | pdfplumber (digital PDFs), Tesseract OCR + pytesseract (photos & scans) |
| PDF reports | ReportLab |
| Frontend | HTML, CSS, JavaScript (Jinja templates) |
| Development | Jupyter notebooks, Git & GitHub |

---

## 📁 Project structure

```
CardioSense-AI/
├── app.py                  # Flask app: routes, login, database
├── requirements.txt        # Pinned Python packages
├── models/
│   └── cardio_rf.joblib    # Trained Random Forest model
├── notebooks/
│   ├── 01_explore_data.ipynb   # Data exploration & cleaning
│   └── 02_train_model.ipynb    # Model training & evaluation
├── utils/
│   ├── predict.py          # Loads the model, converts units, predicts risk
│   ├── ocr.py              # Reads PDFs/photos and extracts lab values
│   ├── report.py           # Builds the PDF report
│   └── timefmt.py          # Shows times in the user's timezone
├── templates/              # HTML pages (login, check, confirm, result, history)
├── static/css/style.css    # Design (red & white theme)
├── samples/                # Fictional blood reports for testing uploads
└── data/                   # Dataset goes here (not included, see below)
```

---

## 🚀 Getting started

### Requirements
- **Python 3.14** (the model was trained with this version, so use the same one)
- **Tesseract OCR** (for reading photos of reports)
- Git

### 🐧 Linux (Ubuntu)

```bash
# 1. Install system tools
sudo apt update
sudo apt install -y python3-venv python3-pip git tesseract-ocr

# 2. Get the code
git clone https://github.com/pankajukirde8811/CardioSense-AI.git
cd CardioSense-AI

# 3. Create the virtual environment and install packages
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Create the secret key file
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env

# 5. Run the app
python app.py
```

### 🪟 Windows

1. Install **Python 3.14** from [python.org](https://www.python.org/downloads/) and tick **"Add Python to PATH"**.
2. Install **Git** from [git-scm.com](https://git-scm.com/).
3. Install **Tesseract OCR** using the Windows installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki), keeping the default folder `C:\Program Files\Tesseract-OCR`. The app finds it there automatically.
4. Open **Command Prompt** and run:

```bat
git clone https://github.com/pankajukirde8811/CardioSense-AI.git
cd CardioSense-AI

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env

python app.py
```

### Open the app
- On the same computer: **http://127.0.0.1:5000**
- On a phone on the same network: **http://&lt;your-computer-IP&gt;:5000**
  (Some university or student Wi-Fi networks block this. Use a phone hotspot instead.)

---

## 🧪 Trying the report upload

Two **fictional** test reports are included in `samples/`:

- `sample_blood_report.pdf`: a digital PDF (text is read directly)
- `sample_blood_report.png`: an image (read with OCR)

Upload either one on the **Check risk** page. The app should find *cholesterol 245, glucose 105, BP 150/95, age 54, male, 172 cm, 86 kg*.

To recreate them:
```bash
python samples/make_samples.py
```

---

## 🔁 Retraining the model (optional)

The trained model is already included, so this is only needed to reproduce the results.

1. Download `cardio_train.csv` from [Kaggle](https://www.kaggle.com/datasets/sulianova/cardiovascular-disease-dataset) and place it in `data/`.
2. Run `notebooks/01_explore_data.ipynb`, which creates `data/cardio_clean.csv`.
3. Run `notebooks/02_train_model.ipynb`, which saves `models/cardio_rf.joblib`.

The dataset is not included in this repository. Please download it from Kaggle.

---

## 🔒 Security & privacy

- **Hashed passwords**: credentials are never stored in plain text.
- **Private by default**: each user can only see their own checks and reports.
- **Uploads are deleted immediately**: a blood report is read once and then removed from the server.
- **Secrets stay local**: `.env` and the database are excluded from Git.
- **Human-in-the-loop**: values read from a report must be confirmed before predicting.

---

## ⚠️ Limitations

- **Accuracy is about 73%.** The model misses about 1 in 3 disease cases, which is why results are framed as guidance only.
- **Age range:** the training data covers adults aged **30–65**. Results outside this range are less reliable, and the app shows a note.
- **Self-reported lifestyle data:** in this dataset smoking and alcohol were self-reported and have very little effect on the model. The app still flags them as risk factors based on medical guidelines.
- **OCR quality** depends on the photo. Blurry or angled photos may be misread, which is why every value must be confirmed.

---

## 🔮 Future scope

- Install as a phone app (Progressive Web App)
- Online deployment with HTTPS
- Wearable device integration (heart rate, activity)
- Doctor-facing dashboard for patient monitoring
- Multi-language support (e.g. German, Hindi)
- Per-patient explanations with SHAP

---

## 👤 Author

**Pankaj Dattatray Ukirde**
GitHub: [@pankajukirde8811](https://github.com/pankajukirde8811)

---

<sub>Dataset: Cardiovascular Disease dataset by Svetlana Ulianova, Kaggle. Sample reports in `samples/` are fictional and made only for testing.</sub>
