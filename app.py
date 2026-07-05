import streamlit as st
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
import os
from datetime import date as date_type, timedelta

from ocr.ocr_engine import extract_transaction_from_image
from database.db import (
    create_table, save_transaction, load_transactions,
    delete_transaction, register_user, login_user, update_currency
)
from advice.advisor import generate_financial_advice, build_rag_from_pdf, query_rag
from advice.sql_agent import query_expenses
from utils.validators import validate_registration

from utils.currency import format_inr, get_usd_to_inr_rate, convert_to_inr
from ml.anomaly import detect_anomalies, suggest_category

create_table()

st.set_page_config(
    page_title="FinSage",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .finance-card {
        background-color: #1e2130;
        border: 1px solid #3d3d5a;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        color: #ffffff;
        line-height: 1.8;
    }
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

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

if "usd_rate" not in st.session_state:
    st.session_state.usd_rate = get_usd_to_inr_rate()

def show_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="logo-text">💰 FinSage</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="logo-subtitle">Your AI-powered personal finance advisor</div>',
            unsafe_allow_html=True
        )

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            st.markdown("### Welcome back")
            username_login = st.text_input(
                "Username", key="login_username",
                placeholder="Enter your username"
            )
            password_login = st.text_input(
                "Password", type="password", key="login_password",
                placeholder="Enter your password"
            )
            if st.button("Login", type="primary", key="login_btn", use_container_width=True):
                if username_login and password_login:
                    success, user, message = login_user(username_login, password_login)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.session_state.currency = user.get("currency", "INR")
                        st.success(f"Welcome back, {user['name']}!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please fill in all fields.")

        with tab2:
            st.markdown("### Create your account")
            username_reg = st.text_input(
                "Username", key="reg_username",
                placeholder="Letters, numbers, underscores only"
            )
            email_reg = st.text_input(
                "Email", key="reg_email",
                placeholder="you@example.com"
            )
            password_reg = st.text_input(
                "Password", type="password", key="reg_password",
                placeholder="Min 6 chars, must include a number"
            )
            password_confirm = st.text_input(
                "Confirm Password", type="password", key="reg_confirm",
                placeholder="Repeat your password"
            )
            if st.button("Create Account", type="primary", key="reg_btn", use_container_width=True):
                valid, errors = validate_registration(
                    username_reg, email_reg, password_reg, password_confirm
                )
                if not valid:
                    for error in errors:
                        st.error(error)
                else:
                    success, message = register_user(
                        username_reg, email_reg, password_reg
                    )
                    if success:
                        st.success("✅ Account created! Please login.")
                    else:
                        st.error(message)


def show_main_app():
    user = st.session_state.user
    user_id = user["id"]
    rate = st.session_state.usd_rate

    def fmt(amount):
        return format_inr(amount)

    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.divider()

        page = st.radio("Navigate", [
            "📸 Upload & Extract",
            "✏️ Manual Entry",
            "💬 Ask Your Expenses",
            "📚 Book Advisor",
            "📊 Dashboard"
        ])

        

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

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

                if transaction.get("merchant"):
                    suggested_cat = suggest_category(transaction["merchant"])
                    if transaction.get("category") in [None, "Others"]:
                        transaction["category"] = suggested_cat

                st.subheader("✅ Extracted Details")
                st.caption("Review and correct if needed")

                transaction["merchant"] = st.text_input(
                    "Merchant",
                    value=transaction.get("merchant") or ""
                )

                col_curr, col_amt = st.columns([1, 2])
                with col_curr:
                    txn_currency = st.selectbox("Currency", ["INR", "USD"], key="upload_currency")
                with col_amt:
                    entered_amount = st.number_input(
                        f"Amount ({txn_currency})",
                        value=float(transaction.get("amount") or 0.0),
                        min_value=0.0
                    )

                inr_amount = convert_to_inr(entered_amount, txn_currency, rate)
                if txn_currency == "USD":
                    st.caption(f"≈ ₹{inr_amount:,.2f} (at ₹{rate:.2f}/USD)")

                transaction["amount"] = inr_amount
                transaction["original_amount"] = entered_amount
                transaction["original_currency"] = txn_currency
                transaction["exchange_rate"] = rate if txn_currency == "USD" else 1.0

                transaction["date"] = st.date_input(
                    "Transaction Date", value=date_type.today()
                ).isoformat()

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
    elif page == "✏️ Manual Entry":
        st.title("✏️ Add Expense Manually")
        st.caption("No screenshot? Add your expense directly.")
        st.divider()

        with st.form("manual_entry_form"):
            col1, col2 = st.columns(2)
            with col1:
                merchant = st.text_input(
                    "Merchant / Shop Name",
                    placeholder="e.g. Dominos, DMart, Ola, Netflix US"
                )
                col_curr, col_amt = st.columns([1, 2])
                with col_curr:
                    txn_currency = st.selectbox("Currency", ["INR", "USD"], key="manual_currency")
                with col_amt:
                    amount = st.number_input(f"Amount ({txn_currency})", min_value=0.0, step=1.0)

                if txn_currency == "USD" and amount > 0:
                    inr_preview = convert_to_inr(amount, "USD", rate)
                    st.caption(f"≈ ₹{inr_preview:,.2f} (at ₹{rate:.2f}/USD)")

                selected_date = st.date_input("Date", value=date_type.today())
            with col2:
                categories = ["Food", "Shopping", "Transport",
                              "Entertainment", "Utilities", "Healthcare", "Others"]

                if "last_merchant_seen" not in st.session_state:
                    st.session_state.last_merchant_seen = ""
                if "manual_category_index" not in st.session_state:
                    st.session_state.manual_category_index = categories.index("Others")

                merchant_changed = merchant != st.session_state.last_merchant_seen

                if merchant_changed:
                    st.session_state.last_merchant_seen = merchant
                    if merchant:
                        # New merchant typed in → auto-suggest
                        suggested = suggest_category(merchant)
                        st.session_state.manual_category_index = categories.index(suggested)
                    else:
                        # Merchant cleared → reset to Others
                        st.session_state.manual_category_index = categories.index("Others")

                category = st.selectbox(
                    "Category",
                    categories,
                    index=st.session_state.manual_category_index,
                    key="manual_entry_category_select"
                )
                # Save whatever the user currently has selected (manual or auto)
                st.session_state.manual_category_index = categories.index(category)
                payment_method = st.selectbox(
                    "Payment Method",
                    ["UPI", "Credit Card", "Debit Card",
                     "Net Banking", "Cash", "Unknown"]
                )

            submitted = st.form_submit_button("💾 Save Expense", type="primary")
            if submitted:
                if amount > 0:
                    inr_amount = convert_to_inr(amount, txn_currency, rate)
                    save_transaction({
                        "merchant": merchant if merchant else "Unknown Merchant",
                        "amount": inr_amount,
                        "original_amount": amount,
                        "original_currency": txn_currency,
                        "exchange_rate": rate if txn_currency == "USD" else 1.0,
                        "date": selected_date.isoformat(),
                        "category": category,
                        "payment_method": payment_method
                    }, user_id)
                    st.success(f"✅ {fmt(inr_amount)} expense saved!")
                    st.balloons()
                else:
                    st.error("Amount must be greater than 0.")
      

            

    elif page == "💬 Ask Your Expenses":
        st.title("💬 Ask About Your Spending")
        st.caption("Powered by LangChain SQL Agent")
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
            with st.spinner("🤖 Thinking..."):
                answer = query_expenses(question)
            st.subheader("Answer:")
            st.markdown(
                f'<div class="finance-card">{answer}</div>',
                unsafe_allow_html=True
            )

        st.divider()

        st.subheader("📜 Transaction History")
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            filter_type = st.selectbox(
                "Filter",
                ["All", "Today", "This Week", "This Month", "Custom"]
            )
        start_date = end_date = None
        if filter_type == "Custom":
            with col2:
                start_date = st.date_input("From", value=date_type.today() - timedelta(days=30))
            with col3:
                end_date = st.date_input("To", value=date_type.today())

        transactions = load_transactions(user_id, filter_type, start_date, end_date)

        if transactions:
            anomalous_ids = detect_anomalies(transactions)

            df = pd.DataFrame(transactions)
            df["amount_display"] = df["amount"].apply(lambda x: fmt(x))
            if anomalous_ids:
                df["⚠️"] = df["id"].apply(
                    lambda x: "⚠️ Unusual" if x in anomalous_ids else ""
                )

            display_cols = ["merchant", "amount_display", "date",
                            "category", "payment_method"]
            if anomalous_ids:
                display_cols.append("⚠️")

            st.dataframe(df[display_cols], use_container_width=True)

            if anomalous_ids:
                st.warning(f"⚠️ {len(anomalous_ids)} transaction(s) flagged as unusually high for their category.")

            st.subheader("🗑️ Delete a Transaction")
            transaction_options = {
                f"#{t['id']} — {t['merchant']} — {fmt(t['amount'])} — {t['date']}": t['id']
                for t in transactions
            }
            selected = st.selectbox(
                "Select transaction to delete",
                options=list(transaction_options.keys())
            )
            if st.button("🗑️ Delete Selected", type="primary"):
                delete_transaction(transaction_options[selected], user_id)
                st.success("✅ Deleted!")
                st.rerun()
        else:
            st.info("No transactions found for the selected period.")

    elif page == "📚 Book Advisor":
        st.title("📚 Financial Book Advisor")
        st.caption("Upload any financial book as PDF and get personalized advice.")
        st.divider()

        pdf_file = st.file_uploader("Upload Financial Book (PDF)", type=["pdf"])
        if pdf_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_file.read())
                tmp_path = tmp.name
            with st.spinner("📖 Building RAG pipeline..."):
                build_rag_from_pdf(tmp_path)
            os.unlink(tmp_path)
            st.success("✅ Book indexed! Ask questions below.")

        st.divider()

        transactions = load_transactions(user_id)
        spending_context = ""
        if transactions:
            df = pd.DataFrame(transactions)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            total = df["amount"].sum()
            by_category = df.groupby("category")["amount"].sum().to_dict()
            spending_context = (
                f"Total spent: ₹{total:.2f}. "
                f"By category: {by_category}"
            )

        book_question = st.text_input(
            "Ask the book",
            placeholder="e.g. How should I manage my food expenses?"
        )

        if st.button("📖 Ask Book", type="primary") and book_question:
            with st.spinner("🔍 Searching book..."):
                result = query_rag(book_question, spending_context)
            st.subheader("Answer:")
            st.markdown(
                f'<div class="finance-card">{result["result"]}</div>',
                unsafe_allow_html=True
            )
            if result.get("source_documents"):
                with st.expander("📄 Sources"):
                    for doc in result["source_documents"]:
                        page_num = doc.metadata.get("page", "N/A")
                        st.caption(f"Page {page_num}: {doc.page_content[:200]}...")

    elif page == "📊 Dashboard":
        st.title("📊 Spending Dashboard")
        st.caption(f"Welcome back, {user['name']}. Currency:  All amounts in INR (₹)")
        st.divider()

        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            dash_filter = st.selectbox(
                "Period",
                ["All", "Today", "This Week", "This Month", "Custom"],
                key="dash_filter"
            )
        dash_start = dash_end = None
        if dash_filter == "Custom":
            with col2:
                dash_start = st.date_input(
                    "From", value=date_type.today() - timedelta(days=30),
                    key="dash_start"
                )
            with col3:
                dash_end = st.date_input(
                    "To", value=date_type.today(),
                    key="dash_end"
                )

        transactions = load_transactions(user_id, dash_filter, dash_start, dash_end)

        if not transactions:
            st.info("No transactions for this period.")
        else:
            df = pd.DataFrame(transactions)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            df["transaction_date"] = pd.to_datetime(df["date"])

            total_spent = df["amount"].sum()
            category_summary = df.groupby("category")["amount"].sum()
            highest_category = category_summary.idxmax()
            avg_transaction = df["amount"].mean()

            anomalous_ids = detect_anomalies(transactions)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💸 Total Spent", fmt(total_spent))
            col2.metric("📦 Transactions", len(df))
            col3.metric("🏆 Top Category", highest_category)
            col4.metric("📊 Avg Transaction", fmt(avg_transaction))

            if anomalous_ids:
                st.warning(
                    f"⚠️ {len(anomalous_ids)} unusual transaction(s) detected. "
                    f"Check 'Ask Your Expenses' for details."
                )

            st.divider()

            col1, col2 = st.columns(2)
            colors = ["#6c63ff", "#a78bfa", "#60a5fa",
                      "#34d399", "#fbbf24", "#f87171", "#e879f9"]

            with col1:
                st.subheader("Spending by Category")
                fig, ax = plt.subplots(facecolor="#1e2130")
                ax.set_facecolor("#1e2130")
                wedges, texts, autotexts = ax.pie(
                    category_summary,
                    labels=category_summary.index,
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=colors[:len(category_summary)]
                )
                for t in texts:
                    t.set_color("#ffffff")
                for t in autotexts:
                    t.set_color("#ffffff")
                st.pyplot(fig)

            with col2:
                st.subheader("Category Breakdown")
                st.bar_chart(category_summary)

            st.divider()

            st.subheader("📈 Spending Over Time")
            st.caption("Shows your total spending per day — add more transactions across different dates to see trends")
            daily = df.groupby("transaction_date")["amount"].sum().reset_index()
            if len(daily) >= 2:
                daily.columns = ["Date", "Amount (₹)"]
                st.line_chart(daily.set_index("Date"))
            else:
                st.info("Add transactions across at least 2 different dates to see your spending trend.")
            

            st.subheader("Payment Methods")
            payment_summary = df.groupby("payment_method")["amount"].sum()
             
            st.bar_chart(payment_summary)

            st.divider()

            st.subheader("🤖 AI Financial Advice")
            st.caption("Dynamic advice based on your spending patterns vs healthy benchmarks")
            if st.button("✨ Generate Advice", type="primary"):
                with st.spinner("Analyzing your spending patterns..."):
                    advice, potential_savings = generate_financial_advice(
                        category_summary.to_dict(),
                        total_spent
                    )
                st.markdown(
                    f'<div class="finance-card">{advice}</div>',
                    unsafe_allow_html=True
                )
                savings_display = fmt(potential_savings)
                st.success(
                    f"💡 Estimated monthly savings potential: {savings_display} "
                    f"based on your actual spending patterns"
                )

            st.divider()

            st.subheader("Recent Transactions")
            df["amount_display"] = df["amount"].apply(fmt)
            if anomalous_ids:
                df["⚠️"] = df["id"].apply(
                    lambda x: "⚠️ Unusual" if x in anomalous_ids else ""
                )
            display_cols = ["merchant", "amount_display", "date", "category", "payment_method"]
            if anomalous_ids:
                display_cols.append("⚠️")
            st.dataframe(df[display_cols], use_container_width=True)


if not st.session_state.logged_in:
    show_auth_page()
else:
    show_main_app()