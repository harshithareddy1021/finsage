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
    delete_transaction, register_user, login_user, update_currency,
    save_income, get_income, add_emi, get_active_emis, get_all_emis,
    update_emi_progress, delete_emi, get_total_emi,
    add_goal, get_active_goals, complete_goal, delete_goal,
    get_disposable_income
)
from advice.advisor import generate_financial_advice, build_rag_from_pdf, query_rag, has_book_indexed
from advice.agent import ask_finsage
from advice.intelligence import generate_transaction_insight
from utils.validators import validate_registration
from utils.currency import format_inr, get_usd_to_inr_rate, convert_to_inr
from ml.anomaly import detect_anomalies, suggest_category

# ─────────────────────────────────────────
# Init
# ─────────────────────────────────────────
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

# ─────────────────────────────────────────
# Session State
# ─────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "usd_rate" not in st.session_state:
    st.session_state.usd_rate = get_usd_to_inr_rate()


# ═══════════════════════════════════════════
# AUTH PAGE
# ═══════════════════════════════════════════
def show_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="logo-text">💰 FinSage</div>',
                    unsafe_allow_html=True)
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
            if st.button("Login", type="primary", key="login_btn",
                         use_container_width=True):
                if username_login and password_login:
                    success, user, message = login_user(
                        username_login, password_login
                    )
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user = user
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
            if st.button("Create Account", type="primary", key="reg_btn",
                         use_container_width=True):
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


# ═══════════════════════════════════════════
# INSIGHT CARD
# ═══════════════════════════════════════════
def show_insight_card(insight: dict):
    st.markdown("---")
    st.markdown("### 🧠 FinSage Insight")

    st.markdown(
        f'<div class="finance-card">{insight["llm_insight"]}</div>',
        unsafe_allow_html=True
    )

    if insight["is_anomalous"] and insight["avg_amount"]:
        st.warning(
            f"⚠️ Unusual amount — ₹{insight['amount']:,.0f} is significantly "
            f"higher than your average {insight['category']} spend of "
            f"₹{insight['avg_amount']:,.0f}."
        )

    col1, col2, col3 = st.columns(3)
    col1.metric(
        f"This transaction",
        f"₹{insight['amount']:,.0f}"
    )
    col2.metric(
        f"Monthly {insight['category']}",
        f"₹{insight['monthly_category_total']:,.0f}",
        delta=f"{insight['actual_pct']:.1f}% of spending"
    )
    col3.metric(
        "Healthy benchmark",
        f"{insight['benchmark_pct']:.0f}%",
        delta=f"{insight['actual_pct'] - insight['benchmark_pct']:+.1f}%",
        delta_color="inverse"
    )

    if insight.get("book_insight"):
        st.info(f"📚 **From your book:** {insight['book_insight']}")

    if insight.get("goal_alerts"):
        for alert in insight["goal_alerts"]:
            if "✅" in alert:
                st.success(alert)
            else:
                st.warning(alert)


# ═══════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════
def show_main_app():
    user = st.session_state.user
    user_id = user["id"]
    rate = st.session_state.usd_rate

    def fmt(amount):
        return format_inr(amount)

    # ── Sidebar ──────────────────────────────
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.divider()

        page = st.radio("Navigate", [
            "📸 Upload & Extract",
            "✏️ Manual Entry",
            "💰 Income & EMI",
            "🎯 Goals",
            "🤖 Ask FinSage",
            "📚 Book Advisor",
            "📊 Dashboard"
        ])

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
                transaction["amount"] = st.number_input(
                    "Amount",
                    value=float(transaction.get("amount") or 0.0),
                    min_value=0.0
                )
                transaction["date"] = st.date_input(
                    "Transaction Date",
                    value=date_type.today()
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

                col_curr, col_amt = st.columns([1, 2])
                with col_curr:
                    txn_currency = st.selectbox(
                        "Currency", ["INR", "USD"], key="upload_currency"
                    )
                with col_amt:
                    entered_amount = st.number_input(
                        f"Amount ({txn_currency})",
                        value=float(transaction.get("amount") or 0.0),
                        min_value=0.0,
                        key="upload_amount"
                    )

                inr_amount = convert_to_inr(entered_amount, txn_currency, rate)
                if txn_currency == "USD":
                    st.caption(f"≈ ₹{inr_amount:,.2f} (at ₹{rate:.2f}/USD)")

                transaction["amount"] = inr_amount
                transaction["original_amount"] = entered_amount
                transaction["original_currency"] = txn_currency
                transaction["exchange_rate"] = rate if txn_currency == "USD" else 1.0

                if st.button("💾 Save Transaction", type="primary"):
                    if transaction["amount"] > 0:
                        if not transaction["merchant"]:
                            transaction["merchant"] = "Unknown Merchant"
                        save_transaction(transaction, user_id)
                        st.success("✅ Transaction saved!")

                        with st.spinner("🧠 FinSage is analyzing..."):
                            all_transactions = load_transactions(user_id)
                            has_book = has_book_indexed()
                            insight = generate_transaction_insight(
                                transaction,
                                all_transactions,
                                has_book,
                                user_id
                            )
                        show_insight_card(insight)
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
                    placeholder="e.g. Dominos, DMart, Ola, Netflix US"
                )
                col_curr, col_amt = st.columns([1, 2])
                with col_curr:
                    txn_currency = st.selectbox(
                        "Currency", ["INR", "USD"], key="manual_currency"
                    )
                with col_amt:
                    amount = st.number_input(
                        f"Amount ({txn_currency})",
                        min_value=0.0, step=1.0
                    )
                if txn_currency == "USD" and amount > 0:
                    inr_preview = convert_to_inr(amount, "USD", rate)
                    st.caption(f"≈ ₹{inr_preview:,.2f} (at ₹{rate:.2f}/USD)")
                selected_date = st.date_input("Date", value=date_type.today())

            with col2:
                categories = ["Food", "Shopping", "Transport",
                              "Entertainment", "Utilities", "Healthcare", "Others"]
                category = st.selectbox(
                    "Category (leave as Others to auto-detect)",
                    categories,
                    index=categories.index("Others")
                )
                payment_method = st.selectbox(
                    "Payment Method",
                    ["UPI", "Credit Card", "Debit Card",
                     "Net Banking", "Cash", "Unknown"]
                )

            submitted = st.form_submit_button("💾 Save Expense", type="primary")
            if submitted:
                if amount > 0:
                    final_category = category
                    if category == "Others" and merchant:
                        suggested = suggest_category(merchant)
                        if suggested != "Others":
                            final_category = suggested

                    inr_amount = convert_to_inr(amount, txn_currency, rate)
                    saved_transaction = {
                        "merchant": merchant if merchant else "Unknown Merchant",
                        "amount": inr_amount,
                        "original_amount": amount,
                        "original_currency": txn_currency,
                        "exchange_rate": rate if txn_currency == "USD" else 1.0,
                        "date": selected_date.isoformat(),
                        "category": final_category,
                        "payment_method": payment_method
                    }
                    save_transaction(saved_transaction, user_id)
                    st.success(f"✅ {fmt(inr_amount)} saved as {final_category}!")

                    with st.spinner("🧠 FinSage is analyzing..."):
                        all_transactions = load_transactions(user_id)
                        has_book = has_book_indexed()
                        insight = generate_transaction_insight(
                            saved_transaction,
                            all_transactions,
                            has_book,
                            user_id
                        )
                    show_insight_card(insight)
                else:
                    st.error("Amount must be greater than 0.")

    # ═══════════════════════════════════════
    # PAGE 3 — Income & EMI
    # ═══════════════════════════════════════
    elif page == "💰 Income & EMI":
        st.title("💰 Income & EMI Manager")
        st.caption("Track your salary and loan obligations.")
        st.divider()

        completed_emis = update_emi_progress(user_id)
        if completed_emis:
            for name in completed_emis:
                st.success(f"🎉 Your {name} EMI is now complete!")

        st.subheader("💵 Monthly Salary")
        current_salary = get_income(user_id)
        if current_salary > 0:
            st.info(f"Current salary: ₹{current_salary:,.0f}/month")

        with st.form("income_form"):
            new_salary = st.number_input(
                "Enter your monthly salary (₹)",
                min_value=0.0,
                value=float(current_salary) if current_salary > 0 else 0.0,
                step=1000.0
            )
            if st.form_submit_button("💾 Save Salary", type="primary"):
                if new_salary > 0:
                    save_income(user_id, new_salary)
                    st.success(f"✅ Salary saved: ₹{new_salary:,.0f}/month")
                    st.rerun()
                else:
                    st.error("Please enter a valid salary.")

        st.divider()

        data = get_disposable_income(user_id)
        if data["salary"] > 0:
            st.subheader("📊 Monthly Overview")
            col1, col2, col3 = st.columns(3)
            col1.metric("Monthly Salary", f"₹{data['salary']:,.0f}")
            col2.metric("Total EMIs", f"₹{data['total_emi']:,.0f}",
                        delta=f"-₹{data['total_emi']:,.0f}",
                        delta_color="inverse")
            col3.metric("Disposable Income", f"₹{data['disposable']:,.0f}")

        st.divider()
        st.subheader("🏦 EMI / Loan Payments")

        with st.form("emi_form"):
            st.markdown("**Add New EMI**")
            col1, col2 = st.columns(2)
            with col1:
                emi_name = st.text_input(
                    "Loan Name",
                    placeholder="e.g. Home Loan, Car Loan"
                )
                emi_amount = st.number_input(
                    "Monthly EMI (₹)", min_value=0.0, step=100.0
                )
            with col2:
                emi_tenure = st.number_input(
                    "Total Tenure (months)",
                    min_value=1, max_value=360, value=12
                )
                emi_start = st.date_input(
                    "EMI Start Date", value=date_type.today()
                )

            if st.form_submit_button("➕ Add EMI", type="primary"):
                if emi_name and emi_amount > 0:
                    add_emi(user_id, emi_name, emi_amount,
                            emi_tenure, emi_start.isoformat())
                    st.success(f"✅ {emi_name} EMI added!")
                    st.rerun()
                else:
                    st.error("Please fill all fields.")

        all_emis = get_all_emis(user_id)
        if all_emis:
            st.markdown("**Your EMIs**")
            for emi in all_emis:
                with st.expander(
                    f"{'✅' if emi['status'] == 'completed' else '🔄'} "
                    f"{emi['name']} — ₹{emi['amount']:,.0f}/month"
                ):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Monthly", f"₹{emi['amount']:,.0f}")
                    col2.metric("Remaining", f"{emi['months_remaining']} months")
                    col3.metric("Tenure", f"{emi['tenure_months']} months")

                    progress = min(
                        emi["months_paid"] / emi["tenure_months"], 1.0
                    )
                    st.progress(
                        progress,
                        text=f"{emi['months_paid']}/{emi['tenure_months']} months paid"
                    )

                    if emi["status"] == "active":
                        if st.button(
                            f"🗑️ Remove", key=f"del_emi_{emi['id']}"
                        ):
                            delete_emi(emi["id"], user_id)
                            st.rerun()
        else:
            st.info("No EMIs added yet.")

    # ═══════════════════════════════════════
    # PAGE 4 — Goals
    # ═══════════════════════════════════════
    elif page == "🎯 Goals":
        st.title("🎯 Savings Goals")
        st.caption("Set financial goals and track your progress automatically.")
        st.divider()

        with st.form("goal_form"):
            col1, col2 = st.columns(2)
            with col1:
                goal_name = st.text_input(
                    "What are you saving for?",
                    placeholder="e.g. Air Fryer, Goa Trip, New Phone"
                )
                goal_amount = st.number_input(
                    "Target Amount (₹)", min_value=0.0, step=100.0
                )
            with col2:
                goal_date = st.date_input(
                    "Target Date", value=date_type.today()
                )

            if st.form_submit_button("🎯 Set Goal", type="primary"):
                if goal_name and goal_amount > 0:
                    add_goal(user_id, goal_name, goal_amount,
                             goal_date.isoformat())
                    st.success(f"✅ Goal: {goal_name} — ₹{goal_amount:,.0f}")
                    st.rerun()
                else:
                    st.error("Please fill all fields.")

        st.divider()

        goals = get_active_goals(user_id)
        data = get_disposable_income(user_id)
        transactions = load_transactions(user_id, "This Month")
        spent_this_month = sum(t["amount"] for t in transactions)
        saved_this_month = max(0, data["disposable"] - spent_this_month)

        if data["salary"] > 0:
            st.caption(
                f"Disposable: ₹{data['disposable']:,.0f} — "
                f"Spent: ₹{spent_this_month:,.0f} — "
                f"Saved: ₹{saved_this_month:,.0f}"
            )

        if goals:
            st.subheader("📊 Goal Progress")
            for goal in goals:
                today = date_type.today()
                st.markdown(f"### 🎯 {goal['name']}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Target", f"₹{goal['target_amount']:,.0f}")

                if goal["target_date"]:
                    target_date = date_type.fromisoformat(goal["target_date"])
                    days_left = (target_date - today).days
                    months_left = max(1, days_left // 30)
                    needed_per_month = goal["target_amount"] / months_left
                    col2.metric("Days Left", f"{max(0, days_left)}")
                    col3.metric("Need/Month", f"₹{needed_per_month:,.0f}")

                    if saved_this_month > 0:
                        progress = min(
                            saved_this_month / needed_per_month, 1.0
                        )
                        st.progress(
                            progress,
                            text=f"Saving ₹{saved_this_month:,.0f} of "
                                 f"₹{needed_per_month:,.0f} needed/month"
                        )

                    if days_left < 0:
                        st.error("⏰ Target date has passed!")
                    elif data["salary"] == 0:
                        st.warning(
                            "⚠️ Add your salary in Income & EMI page "
                            "for accurate goal tracking."
                        )
                    elif saved_this_month >= needed_per_month:
                        st.success(
                            f"✅ On track! Saving ₹{saved_this_month:,.0f}/month — "
                            f"goal reachable in {months_left} month(s)."
                        )
                    else:
                        shortfall = needed_per_month - saved_this_month
                        st.warning(
                            f"⚠️ Need ₹{needed_per_month:,.0f}/month, "
                            f"saving ₹{saved_this_month:,.0f}. "
                            f"Cut ₹{shortfall:,.0f} more to stay on track."
                        )

                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("✅ Complete", key=f"complete_{goal['id']}"):
                        complete_goal(goal["id"], user_id)
                        st.success(f"🎉 {goal['name']} completed!")
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"delete_{goal['id']}"):
                        delete_goal(goal["id"], user_id)
                        st.rerun()
                st.divider()
        else:
            st.info("No active goals. Set your first goal above!")

    # ═══════════════════════════════════════
    # PAGE 5 — Ask FinSage (ReAct Agent)
    # ═══════════════════════════════════════
    elif page == "🤖 Ask FinSage":
        st.title("🤖 Ask FinSage")
        st.caption("Powered by LangChain ReAct Agent with 6 financial tools")
        st.divider()

        st.info("""
        **Ask anything about your finances:**
        - Can I afford to buy a car next month?
        - How much did I spend on food this month?
        - Am I on track for my Air Fryer goal?
        - How much can I safely spend this weekend?
        - What should I cut to save faster?
        - What does my book say about saving money?
        - How long until I can afford a trip to Goa?
        """)

        question = st.text_input(
            "Ask FinSage anything",
            placeholder="e.g. Can I afford a new phone next month?"
        )

        if st.button("🤖 Ask", type="primary") and question:
            with st.spinner("🧠 FinSage Agent is analyzing your finances..."):
                answer = ask_finsage(question, user_id)
            st.subheader("FinSage says:")
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
                start_date = st.date_input(
                    "From",
                    value=date_type.today() - timedelta(days=30)
                )
            with col3:
                end_date = st.date_input("To", value=date_type.today())

        transactions = load_transactions(
            user_id, filter_type, start_date, end_date
        )

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
                st.warning(
                    f"⚠️ {len(anomalous_ids)} transaction(s) flagged as unusual."
                )

            st.subheader("🗑️ Delete a Transaction")
            transaction_options = {
                f"#{t['id']} — {t['merchant']} — "
                f"{fmt(t['amount'])} — {t['date']}": t['id']
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

    # ═══════════════════════════════════════
    # PAGE 6 — Book Advisor
    # ═══════════════════════════════════════
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
                        st.caption(
                            f"Page {page_num}: {doc.page_content[:200]}..."
                        )

    # ═══════════════════════════════════════
    # PAGE 7 — Dashboard
    # ═══════════════════════════════════════
    elif page == "📊 Dashboard":
        st.title("📊 Spending Dashboard")
        st.caption(f"Welcome back, {user['name']}. All amounts in INR (₹)")
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
                    "From",
                    value=date_type.today() - timedelta(days=30),
                    key="dash_start"
                )
            with col3:
                dash_end = st.date_input(
                    "To", value=date_type.today(), key="dash_end"
                )

        transactions = load_transactions(
            user_id, dash_filter, dash_start, dash_end
        )

        # Income overview at top
        disp_data = get_disposable_income(user_id)
        if disp_data["salary"] > 0:
            st.subheader("💰 Financial Overview")
            col1, col2, col3 = st.columns(3)
            col1.metric("Monthly Salary", f"₹{disp_data['salary']:,.0f}")
            col2.metric("EMI Obligations", f"₹{disp_data['total_emi']:,.0f}")
            col3.metric("Disposable Income", f"₹{disp_data['disposable']:,.0f}")
            st.divider()

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

            if disp_data["salary"] > 0:
                remaining = disp_data["disposable"] - total_spent
                st.metric(
                    "💚 Remaining This Month",
                    fmt(max(0, remaining)),
                    delta=f"{'Surplus' if remaining > 0 else 'Deficit'}"
                )

            if anomalous_ids:
                st.warning(
                    f"⚠️ {len(anomalous_ids)} unusual transaction(s) detected."
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
            st.caption("Total spending per day")
            daily = df.groupby("transaction_date")["amount"].sum().reset_index()
            if len(daily) >= 2:
                daily.columns = ["Date", "Amount (₹)"]
                st.line_chart(daily.set_index("Date"))
            else:
                st.info("Add transactions across 2+ dates to see trend.")

            st.divider()

            st.subheader("Payment Methods")
            payment_summary = df.groupby("payment_method")["amount"].sum()
            st.bar_chart(payment_summary)

            st.divider()

            st.subheader("🤖 AI Financial Advice")
            st.caption("Dynamic advice based on your spending vs benchmarks")
            if st.button("✨ Generate Advice", type="primary"):
                with st.spinner("Analyzing your spending..."):
                    advice, potential_savings = generate_financial_advice(
                        category_summary.to_dict(),
                        total_spent
                    )
                st.markdown(
                    f'<div class="finance-card">{advice}</div>',
                    unsafe_allow_html=True
                )
                st.success(
                    f"💡 Estimated savings potential: {fmt(potential_savings)} "
                    f"based on your actual spending patterns"
                )

            st.divider()

            st.subheader("Recent Transactions")
            df["amount_display"] = df["amount"].apply(fmt)
            if anomalous_ids:
                df["⚠️"] = df["id"].apply(
                    lambda x: "⚠️ Unusual" if x in anomalous_ids else ""
                )
            display_cols = ["merchant", "amount_display", "date",
                            "category", "payment_method"]
            if anomalous_ids:
                display_cols.append("⚠️")
            st.dataframe(df[display_cols], use_container_width=True)


# ─────────────────────────────────────────
# Router
# ─────────────────────────────────────────
if not st.session_state.logged_in:
    show_auth_page()
else:
    show_main_app()