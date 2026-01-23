# 🦷 SmileCare AI Booking Assistant

A chat-based **AI-powered Booking Assistant** built with **Streamlit**, **LangChain**, and **OpenAI**, designed for a dental clinic use case. The application supports **RAG (Retrieval-Augmented Generation)** using uploaded PDFs, conversational appointment booking, email confirmations, and a secure **Admin/Receptionist Dashboard**.

🔗 **Live Demo:** [https://dental-ai-assistant-5epven85r9jgqqwgvhqfbi.streamlit.app/](https://dental-ai-assistant-5epven85r9jgqqwgvhqfbi.streamlit.app/)

---

## 📌 Problem Statement Alignment

This project fully satisfies the given **AI Booking Assistant – Problem Statement**:

* ✅ Chat-based AI application
* ✅ RAG support via user-uploaded PDFs
* ✅ Booking intent detection & guided data collection
* ✅ Confirmation before database storage
* ✅ Email confirmation after booking
* ✅ Mandatory Admin Dashboard for managing bookings
* ✅ Deployed on Streamlit Cloud with public URL
* ✅ Creative booking domain (Dental Clinic)

---

## 🚀 Features

### 🤖 AI Chat Assistant

* Natural language chat interface
* Detects booking-related intents ("book appointment", "schedule visit", etc.)
* Conversationally collects:

  * Name
  * Email
  * Date
  * Time
* Confirms details before final booking

### 📄 RAG (Retrieval-Augmented Generation)

* Upload clinic brochures / PDFs
* AI answers questions **only from uploaded documents**
* Falls back gracefully if info is unavailable

### 🗄️ Booking Management

* Stores bookings in **SQLite** database
* Status lifecycle: Confirmed / Pending / Cancelled / Completed

### 📧 Email Notifications

* Automatic appointment confirmation email
* Uses SMTP (Gmail supported)

### 🏥 Staff Dashboard

**Receptionist**

* View bookings
* Update booking status

**Admin**

* Full booking control (update + delete)
* View audit logs
* Analytics dashboard

### 📊 Analytics

* Total bookings
* Status distribution
* Bar chart visualization

### 🛡️ Audit Logs

* Tracks admin actions (status changes, deletions)

---

## 🧱 Tech Stack

| Layer      | Technology                |
| ---------- | ------------------------- |
| UI         | Streamlit                 |
| AI / LLM   | OpenAI (via LangChain)    |
| RAG        | FAISS + OpenAI Embeddings |
| Backend    | Python                    |
| Database   | SQLite                    |
| Email      | SMTP (Gmail)              |
| Deployment | Streamlit Cloud           |

---

## 📁 Project Structure

```
📦 dental-ai-assistant
 ┣ 📜 app.py                # Main Streamlit application
 ┣ 📜 requirements.txt      # Python dependencies
 ┣ 📜 runtime.txt           # Python runtime version
 ┣ 📜 README.md             # Project documentation
 ┗ 📜 bookings.db           # SQLite database (auto-created)
```

---

## ⚙️ Requirements

### 🔹 Python Version

```
Python 3.10
```

> Required for Streamlit Cloud compatibility

### 🔹 Python Libraries

Create `requirements.txt`:

```
streamlit
pandas
sqlite3
langchain
langchain-openai
langchain-community
faiss-cpu
pypdf
python-dotenv
```

---

## 🔐 Secrets Configuration

Set secrets in **Streamlit Cloud → App Settings → Secrets**

```toml
OPENAI_API_KEY = "your_openai_api_key"
SMTP_EMAIL = "your_email@gmail.com"
SMTP_PASSWORD = "your_app_password"
ADMIN_PASSWORD = "admin123"
RECEPTIONIST_PASSWORD = "reception123"
```

> ⚠️ Use **Gmail App Password**, not your real password

---

## ▶️ Running Locally

```bash
# Clone repository
git clone https://github.com/your-username/dental-ai-assistant.git
cd dental-ai-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run app
streamlit run app.py
```

App runs at: `http://localhost:8501`

---

## 🌐 Deployment (Streamlit Cloud)

1. Push code to **GitHub**
2. Go to **[https://streamlit.io/cloud](https://streamlit.io/cloud)**
3. Click **New App**
4. Select:

   * Repository
   * Branch: `main`
   * Main file: `app.py`
5. Add **Secrets** (see above)
6. Deploy 🎉

---

## 🧪 Sample Usage

### Booking Flow

```
User: I want to book an appointment
AI: What is your full name?
User: Rahul Sharma
AI: What is your email?
User: rahul@gmail.com
AI: What date?
User: 2025-02-01
AI: What time?
User: 10:30 AM
AI: Please confirm details. Type Yes.
User: Yes
AI: Booking confirmed! Email sent.
```

---

## 🔮 Future Enhancements

* OTP-based email verification
* Multi-doctor scheduling
* Time-slot availability checks
* Calendar (Google Calendar) sync
* WhatsApp/SMS notifications
* Role-based user authentication

---

## 👨‍💻 Author

**Koushik Mamidi**
Computer Science Student | AI & Cloud Enthusiast

---

## ⭐ Final Notes

This project demonstrates:

* Real-world AI + RAG integration
* Conversational state management
* Secure admin workflows
* Production-ready Streamlit deployment

Perfect fit for **internships, hackathons, and AI project evaluations** 🚀

---

✅ **End of README.md**
