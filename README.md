# 🐾 WildNest — AI Wildlife Rescue & Rehoming Platform

**WildNest tracks rescued animals from rescue to adoption** — with AI health scans, a grounded care chatbot, weather-smart meal plans, and AI adopter matching, so no animal's story gets lost in paperwork.

Built for **AnimalHack 2026** (CUTC Transform).

---

## 🌟 Features

| Feature | What it does |
|---|---|
| 🩺 **WildSight AI Chat** | A grounded care assistant that answers species-specific questions using the animal's own medical records, weight logs, and environmental history. Supports **photo health analysis** — upload a picture of a wound or skin condition and get an instant, vision-model assessment. |
| 🍽️ **Smart Meal Planner** | Generates daily, species-appropriate meal plans using the live **Open-Meteo weather API**, adjusting portions and hydration for real-time temperature and humidity. |
| 🤝 **AI Adopter Matching** | Scores and ranks potential adopters against each animal's specific needs (habitat, experience, medical requirements) so rescuers make data-driven rehoming decisions. |
| 🎫 **Digital Passport & QR Handover** | Every animal gets a portable identity card with a scannable QR code. When an animal transfers between rescuers, its full history travels with it — no paperwork lost. |
| 📢 **Rehoming Feed** | A public adoption listing where approved animals are showcased to potential adopters. |
| 📊 **Dashboard Analytics** | Interactive Plotly charts tracking weight, environment, feeding, stress, and activity trends over time. |
| 🔔 **Notifications** | Automated, warm "updates from the pet" plus vaccination reminders and transition milestones. |

---

## 🧠 How the AI works (RAG-grounded)

WildSight doesn't just call an LLM — it grounds every answer in **that specific animal's real data**:

1. The animal's profile, medical history, and logged analytics are injected into the system prompt.
2. A local **RAG layer** (ChromaDB + `sentence-transformers`) retrieves and cites relevant species-care references.
3. The pet's own logged data always takes priority over general reference material.

**Models** (served via [Groq](https://groq.com)'s free OpenAI-compatible API):
- Text (chat, meal plans, matching, notifications): `openai/gpt-oss-120b`
- Vision (photo health analysis): `qwen/qwen3.6-27b`

---

## 🛠️ Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-Login
- **Database:** SQLite (dev) / PostgreSQL (production)
- **AI:** Groq API (OpenAI-compatible client) + RAG pipeline (ChromaDB, sentence-transformers `all-MiniLM-L6-v2`)
- **Weather:** Open-Meteo API
- **Frontend:** Jinja2 templates, Plotly.js charts
- **QR / Media:** `qrcode`, Pillow
- **Deployment:** Render (Gunicorn)

---

## 🚀 Getting Started

### 1. Clone & set up a virtual environment
```bash
git clone https://github.com/adnanahamedtamim/WildNest.git
cd WildNest
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Create a `.env` file in the project root:
```
SECRET_KEY=your-secret-key
GROQ_API_KEY=your-free-groq-key-from-console.groq.com
```
> Get a free Groq API key at [console.groq.com/keys](https://console.groq.com/keys) — no credit card required.

### 4. (Optional) Seed demo data
```bash
python seed_demo.py
```

### 5. Run
```bash
python app.py
```
Open **http://localhost:5000** in your browser.

> ⚡ The first AI reply after startup takes ~30s while the RAG embedding model warms up, then it's fast.

---

## 📁 Project Structure

```
WildNest/
├── app.py                # Flask app factory, config, lightweight migrations
├── models.py             # SQLAlchemy models (Animal, User, MedicalRecord, …)
├── wildsight_ai.py       # AI module — chat, meal plans, matching, vision
├── rag.py                # RAG pipeline (ChromaDB + sentence-transformers)
├── weather.py            # Open-Meteo weather lookup
├── charts.py             # Plotly analytics charts
├── media.py              # Photo/video upload handling
├── seed_demo.py          # Demo data seeder
├── routes/               # Blueprints: auth, main, animals, wildsight, feed
├── templates/            # Jinja2 templates
├── static/               # CSS, uploads
├── rag/                  # Care-reference documents + vector DB
├── render.yaml           # Render deployment blueprint
└── requirements.txt
```

---

## ☁️ Deployment (Render)

The repo includes a `render.yaml` blueprint. On Render:
1. **New → Blueprint**, connect this repo — it auto-detects `render.yaml`.
2. Set the `GROQ_API_KEY` environment variable.
3. Deploy. A managed PostgreSQL database is provisioned automatically.

---

## 📜 License

Built for AnimalHack 2026. Free to use for educational and non-commercial purposes.
