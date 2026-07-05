#  FinSage — AI-Powered Personal Finance Assistant

> An agentic personal finance platform that reads your payment screenshots, understands your spending, and answers any financial question using a LangChain ReAct Agent backed by real financial data.

---



## 🤖 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT UI                              │
│  Auth │ Upload │ Manual │ Income/EMI │ Goals │ Dashboard    │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │     FINSAGE ReAct AGENT     │
        │   LangChain + Groq LLaMA    │
        │   3.3 70B Versatile         │
        └──┬──────┬──────┬──────┬────┘
           │      │      │      │
     ┌─────▼─┐ ┌──▼──┐ ┌▼────┐ ┌▼──────────┐
     │Income │ │ EMI │ │Goal │ │  Expense  │
     │ Tool  │ │Tool │ │Tool │ │   Tool    │
     └───────┘ └─────┘ └─────┘ └───────────┘
           │                         │
     ┌─────▼─────────────────────────▼──────┐
     │            SQLite Database            │
     │  users │ transactions │ emis │ goals  │
     └───────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────────┐
│   OCR PIPELINE   │    │     RAG PIPELINE      │
│                  │    │                       │
│ Screenshot       │    │ Financial PDF         │
│     ↓            │    │      ↓                │
│ Groq Vision      │    │ PyPDFLoader           │
│ LLaMA 4 Scout    │    │      ↓                │
│     ↓            │    │ Text Chunking         │
│ Structured JSON  │    │      ↓                │
│ {amount,         │    │  chromadb    │
│  merchant,       │    │      ↓                │
│  category...}    │    │ RetrievalQA Chain     │
└──────────────────┘    │      ↓                │
                        │ Groq LLM Answer       │
                        └──────────────────────┘
```

---


## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **UI** | Streamlit |
| **Agent Framework** | LangChain ReAct Agent |
| **LLM (Text)** | Groq — LLaMA 3.3 70B Versatile |
| **LLM (Vision)** | Groq — LLaMA 4 Scout 17B |
| **RAG Pipeline** | LangChain + chromadb |
| **Vector Store** | chromadb |
| **Database** | SQLite |
| **ML** | NumPy Z-score anomaly detection |
| **Auth** | bcrypt password hashing |
| **Currency** | ExchangeRate API (live INR/USD) |
| **OCR** | Groq Vision API |

---

## 📁 Project Structure

```
finsage/
│
├── app.py                    # Main Streamlit app — all pages and routing
│
├── advice/
│   ├── agent.py              # LangChain ReAct Agent with 6 tools
│   ├── advisor.py            # RAG pipeline + financial advice generation
│   ├── intelligence.py       # Unified intelligence engine (post-save insight)
│   └── sql_agent.py          # LangChain SQL Agent (legacy query support)
│
├── database/
│   └── db.py                 # SQLite — users, transactions, EMIs, goals
│
├── ml/
│   └── anomaly.py            # Z-score anomaly detection + category suggestion
│
├── ocr/
│   └── ocr_engine.py         # Groq Vision OCR pipeline
│
├── utils/
│   ├── helpers.py            # API key management
│   ├── validators.py         # Input validation (email, password, username)
│   └── currency.py           # INR/USD conversion with live rates
│
└── data/                     # SQLite DB + Chromadb (gitignored)
```

---

```



## 📱 Usage Guide

### 1. Register & Login
Create an account with username, email, and password. All passwords are bcrypt-hashed.

### 2. Add Income & EMIs
Go to **Income & EMI** → Enter your monthly salary → Add any loan EMIs with name, amount, and tenure. FinSage auto-calculates your disposable income.

### 3. Track Expenses
**Upload & Extract** → Upload any payment screenshot → AI reads it automatically → Review and save.

Or use **Manual Entry** → Enter expense details → Category auto-suggested from merchant name.

### 4. Set Goals
Go to **Goals** → Set a savings goal with target amount and date → FinSage tracks your progress after every transaction.

### 5. Ask FinSage
Go to **Ask FinSage** → Ask anything in plain English → The ReAct Agent queries your real financial data across all tools and responds with a personalized answer.

### 6. Upload Financial Books
Go to **Book Advisor** → Upload any financial PDF → Ask questions grounded in both the book and your spending patterns.

### 7. View Dashboard
See spending breakdowns, trends, anomaly alerts, and generate dynamic AI financial advice based on your actual spending vs healthy benchmarks.

---

## 🔒 Security

- Passwords hashed with **bcrypt** — never stored in plaintext
- Per-user data isolation via **foreign key constraints** — users cannot access each other's data
- API keys stored in **environment variables** — never committed to version control
- Parameterized SQL queries — **SQL injection protected**
- Screenshot images processed by Groq Vision and **never stored** — only extracted fields saved locally
- **Zero Data Retention** enabled on Groq console

---

## 🤖 How the ReAct Agent Works

The FinSage Agent follows the **Reason → Act → Observe** loop:

```
User: "Can I afford a new phone next month?"

Thought: I need to check income, EMIs, and this month's expenses
Action: get_disposable_income
Observation: Salary ₹50,000 | EMIs ₹12,000 | Disposable ₹38,000

Thought: Now I need to see how much has been spent this month
Action: get_expenses
Observation: Spent ₹22,000 this month (Food ₹8,000, Shopping ₹6,000...)

Thought: Remaining = ₹38,000 - ₹22,000 = ₹16,000
Action: get_goal_progress
Observation: Goa trip goal needs ₹5,000/month — currently saving ₹16,000 ✅

Final Answer: "You have ₹16,000 remaining this month after expenses.
After setting aside ₹5,000 for your Goa trip goal, you'd have
₹11,000 available. A mid-range phone under ₹10,000 is affordable
this month. A flagship phone above ₹15,000 would strain your goals."
```

---

## 🔮 Roadmap

- [ ] PostgreSQL migration for persistent cloud deployment
- [ ] Local vision model (LLaVA) for on-device OCR
- [ ] Recurring transaction detection
- [ ] Monthly financial report generation (PDF export)
- [ ] Mobile app (React Native)
- [ ] Bank SMS parsing for automatic expense capture

---

## 🎓 Built By

**Harshitha Reddy**

demonstrating practical applications of:
- Agentic AI (LangChain ReAct)
- Retrieval-Augmented Generation
- Vision AI for document understanding
- Statistical ML for anomaly detection
- Secure multi-user application architecture

---



*FinSage — Because financial clarity shouldn't require a finance degree.*
