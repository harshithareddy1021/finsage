from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_community.utilities import SQLDatabase
from utils.helpers import GROQ_API_KEY
from database.db import (
    get_income, get_active_emis, get_disposable_income,
    get_active_goals, get_db_path, create_table
)
from advice.advisor import load_existing_rag
import json

def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.3
    )

# ─────────────────────────────────────────────────────────────────
# TOOL DEFINITIONS
# Each tool is a function the agent can call autonomously
# ─────────────────────────────────────────────────────────────────

def tool_get_income(user_id: int):
    def _run(input: str = "") -> str:
        salary = get_income(user_id)
        if salary == 0:
            return "No income data found. User has not entered their salary yet."
        return f"Monthly salary: ₹{salary:,.2f}"
    return _run

def tool_get_emis(user_id: int):
    def _run(input: str = "") -> str:
        emis = get_active_emis(user_id)
        if not emis:
            return "No active EMIs found."
        lines = [f"Active EMIs:"]
        total = 0
        for e in emis:
            lines.append(
                f"- {e['name']}: ₹{e['amount']:,.0f}/month, "
                f"{e['months_remaining']} months remaining"
            )
            total += e["amount"]
        lines.append(f"Total monthly EMI burden: ₹{total:,.0f}")
        return "\n".join(lines)
    return _run

def tool_get_disposable_income(user_id: int):
    def _run(input: str = "") -> str:
        data = get_disposable_income(user_id)
        if data["salary"] == 0:
            return "No income data found. Cannot calculate disposable income."
        return (
            f"Monthly salary: ₹{data['salary']:,.0f}\n"
            f"Total EMI deductions: ₹{data['total_emi']:,.0f}\n"
            f"Disposable income: ₹{data['disposable']:,.0f}"
        )
    return _run

def tool_get_expenses(user_id: int):
    def _run(input: str = "") -> str:
        from database.db import load_transactions
        from datetime import date
        today = date.today()
        month_start = today.replace(day=1)
        transactions = load_transactions(
            user_id, "This Month"
        )
        if not transactions:
            return "No transactions found this month."
        total = sum(t["amount"] for t in transactions)
        by_category = {}
        for t in transactions:
            cat = t.get("category", "Others")
            by_category[cat] = by_category.get(cat, 0) + t["amount"]
        lines = [f"This month's spending (total: ₹{total:,.0f}):"]
        for cat, amt in sorted(by_category.items(),
                               key=lambda x: x[1], reverse=True):
            lines.append(f"- {cat}: ₹{amt:,.0f}")
        return "\n".join(lines)
    return _run

def tool_get_goal_progress(user_id: int):
    def _run(input: str = "") -> str:
        from database.db import load_transactions, get_disposable_income
        from datetime import date

        goals = get_active_goals(user_id)
        if not goals:
            return "No active savings goals found."

        # Calculate this month's savings
        data = get_disposable_income(user_id)
        transactions = load_transactions(user_id, "This Month")
        spent_this_month = sum(t["amount"] for t in transactions)
        saved_this_month = max(0, data["disposable"] - spent_this_month)

        lines = []
        today = date.today()

        for goal in goals:
            lines.append(f"\nGoal: {goal['name']}")
            lines.append(f"  Target: ₹{goal['target_amount']:,.0f}")
            if goal["target_date"]:
                target = date.fromisoformat(goal["target_date"])
                days_left = (target - today).days
                months_left = max(1, days_left // 30)
                needed_per_month = goal["target_amount"] / months_left
                lines.append(f"  Target date: {goal['target_date']} "
                            f"({days_left} days left)")
                lines.append(f"  Need to save: ₹{needed_per_month:,.0f}/month")
                lines.append(f"  Current monthly savings: ₹{saved_this_month:,.0f}")
                if saved_this_month >= needed_per_month:
                    lines.append(f"  ✅ On track to reach this goal!")
                else:
                    shortfall = needed_per_month - saved_this_month
                    lines.append(f"  ⚠️ Short by ₹{shortfall:,.0f}/month")
            else:
                lines.append(f"  Saving ₹{saved_this_month:,.0f} this month")
                months_to_goal = (goal["target_amount"] / saved_this_month
                                  if saved_this_month > 0 else 999)
                lines.append(f"  At this rate: {months_to_goal:.1f} months to reach goal")

        return "\n".join(lines)
    return _run

def tool_query_book(input: str = "") -> str:
    try:
        chain = load_existing_rag()
        if chain is None:
            return "No financial book has been uploaded yet."
        result = chain.invoke({"query": input if input else "financial advice"})
        answer = result.get("result", "").strip()
        return f"From your financial book: {answer[:300]}"
    except Exception:
        return "Could not retrieve information from the book."

# ─────────────────────────────────────────────────────────────────
# AGENT BUILDER
# ─────────────────────────────────────────────────────────────────

def build_finsage_agent(user_id: int) -> AgentExecutor:
    create_table()

    tools = [
        Tool(
            name="get_income",
            func=tool_get_income(user_id),
            description=(
                "Use this to get the user's monthly salary. "
                "Call this when the question involves income, "
                "salary, or earning."
            )
        ),
        Tool(
            name="get_emis",
            func=tool_get_emis(user_id),
            description=(
                "Use this to get all active EMIs (loan payments). "
                "Call this when the question involves loans, EMIs, "
                "or fixed monthly obligations."
            )
        ),
        Tool(
            name="get_disposable_income",
            func=tool_get_disposable_income(user_id),
            description=(
                "Use this to get the user's disposable income "
                "(salary minus EMIs). Call this when the question "
                "involves affordability, savings capacity, or "
                "how much money is available."
            )
        ),
        Tool(
            name="get_expenses",
            func=tool_get_expenses(user_id),
            description=(
                "Use this to get this month's spending breakdown "
                "by category. Call this when the question involves "
                "spending, expenses, or where money is going."
            )
        ),
        Tool(
            name="get_goal_progress",
            func=tool_get_goal_progress(user_id),
            description=(
                "Use this to check progress toward savings goals. "
                "Call this when the question involves goals, "
                "saving for something specific, or affordability "
                "of a future purchase."
            )
        ),
        Tool(
            name="query_book",
            func=tool_query_book,
            description=(
                "Use this to get advice from the user's uploaded "
                "financial book. Call this when asking for financial "
                "wisdom, strategies, or book-based recommendations. "
                "Pass the specific topic as input."
            )
        ),
    ]

    prompt = PromptTemplate.from_template("""
You are FinSage, a smart personal finance advisor for Indian users.
You have access to the user's real financial data through tools.

Always use tools to get actual data before answering.
Give specific, numbers-based answers. Reference actual figures.
Speak like a knowledgeable friend, not a generic chatbot.
All amounts are in Indian Rupees (₹).

You have access to the following tools:
{tools}

Use the following format:
Question: the input question you must answer
Thought: think about which tools to call and why
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Begin!

Question: {input}
Thought: {agent_scratchpad}
""")

    llm = get_llm()
    agent = create_react_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=6
    )

def ask_finsage(question: str, user_id: int) -> str:
    """
    Main entry point. Takes any financial question,
    runs the ReAct agent, returns a human-readable answer.
    """
    try:
        agent_executor = build_finsage_agent(user_id)
        result = agent_executor.invoke({"input": question})
        return result.get("output", "I could not generate a response.")
    except Exception as e:
        return f"FinSage encountered an error: {str(e)}"