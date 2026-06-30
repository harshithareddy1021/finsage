import streamlit as st
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
import os
from datetime import date as date_type

from ocr.ocr_engine import extract_transaction_from_image
from database.db import (
    create_table, save_transaction, load_transactions,
    delete_transaction, register_user, login_user
)
from advice.advisor import generate_financial_advice, build_rag_from_pdf, query_rag
from advice.sql_agent import query_expenses

# ─────────────────────────────────────────
# Init DB
# ─────────────────────────────────────────
create_table()

# ─────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="FinanceAI",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    /* Hide streamlit default header */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Cards */
    .finance-card {
        background-color: #1e2130;
        border: 1px solid #2d2d3a;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        color: #ffffff;
    }

    /* Logo */
    .logo-text {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6c63ff, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 8px;
    }

    .logo-subtitle {
        text-align: center;
        color: #9ca3af;
        font-size: 0.95rem;
        margin-bottom: 24px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Session State Init
# ─────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

# ═══════════════════════════════════════════
# AUTH PAGE
# ═══════════════════════════════════════════
def show_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="logo-text">💰 FinanceAI</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="logo-subtitle">Your AI-powered personal finance advisor</div>',
            unsafe_allow_html=True
        )

        tab1, tab2 = st.tabs(["Login", "Register"])

        # ── Login Tab ──
        with tab1:
            st.markdown("### Welcome back")
            email = st.text_input("Email", key="login_email", placeholder="you@example.com")
            password = st.text_input(
                "Password", type="password", key="login_password",
                placeholder="Enter your password"
            )
            st.markdown("")
            if st.button("Login", type="primary", key="login_btn", use_container_width=True):
                if email and password:
                    success, user, message = login_user(email, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.success(f"Welcome back, {user['name']}!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please fill in all fields.")

        # ── Register Tab ──
        with tab2:
            st.markdown("### Create your account")
            name = st.text_input("Full Name", key="reg_name", placeholder="John Doe")
            email_reg = st.text_input("Email", key="reg_email", placeholder="you@example.com")
            password_reg = st.text_input(
                "Password", type="password", key="reg_password",
                placeholder="Min 6 characters"
            )
            password_confirm = st.text_input(
                "Confirm Password", type="password", key="reg_confirm",
                placeholder="Repeat your password"
            )
            st.markdown("")
            if st.button("Create Account", type="primary", key="reg_btn", use_container_width=True):
                if name and email_reg and password_reg and password_confirm:
                    if len(password_reg) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif password_reg != password_confirm:
                        st.error("Passwords do not match.")
                    else:
                        success, message = register_user(name, email_reg, password_reg)
                        if success:
                            st.success("Account created! Please login.")
                        else:
                            st.error(message)
                else:
                    st.error("Please fill in all fields.")

# ═══════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════
def show_main_app():
    user = st.session_state.user
    user_id = user["id"]

    # ── Sidebar ──
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.caption(user['email'])
        st.divider()

        page = st.radio(
            "Navigate",
            [
                "📸 Upload & Extract",
                "✏️ Manual Entry",
                "💬 Ask Your Expenses",
                "📚 Book Advisor",
                "📊 Dashboard"
            ]
        )

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

    # ═══════════════════════════════════════
    # PAGE 1 — Upload & Extract
    # ═══════════════════════════════════════
    if page == "📸 Upload & Extract":
        st.title("📸 Upload Payment Screenshot")
        st.caption("Supports Swiggy, Zomato, GPay, PhonePe, Amazon, any UPI screenshot")
        st.divider()

        uploaded_file = st.file_uploader(
            "Drop your screenshot here",
            type=["png", "jpg", "jpeg"]
        )

        if uploaded_file:
            image = Image.open(uploaded_file)
            col1, col2 = st.columns(2)

            with col1:
                st.image(image, caption="Uploaded Screenshot", width=350)

            with col2:
                with st.spinner("🔍 AI is reading your screenshot..."):
                    transaction = extract_transaction_from_image(image)

                st.subheader("✅ Extracted Details")
                st.caption("Review and correct if needed before saving")

                merchant_val = transaction.get("merchant") or ""
                transaction["merchant"] = st.text_input("Merchant", value=merchant_val)

                amount_val = float(transaction.get("amount") or 0.0)
                transaction["amount"] = st.number_input(
                    "Amount (₹)", value=amount_val, min_value=0.0
                )

                date_val = transaction.get("date") or ""
                transaction["date"] = st.text_input("Date", value=date_val)

                categories = ["Food", "Shopping", "Transport",
                              "Entertainment", "Utilities", "Healthcare", "Others"]
                extracted_cat = transaction.get("category") or "Others"
                if extracted_cat not in categories:
                    extracted_cat = "Others"
                transaction["category"] = st.selectbox(
                    "Category", categories,
                    index=categories.index(extracted_cat)
                )

                payment_methods = ["UPI", "Credit Card", "Debit Card",
                                   "Net Banking", "Cash", "Unknown"]
                extracted_method = transaction.get("payment_method") or "Unknown"
                if extracted_method not in payment_methods:
                    extracted_method = "Unknown"
                transaction["payment_method"] = st.selectbox(
                    "Payment Method", payment_methods,
                    index=payment_methods.index(extracted_method)
                )

                if st.button("💾 Save Transaction", type="primary"):
                    if transaction["amount"] > 0:
                        if not transaction["merchant"]:
                            transaction["merchant"] = "Unknown Merchant"
                        save_transaction(transaction, user_id)
                        st.success("✅ Transaction saved!")
                        st.balloons()
                    else:
                        st.error("Amount must be greater than 0.")

    # ═══════════════════════════════════════
    # PAGE 2 — Manual Entry
    # ═══════════════════════════════════════
    elif page == "✏️ Manual Entry":
        st.title("✏️ Add Expense Manually")
        st.caption("No screenshot? Add your expense directly.")
        st.divider()

        with st.form("manual_entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                merchant = st.text_input(
                    "Merchant / Shop Name",
                    placeholder="e.g. Dominos, DMart, Ola"
                )
                amount = st.number_input("Amount (₹)", min_value=0.0, step=1.0)
                selected_date = st.date_input("Date", value=date_type.today())
            with col2:
                category = st.selectbox(
                    "Category",
                    ["Food", "Shopping", "Transport",
                     "Entertainment", "Utilities", "Healthcare", "Others"]
                )
                payment_method = st.selectbox(
                    "Payment Method",
                    ["UPI", "Credit Card", "Debit Card", "Net Banking", "Cash", "Unknown"]
                )

            submitted = st.form_submit_button("💾 Save Expense", type="primary")
            if submitted:
                if amount > 0:
                    transaction = {
                        "merchant": merchant if merchant else "Unknown Merchant",
                        "amount": amount,
                        "date": selected_date.strftime("%d/%m/%Y"),
                        "category": category,
                        "payment_method": payment_method
                    }
                    save_transaction(transaction, user_id)
                    st.success(f"✅ ₹{amount} expense saved!")
                    st.balloons()
                else:
                    st.error("Amount must be greater than 0.")

    # ═══════════════════════════════════════
    # PAGE 3 — Ask Your Expenses
    # ═══════════════════════════════════════
    elif page == "💬 Ask Your Expenses":
        st.title("💬 Ask About Your Spending")
        st.caption("Ask anything in plain English. Powered by LangChain SQL Agent.")
        st.divider()

        st.info("""
        **Try asking:**
        - How much did I spend on Food?
        - What is my total spending?
        - Which category has the highest spending?
        - Show me all UPI transactions
        - What was my most expensive purchase?
        """)

        question = st.text_input(
            "Your question",
            placeholder="e.g. How much did I spend on food?"
        )

        if st.button("🔍 Ask", type="primary") and question:
            with st.spinner("🤖 LangChain SQL Agent is thinking..."):
                answer = query_expenses(question)
            st.subheader("Answer:")
            st.markdown(f"""
            <div class="finance-card">
                {answer}
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.subheader("📜 All Transactions")
        transactions = load_transactions(user_id)
        if transactions:
            df = pd.DataFrame(transactions)
            st.dataframe(df, use_container_width=True)

            st.subheader("🗑️ Delete a Transaction")
            transaction_options = {
                f"#{t['id']} — {t['merchant']} — ₹{t['amount']} — {t['date']}": t['id']
                for t in transactions
            }
            selected = st.selectbox(
                "Select transaction to delete",
                options=list(transaction_options.keys())
            )
            if st.button("🗑️ Delete Selected", type="primary"):
                transaction_id = transaction_options[selected]
                delete_transaction(transaction_id, user_id)
                st.success("✅ Transaction deleted!")
                st.rerun()
        else:
            st.info("No transactions yet. Upload a screenshot or add manually.")

    # ═══════════════════════════════════════
    # PAGE 4 — Book Advisor
    # ═══════════════════════════════════════
    elif page == "📚 Book Advisor":
        st.title("📚 Financial Book Advisor")
        st.caption("Upload any financial book as PDF and ask questions personalized to your spending.")
        st.divider()

        pdf_file = st.file_uploader("Upload Financial Book (PDF)", type=["pdf"])
        if pdf_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_file.read())
                tmp_path = tmp.name
            with st.spinner("📖 Building RAG pipeline from your book..."):
                build_rag_from_pdf(tmp_path)
            os.unlink(tmp_path)
            st.success("✅ Book indexed! Ask your questions below.")

        st.divider()

        transactions = load_transactions(user_id)
        spending_context = ""
        if transactions:
            df = pd.DataFrame(transactions)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            total = df["amount"].sum()
            by_category = df.groupby("category")["amount"].sum().to_dict()
            spending_context = f"Total spent: ₹{total:.2f}. By category: {by_category}"

        book_question = st.text_input(
            "Ask the book",
            placeholder="e.g. How should I manage my food expenses?"
        )

        if st.button("📖 Ask Book", type="primary") and book_question:
            with st.spinner("🔍 Searching book for personalized advice..."):
                result = query_rag(book_question, spending_context)
            st.subheader("Answer:")
            st.markdown(f"""
            <div class="finance-card">
                {result["result"]}
            </div>
            """, unsafe_allow_html=True)

            if result.get("source_documents"):
                with st.expander("📄 Sources from the book"):
                    for doc in result["source_documents"]:
                        page_num = doc.metadata.get("page", "N/A")
                        st.caption(f"Page {page_num}: {doc.page_content[:200]}...")

    # ═══════════════════════════════════════
    # PAGE 5 — Dashboard
    # ═══════════════════════════════════════
    elif page == "📊 Dashboard":
        st.title("📊 Spending Dashboard")
        st.caption(f"Welcome back, {user['name']}. Here's your financial overview.")
        st.divider()

        transactions = load_transactions(user_id)

        if not transactions:
            st.info("No transactions yet. Upload screenshots or add expenses manually to see your dashboard.")
        else:
            df = pd.DataFrame(transactions)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

            total_spent = df["amount"].sum()
            category_summary = df.groupby("category")["amount"].sum()
            highest_category = category_summary.idxmax()
            avg_transaction = df["amount"].mean()

            # ── Metrics ──
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💸 Total Spent", f"₹{total_spent:.2f}")
            col2.metric("📦 Transactions", len(df))
            col3.metric("🏆 Top Category", highest_category)
            col4.metric("📊 Avg Transaction", f"₹{avg_transaction:.2f}")

            st.divider()

            # ── Charts ──
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Spending by Category")
                fig, ax = plt.subplots(facecolor="#1e2130")
                ax.set_facecolor("#1e2130")
                colors = ["#6c63ff", "#a78bfa", "#60a5fa",
                          "#34d399", "#fbbf24", "#f87171", "#e879f9"]
                wedges, texts, autotexts = ax.pie(
                    category_summary,
                    labels=category_summary.index,
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=colors[:len(category_summary)]
                )
                for text in texts:
                    text.set_color("#ffffff")
                for autotext in autotexts:
                    autotext.set_color("#ffffff")
                st.pyplot(fig)

            with col2:
                st.subheader("Category Breakdown")
                chart_data = pd.DataFrame({
                    "Amount (₹)": category_summary
                })
                st.bar_chart(chart_data)

            st.divider()

            # ── Payment Method Breakdown ──
            st.subheader("Payment Methods Used")
            payment_summary = df.groupby("payment_method")["amount"].sum()
            st.bar_chart(payment_summary)

            st.divider()

            # ── AI Advice ──
            st.subheader("🤖 AI Financial Advice")
            st.caption("Personalized advice based on your actual spending")
            if st.button("✨ Generate Advice", type="primary"):
                with st.spinner("Analyzing your spending patterns..."):
                    advice, savings = generate_financial_advice(
                        category_summary.to_dict(),
                        total_spent
                    )
                st.markdown(f"""
                <div class="finance-card">
                    {advice}
                </div>
                """, unsafe_allow_html=True)
                st.success(f"💡 Save 20% and you could keep ₹{savings:.2f} this period!")

            st.divider()

            # ── Transaction History ──
            st.subheader("Recent Transactions")
            st.dataframe(df, use_container_width=True)

# ─────────────────────────────────────────
# Router
# ─────────────────────────────────────────
if not st.session_state.logged_in:
    show_auth_page()
else:
    show_main_app()