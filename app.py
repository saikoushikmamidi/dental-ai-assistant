import streamlit as st
import pandas as pd
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
# --- EMAIL CONFIG ---
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.retrieval_qa.base import RetrievalQA

def get_rag_chain(vectorstore):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        chain_type="stuff",
        return_source_documents=False
    )
    return qa_chain



# --- CONFIGURATION ---
# In a real app, use st.secrets or environment variables
# st.secrets["OPENAI_API_KEY"]

import os

os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            patient_email TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            booking_type TEXT,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            booking_id INTEGER,
            performed_by TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    
def update_booking_status(booking_id, new_status, admin="Admin"):
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()

    c.execute(
        "UPDATE bookings SET status=? WHERE id=?",
        (new_status, booking_id)
    )

    c.execute(
        "INSERT INTO admin_logs (action, booking_id, performed_by) VALUES (?, ?, ?)",
        (f"Status changed to {new_status}", booking_id, admin)
    )

    conn.commit()
    conn.close()


def delete_booking(booking_id, admin="Admin"):
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()

    c.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    c.execute(
        "INSERT INTO admin_logs (action, booking_id, performed_by) VALUES (?, ?, ?)",
        ("Booking deleted", booking_id, admin)
    )

    conn.commit()
    conn.close()


def add_booking(name, email, date, time, booking_type="Dental Consultation"):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()

    c.execute("""
        INSERT INTO bookings 
        (patient_name, patient_email, appointment_date, appointment_time, booking_type, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, email, date, time, booking_type, "Confirmed"))

    booking_id = c.lastrowid  # ✅ THIS IS IMPORTANT
    conn.commit()
    conn.close()

    return booking_id


def get_all_bookings():
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('SELECT * FROM bookings ORDER BY timestamp DESC')
    data = c.fetchall()
    conn.close()
    return data

import re
from datetime import datetime

def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)

def is_valid_date(date_text):
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_text):
    try:
        datetime.strptime(time_text, "%I:%M %p")  # 10:30 AM
        return True
    except ValueError:
        return False

def is_greeting(text):
    greetings = [
        "hello", "hi", "hey", "good morning",
        "good afternoon", "good evening", "hola"
    ]
    text = text.lower().strip()
    return any(greet in text for greet in greetings)

def greeting_response():
    return (
        "Hello! 😊 Welcome to SmileCare Dental Clinic.\n\n"
        "How can I help you today?\n"
        "• Book an appointment\n"
        "• Clinic timings\n"
        "• Treatments offered\n"
        "• Doctors information"
    )
def is_thanks(text):
    thanks_words = ["thanks", "thank you", "thx", "ty"]
    return any(word in text.lower() for word in thanks_words)
def thanks_response():
    return "😊 You're welcome! If you need anything else or want to book an appointment, just let me know."

def send_email_confirmation(
    to_email,
    name,
    booking_id,
    date,
    time,
    booking_type="Dental Consultation"
):
    try:
        subject = "🦷 Appointment Confirmation - SmileCare Dental Clinic"

        body = f"""
Hello {name},

✅ Your appointment has been successfully booked!

📌 Booking Details:
-------------------------
Booking ID   : {booking_id}
Name         : {name}
Date         : {date}
Time         : {time}
Appointment  : {booking_type}

📍 Location:
SmileCare Dental Clinic
Hyderabad, Telangana

If you need to reschedule or cancel, please contact us.

📞 Phone: 9876543210
📧 Email: smilecare@gmail.com

Thank you for choosing SmileCare Dental Clinic!
"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        return True  # ✅ Email sent successfully

    except Exception as e:
        print("EMAIL ERROR:", e)
        return False  # ❌ Failed safely

def send_admin_alert(booking_id, name, date, time):
    try:
        subject = "📢 New Appointment Booked - Admin Alert"

        body = f"""
New appointment has been booked.

📌 Booking Details:
-------------------------
Booking ID : {booking_id}
Patient    : {name}
Date       : {date}
Time       : {time}

Please review this booking in the admin dashboard.
"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = SMTP_EMAIL

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

    except Exception as e:
        print("ADMIN EMAIL ERROR:", e)

# --- RAG & LLM LOGIC ---
def get_vectorstore(pdf_file):
    # Save uploaded file temporarily
    with open("temp.pdf", "wb") as f:
        f.write(pdf_file.getvalue())
    
    loader = PyPDFLoader("temp.pdf")
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    
    # Create Vector Store
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(splits, embeddings)
    return vectorstore


    

def detect_booking_intent(user_input):
    """Simple keyword/LLM check to see if user wants to book."""
    keywords = ["book", "schedule", "appointment", "reserve", "slot"]
    return any(word in user_input.lower() for word in keywords)

# --- STREAMLIT UI ---
st.set_page_config(page_title="Dental AI Assistant", layout="wide")
init_db()

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "booking_state" not in st.session_state:
    st.session_state.booking_state = "IDLE" # IDLE, NAME, DATE, TIME, CONFIRM
if "booking_data" not in st.session_state:
    st.session_state.booking_data = {}
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = None

# Sidebar - Admin & Upload
# =======================
# SIDEBAR
# =======================
with st.sidebar:
    st.title("⚙️ Controls")

    # =======================
    # 1️⃣ PDF Upload (RAG)
    # =======================
    st.subheader("1️⃣ Upload Knowledge Base")
    pdf_file = st.file_uploader(
        "Upload Clinic Brochure (PDF)",
        type=["pdf"]
    )

    if pdf_file and st.button("📚 Process PDF"):
        with st.spinner("Indexing PDF..."):
            st.session_state.vectorstore = get_vectorstore(pdf_file)
        st.success("✅ Knowledge Base Ready!")

    # =======================
    # 2️⃣ ADMIN DASHBOARD
    # =======================
    st.divider()
    st.subheader("2️⃣ Admin Dashboard")

    role = st.selectbox("Login As", ["Receptionist", "Admin"])
    admin_pass = st.text_input("Password", type="password")

    if "user_role" not in st.session_state:
        st.session_state.user_role = None

    # 🔐 LOGIN CHECK
    if role == "Admin" and admin_pass == st.secrets["ADMIN_PASSWORD"]:
        st.session_state.user_role = "Admin"
        st.success("✅ Admin Access Granted")

    elif role == "Receptionist" and admin_pass == st.secrets["RECEPTIONIST_PASSWORD"]:
        st.session_state.user_role = "Receptionist"
        st.success("✅ Receptionist Access Granted")

    elif admin_pass:
        st.error("❌ Invalid Password")


# =======================
# 📋 SHARED VIEW (ADMIN + RECEPTIONIST)
# =======================
if st.session_state.user_role in ["Admin", "Receptionist"]:

    bookings = get_all_bookings()

    if bookings:
        df = pd.DataFrame(
            bookings,
            columns=[
                "ID", "Name", "Email",
                "Date", "Time",
                "Type", "Status", "Created At"
            ]
        )

        st.subheader("📋 Booking Records")
        st.dataframe(df, use_container_width=True)

    else:
        st.info("ℹ️ No bookings found.")

# =======================
# 👑 ADMIN-ONLY FEATURES
# =======================
if st.session_state.user_role == "Admin" and bookings:

    # 📊 ANALYTICS
    st.subheader("📊 Booking Analytics")

    today = datetime.today().strftime("%Y-%m-%d")
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Bookings", len(df))
    col2.metric("Today's Bookings", len(df[df["Date"] == today]))
    col3.metric("Cancelled", len(df[df["Status"] == "Cancelled"]))

    st.divider()

    # 🔍 SEARCH & FILTER
    search = st.text_input("🔍 Search by Name or Email")
    status_filter = st.selectbox(
        "Filter by Status",
        ["All", "Pending", "Confirmed", "Cancelled", "Completed"]
    )

    if search:
        df = df[
            df["Name"].str.contains(search, case=False, na=False) |
            df["Email"].str.contains(search, case=False, na=False)
        ]

    if status_filter != "All":
        df = df[df["Status"] == status_filter]

    st.divider()

    # 📥 EXPORT CSV
    st.download_button(
        "⬇️ Download Bookings CSV",
        data=df.to_csv(index=False),
        file_name="bookings.csv",
        mime="text/csv"
    )

    st.divider()

    # 🛠 ADMIN CONTROLS
    st.subheader("🛠 Admin Controls")

    for _, row in df.iterrows():
        with st.expander(f"🆔 Booking #{row['ID']} — {row['Name']}"):

            st.write({
                "Email": row["Email"],
                "Date": row["Date"],
                "Time": row["Time"],
                "Type": row["Type"],
                "Status": row["Status"],
                "Created At": row["Created At"]
            })

            new_status = st.selectbox(
                "Update Status",
                ["Pending", "Confirmed", "Cancelled", "Completed"],
                index=[
                    "Pending",
                    "Confirmed",
                    "Cancelled",
                    "Completed"
                ].index(row["Status"]),
                key=f"status_{row['ID']}"
            )

            if st.button("💾 Save Status", key=f"save_{row['ID']}"):
                update_booking_status(row["ID"], new_status)
                st.success("✅ Status updated")
                st.rerun()

            st.divider()

            if st.button("❌ Delete Booking", key=f"del_{row['ID']}"):
                delete_booking(row["ID"])
                st.warning("🗑 Booking deleted")
                st.rerun()

    # 🕵️ AUDIT LOGS
    st.divider()
    st.subheader("🕵️ Admin Audit Logs")

    conn = sqlite3.connect("bookings.db")
    logs = pd.read_sql(
        "SELECT * FROM admin_logs ORDER BY timestamp DESC",
        conn
    )
    conn.close()

    if logs.empty:
        st.info("No admin actions recorded yet.")
    else:
        st.dataframe(logs, use_container_width=True)



# =======================
# MAIN CHAT UI
# =======================
st.title("🦷 Dental Clinic AI Assistant")
st.markdown("Ask about our services or **book an appointment**!")


# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT & BOOKING LOGIC FLOW ---
if prompt := st.chat_input("Type your message..."):
    
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    response_text = ""

    # STATE MACHINE HANDLER
    # STATE MACHINE HANDLER
    if st.session_state.booking_state == "IDLE":

        # 🔹 STEP 1: GREETING CHECK
        if is_greeting(prompt):
            response_text = greeting_response()

        # THANK YOU CHECK
        elif is_thanks(prompt):
            response_text = thanks_response()

        # 🔹 STEP 2: BOOKING INTENT
        elif detect_booking_intent(prompt):
            st.session_state.booking_state = "NAME"
            response_text = "I can help you book an appointment. First, strictly what is your **Full Name**?"

        # 🔹 STEP 3: RAG / DOCUMENT RESPONSE
        # 🔹 STEP 3: RAG / DOCUMENT RESPONSE
        else:
            if st.session_state.vectorstore:
                rag_chain = get_rag_chain(st.session_state.vectorstore)
                response = rag_chain.invoke({"query": prompt})
                response_text = response["result"]
            else:
                response_text = (
                    "Please upload a PDF brochure in the sidebar so I can answer your questions, "
                    "or just say **'Book'** to schedule an appointment."
                )



    # COLLECTING NAME
    elif st.session_state.booking_state == "NAME":
        st.session_state.booking_data["name"] = prompt
        st.session_state.booking_state = "EMAIL"
        response_text = "Please enter your **Email Address**"

    elif st.session_state.booking_state == "EMAIL":
        if not is_valid_email(prompt):
            response_text = "❌ Invalid email format.\nPlease enter a valid **Email Address** (example: name@gmail.com)"
        else:
            st.session_state.booking_data["email"] = prompt
            st.session_state.booking_state = "DATE"
            response_text = "What **Date** would you like? (YYYY-MM-DD)"


    # COLLECTING DATE
    elif st.session_state.booking_state == "DATE":
        if not is_valid_date(prompt):
            response_text = "❌ Invalid date format.\nPlease enter the date in **YYYY-MM-DD** format."
        else:
            st.session_state.booking_data["date"] = prompt
            st.session_state.booking_state = "TIME"
            response_text = "Got it. What **Time** works for you? (e.g., 10:30 AM)"


    # COLLECTING TIME
    elif st.session_state.booking_state == "TIME":
        if not is_valid_time(prompt):
            response_text = "❌ Invalid time format.\nPlease enter time like **10:30 AM**"
        else:
            st.session_state.booking_data["time"] = prompt
            st.session_state.booking_state = "CONFIRM"
            data = st.session_state.booking_data
            response_text = (
                f"Please confirm details:\n"
                f"- **Name:** {data['name']}\n"
                f"- **Date:** {data['date']}\n"
                f"- **Time:** {data['time']}\n\n"
                f"Type **'Yes'** to confirm or **'No'** to cancel."
            )

    # CONFIRMATION
    elif st.session_state.booking_state == "CONFIRM":
        if prompt.lower() in ["yes", "y", "confirm", "ok"]:

            data = st.session_state.booking_data

            # 1️⃣ SAVE TO DB (get booking ID)
            booking_id = add_booking(
                data["name"],
                data["email"],
                data["date"],
                data["time"],
                "Dental Consultation"
            )

            # 2️⃣ SEND CONFIRMATION EMAIL
            email_sent = send_email_confirmation(
                to_email=data["email"],
                name=data["name"],
                booking_id=booking_id,
                date=data["date"],
                time=data["time"],
                booking_type="Dental Consultation"
            )

            # 📧 EMAIL ADMIN ALERT
            send_admin_alert(
                booking_id=booking_id,
                name=data["name"],
                date=data["date"],
                time=data["time"]
            )



            # 3️⃣ USER RESPONSE
            if email_sent:
                response_text = (
                    f"✅ Booking Confirmed!\n"
                    f"🆔 Booking ID: {booking_id}\n"
                    f"📧 Confirmation email sent successfully."
                )

            
            else:
                response_text = (
                    f"⚠️ Booking Confirmed!\n"
                    f"🆔 Booking ID: {booking_id}\n"
                    f"📧 Email could not be sent."
                )

        else:
            response_text = "❌ Booking cancelled. You can ask me other questions."

        
        # Reset State
        st.session_state.booking_state = "IDLE"
        st.session_state.booking_data = {}

    # Display Assistant Response
    with st.chat_message("assistant"):
        st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})
