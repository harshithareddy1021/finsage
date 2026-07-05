from langchain_groq import ChatGroq
from utils.helpers import GROQ_API_KEY
from ml.anomaly import detect_anomalies
from advice.advisor import CATEGORY_BENCHMARKS, load_existing_rag
import os
import numpy as np
from collections import defaultdict

def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.4
    )

def generate_transaction_insight(
    new_transaction: dict,
    all_transactions: list,
    has_book: bool = False,
    user_id: int = 0
) -> dict:
    from datetime import date
    today = date.today()
    month_start = today.replace(day=1).isoformat()

    category = new_transaction.get("category", "Others")
    amount = new_transaction.get("amount", 0)
    merchant = new_transaction.get("merchant", "Unknown")

    # ── Layer 1: Monthly stats ────────────────────────────────────
    monthly_same_category = [
        t for t in all_transactions
        if t.get("category") == category
        and t.get("date", "") >= month_start
    ]
    monthly_category_total = sum(
        t.get("amount", 0) for t in monthly_same_category
    )
    monthly_total = sum(
        t.get("amount", 0) for t in all_transactions
        if t.get("date", "") >= month_start
    )

    # ── Layer 2: Benchmark analysis ───────────────────────────────
    benchmark = CATEGORY_BENCHMARKS.get(category, 0.10)
    benchmark_pct = benchmark * 100
    actual_pct = (
        (monthly_category_total / monthly_total * 100)
        if monthly_total > 0 else 0
    )
    is_over_benchmark = actual_pct > (benchmark_pct + 5)

    # ── Layer 3: Anomaly detection ────────────────────────────────
    is_anomalous = False
    avg_amount = None
    if len(monthly_same_category) >= 3:
        amounts = [t.get("amount", 0) for t in monthly_same_category]
        mean = np.mean(amounts)
        std = np.std(amounts)
        avg_amount = mean
        if std > 0:
            z_score = abs((amount - mean) / std)
            is_anomalous = z_score > 2.0

    # ── Layer 4: Book context ─────────────────────────────────────
    book_insight = None
    if has_book:
        try:
            chain = load_existing_rag()
            if chain:
                question = (
                    f"What is one specific tip about {category} spending? "
                    f"Keep it to 1-2 sentences."
                )
                result = chain.invoke({"query": question})
                book_insight = result.get("result", "").strip()
                if len(book_insight) > 200:
                    book_insight = book_insight[:200] + "..."
        except Exception:
            book_insight = None

    # ── Layer 5: Goal progress check ──────────────────────────────
    goal_alerts = []
    if user_id > 0:
        try:
            from database.db import get_active_goals, get_disposable_income
            goals = get_active_goals(user_id)
            if goals:
                disp_data = get_disposable_income(user_id)
                spent = sum(
                    t.get("amount", 0) for t in all_transactions
                    if t.get("date", "") >= month_start
                )
                saved = max(0, disp_data["disposable"] - spent)
                for goal in goals:
                    if goal.get("target_date"):
                        target = date.fromisoformat(goal["target_date"])
                        days_left = (target - today).days
                        months_left = max(1, days_left // 30)
                        needed = goal["target_amount"] / months_left
                        if saved < needed:
                            shortfall = needed - saved
                            goal_alerts.append(
                                f"⚠️ Goal '{goal['name']}' needs "
                                f"₹{needed:,.0f}/month but you're saving "
                                f"₹{saved:,.0f}. Cut ₹{shortfall:,.0f} "
                                f"more to stay on track."
                            )
                        else:
                            goal_alerts.append(
                                f"✅ On track for '{goal['name']}' goal!"
                            )
        except Exception:
            goal_alerts = []

    # ── Layer 6: Unified LLM insight ──────────────────────────────
    prompt_parts = [
        f"User just saved: ₹{amount} at {merchant} ({category}).",
        f"{category} spending this month: ₹{monthly_category_total:.0f} "
        f"({actual_pct:.1f}% of ₹{monthly_total:.0f} total).",
        f"Healthy benchmark for {category}: {benchmark_pct:.0f}%.",
        f"Number of {category} transactions this month: "
        f"{len(monthly_same_category)}.",
    ]

    if is_anomalous and avg_amount:
        prompt_parts.append(
            f"This ₹{amount} is unusually high vs average "
            f"₹{avg_amount:.0f} for {category}."
        )
    if is_over_benchmark:
        prompt_parts.append(
            f"They are {actual_pct - benchmark_pct:.1f}% over "
            f"the healthy benchmark."
        )

    prompt_parts.append(
        "Write ONE specific insight in 2-3 sentences. "
        "Reference actual numbers. "
        "Do not start with 'Great' or 'Excellent'. "
        "Speak like a smart financial friend."
    )

    llm = get_llm()
    response = llm.invoke("\n".join(prompt_parts))
    llm_insight = response.content.strip()

    return {
        "llm_insight": llm_insight,
        "is_anomalous": is_anomalous,
        "avg_amount": avg_amount,
        "is_over_benchmark": is_over_benchmark,
        "actual_pct": actual_pct,
        "benchmark_pct": benchmark_pct,
        "monthly_category_total": monthly_category_total,
        "monthly_total": monthly_total,
        "monthly_count": len(monthly_same_category),
        "book_insight": book_insight,
        "goal_alerts": goal_alerts,
        "category": category,
        "amount": amount,
        "merchant": merchant
    }