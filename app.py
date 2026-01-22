import streamlit as st
import pandas as pd
import sqlite3
import smtplib
import os
import re
from email.mime.text import MIMEText
from datetime import datetime

# --- LANGCHAIN IMPORTS ---
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# --- CONFIGURATION & SECRETS ---
st.set_page_config(page_title="SmileCare AI Assistant", layout="wide", page_icon="🦷")

# Helper to safely get secrets
def get_secret(key):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)

# Load API Keys
os.environ["OPENAI_API_KEY"] = get_secret("OPENAI_API_KEY")
SMTP_EMAIL = get_secret("SMTP_EMAIL")
SMTP_PASSWORD = get_secret("SMTP_PASSWORD")

# --- DATABASE MANAGEMENT ---
def init_db():
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    # Bookings Table
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
    # Admin Logs Table
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

def add_booking(name, email, date, time, booking_type="Dental Consultation"):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("""
        INSERT INTO bookings 
        (patient_name, patient_email, appointment_date, appointment_time, booking_type, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, email, date, time, booking_type, "Confirmed"))
    booking_id = c.lastrowid
    conn.commit()
    conn.close()
    return booking_id

def get_all_bookings():
    conn = sqlite3.connect('bookings.db')
    df = pd.read_sql('SELECT * FROM bookings ORDER BY timestamp DESC', conn)
    conn.close()
    return df

def update_booking_status(booking_id, new_status, admin_name):
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()
    c.execute("UPDATE bookings SET status=? WHERE id=?", (new_status, booking_id))
    
    # Log the action
    c.execute(
        "INSERT INTO admin_logs (action, booking_id, performed_by) VALUES (?, ?, ?)",
        (f"Status changed to {new_status}", booking_id, admin_name)
    )
    conn.commit()
    conn.close()

def delete_booking(booking_id, admin_name):
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()
    c.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    
    # Log the action
    c.execute(
        "INSERT INTO admin_logs (action, booking_id, performed_by) VALUES (?, ?, ?)",
        ("Booking deleted", booking_id, admin_name)
    )
    conn.commit()
    conn.close()

def get_logs():
    conn = sqlite3.connect("bookings.db")
    df = pd.read_sql("SELECT * FROM admin_logs ORDER BY timestamp DESC", conn)
    conn.close()
    return df

# --- EMAIL LOGIC ---
def send_email_confirmation(to_email, name, booking_id, date, time, booking_type="Dental Consultation"):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False # Skip if secrets aren't set

    try:
        subject = "🦷 Appointment Confirmation - SmileCare Dental"
        body = f"""
        Hello {name},

        ✅ Your appointment is confirmed!

        📌 Details:
        ID: {booking_id}
        Date: {date}
        Time: {time}
        Type: {booking_type}

        See you soon!
        SmileCare Team
        """
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

# --- RAG / AI LOGIC ---
@st.cache_resource
def process_pdf(file):
    with open("temp.pdf", "wb") as f:
        f.write(file.getvalue())
    loader = PyPDFLoader("temp.pdf")
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()
    return FAISS.from_documents(splits, embeddings)

def get_rag_response(vectorstore, question):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    prompt = ChatPromptTemplate.from_template(
        """You are a dental clinic receptionist. Answer based on context. 
        If unknown, say "I don't have that info, please call us."
        
        Context: {context}
        Question: {question}
        Answer:"""
    )
    
    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
    )
    return chain.invoke(question).content

# --- VALIDATION HELPERS ---
def is_valid_email(email):
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email)

def is_valid_date(date_text):
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_text):
    try:
        datetime.strptime(time_text, "%I:%M %p")
        return True
    except ValueError:
        return False

# --- MAIN APP ---
def main():
    init_db()

    # Session State Init
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "booking_state" not in st.session_state:
        st.session_state.booking_state = "IDLE"
    if "booking_data" not in st.session_state:
        st.session_state.booking_data = {}
    if "vectorstore" not in st.session_state:
        st.session_state.vectorstore = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = "User" # User, Admin, Receptionist

    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3063/3063212.png", width=80)
        st.title("SmileCare")
        
        # Navigation
        app_mode = st.radio("Navigate", ["Chat Assistant", "Staff Dashboard"])
        
        st.divider()
        
        # RAG Upload
        st.subheader("📁 Knowledge Base")
        pdf_file = st.file_uploader("Upload Brochure", type=["pdf"])
        if pdf_file and st.button("Update Knowledge"):
            with st.spinner("Processing..."):
                st.session_state.vectorstore = process_pdf(pdf_file)
            st.success("Brain Updated!")

    # --- PAGE: CHAT ASSISTANT ---
    if app_mode == "Chat Assistant":
        st.header("👋 Welcome to SmileCare Dental")
        st.caption("I can help you answer questions or book appointments.")

        # Chat History
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        # Input Handler
        if prompt := st.chat_input("How can I help you today?"):
            # 1. Add User Message
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            response_text = ""
            
            # --- CONVERSATION STATE MACHINE ---
            state = st.session_state.booking_state
            
            if state == "IDLE":
                booking_keywords = ["book", "appointment", "schedule"]
                if any(x in prompt.lower() for x in booking_keywords):
                    st.session_state.booking_state = "NAME"
                    response_text = "I'd be happy to book that for you. What is your **Full Name**?"
                elif st.session_state.vectorstore:
                    response_text = get_rag_response(st.session_state.vectorstore, prompt)
                else:
                    response_text = "I can help with bookings! Say 'Book appointment' to start. (Upload a PDF to ask me specific questions!)"

            elif state == "NAME":
                st.session_state.booking_data["name"] = prompt
                st.session_state.booking_state = "EMAIL"
                response_text = f"Thanks {prompt}. What is your **Email Address**?"

            elif state == "EMAIL":
                if is_valid_email(prompt):
                    st.session_state.booking_data["email"] = prompt
                    st.session_state.booking_state = "DATE"
                    response_text = "Great. What **Date**? (YYYY-MM-DD)"
                else:
                    response_text = "❌ Invalid email. Please try again (e.g., tom@mail.com)."

            elif state == "DATE":
                if is_valid_date(prompt):
                    st.session_state.booking_data["date"] = prompt
                    st.session_state.booking_state = "TIME"
                    response_text = "And what **Time**? (e.g., 10:30 AM)"
                else:
                    response_text = "❌ Please use format YYYY-MM-DD."

            elif state == "TIME":
                if is_valid_time(prompt):
                    st.session_state.booking_data["time"] = prompt
                    st.session_state.booking_state = "CONFIRM"
                    d = st.session_state.booking_data
                    response_text = f"""Please confirm:
                    **Name:** {d['name']}
                    **Date:** {d['date']} at {d['time']}
                    
                    Type 'Yes' to confirm."""
                else:
                    response_text = "❌ Please use format HH:MM AM/PM (e.g. 10:30 AM)."

            elif state == "CONFIRM":
                if prompt.lower() in ["yes", "y", "ok"]:
                    d = st.session_state.booking_data
                    bid = add_booking(d['name'], d['email'], d['date'], d['time'])
                    send_email_confirmation(d['email'], d['name'], bid, d['date'], d['time'])
                    response_text = f"✅ Done! Booking #{bid} confirmed. Email sent."
                else:
                    response_text = "❌ Booking cancelled."
                
                # Reset
                st.session_state.booking_state = "IDLE"
                st.session_state.booking_data = {}

            # 2. Add Assistant Message
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.chat_message("assistant").write(response_text)

    # --- PAGE: STAFF DASHBOARD ---
    elif app_mode == "Staff Dashboard":
        st.header("🏥 Staff Dashboard")

        # LOGIN LOGIC
        if st.session_state.user_role == "User":
            c1, c2 = st.columns(2)
            with c1:
                role_select = st.selectbox("Role", ["Receptionist", "Admin"])
                password = st.text_input("Password", type="password")
                if st.button("Login"):
                    # Check Secrets
                    if role_select == "Admin" and password == get_secret("ADMIN_PASSWORD"):
                        st.session_state.user_role = "Admin"
                        st.rerun()
                    elif role_select == "Receptionist" and password == get_secret("RECEPTIONIST_PASSWORD"):
                        st.session_state.user_role = "Receptionist"
                        st.rerun()
                    else:
                        st.error("Invalid Credentials")
        
        else:
            # LOGGED IN VIEW
            st.success(f"Logged in as: **{st.session_state.user_role}**")
            if st.button("Logout"):
                st.session_state.user_role = "User"
                st.rerun()

            # TABS FOR UI CLEANUP
            tab_bookings, tab_analytics, tab_logs = st.tabs(["📅 Bookings", "📊 Analytics", "🛡️ Audit Logs"])

            df = get_all_bookings()

            # --- TAB 1: BOOKINGS ---
            with tab_bookings:
                # Search & Filter
                col_search, col_filter = st.columns([3, 1])
                search_term = col_search.text_input("🔍 Search Name or Email")
                status_filter = col_filter.selectbox("Filter Status", ["All", "Confirmed", "Pending", "Cancelled", "Completed"])

                # Apply Filters
                if not df.empty:
                    filtered_df = df.copy()
                    
                    # Fix Search: Ensure string conversion and handle case
                    if search_term:
                        filtered_df = filtered_df[
                            filtered_df["patient_name"].astype(str).str.contains(search_term, case=False) | 
                            filtered_df["patient_email"].astype(str).str.contains(search_term, case=False)
                        ]
                    
                    if status_filter != "All":
                        filtered_df = filtered_df[filtered_df["status"] == status_filter]

                    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

                    # --- ACTION PANEL (Below Table) ---
                    st.divider()
                    st.subheader("✏️ Manage Selected Booking")
                    
                    # Select Booking ID
                    booking_ids = filtered_df["id"].tolist()
                    if booking_ids:
                        selected_id = st.selectbox("Select Booking ID to Edit", booking_ids)
                        
                        # Get current status of selected
                        current_row = filtered_df[filtered_df["id"] == selected_id].iloc[0]
                        st.info(f"Selected: **{current_row['patient_name']}** (Current Status: {current_row['status']})")
                        
                        c1, c2 = st.columns(2)
                        
                        # 1. Update Status (Available to BOTH)
                        with c1:
                            new_status = st.selectbox("Change Status", ["Confirmed", "Pending", "Cancelled", "Completed"], key="sbox")
                            if st.button("Update Status"):
                                update_booking_status(selected_id, new_status, st.session_state.user_role)
                                st.success("Status Updated!")
                                st.rerun()

                        # 2. Delete (ADMIN ONLY)
                        with c2:
                            if st.session_state.user_role == "Admin":
                                if st.button("🗑️ Delete Booking", type="primary"):
                                    delete_booking(selected_id, st.session_state.user_role)
                                    st.warning("Booking Deleted.")
                                    st.rerun()
                            else:
                                st.caption("🚫 Delete restricted to Admin.")
                    else:
                        st.info("No bookings match your filter.")
                else:
                    st.info("No bookings in database.")

            # --- TAB 2: ANALYTICS ---
            with tab_analytics:
                if not df.empty:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Bookings", len(df))
                    col2.metric("Confirmed", len(df[df['status']=="Confirmed"]))
                    col3.metric("Cancelled", len(df[df['status']=="Cancelled"]))
                    
                    st.bar_chart(df["status"].value_counts())
                else:
                    st.write("No data for analytics.")

            # --- TAB 3: AUDIT LOGS (ADMIN ONLY) ---
            with tab_logs:
                if st.session_state.user_role == "Admin":
                    logs_df = get_logs()
                    if not logs_df.empty:
                        st.dataframe(logs_df, use_container_width=True)
                    else:
                        st.info("No logs available.")
                else:
                    st.warning("🔒 Access Restricted to Admin only.")

if __name__ == "__main__":
    main()
