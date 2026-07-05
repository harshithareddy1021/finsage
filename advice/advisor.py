from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import FakeEmbeddings
from langchain.chains import RetrievalQA
from utils.helpers import GROQ_API_KEY
import os

CHROMA_DIR = "data/chroma_db"

CATEGORY_BENCHMARKS = {
    "Food":          0.30,
    "Shopping":      0.20,
    "Transport":     0.15,
    "Entertainment": 0.10,
    "Utilities":     0.15,
    "Healthcare":    0.10,
    "Others":        0.10
}

def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0.4
    )

def generate_financial_advice(category_summary: dict, total_spent: float) -> tuple:
    if total_spent == 0:
        return "Add some transactions to get personalized advice.", 0

    overspent = []
    for category, amount in category_summary.items():
        actual_pct = amount / total_spent
        benchmark = CATEGORY_BENCHMARKS.get(category, 0.10)
        diff = actual_pct - benchmark
        if diff > 0.05:
            overspent.append((category, amount, actual_pct * 100, benchmark * 100))

    spending_lines = "\n".join([
        f"- {cat}: ₹{amt:.2f} ({(amt/total_spent*100):.1f}% of spending, "
        f"benchmark is {CATEGORY_BENCHMARKS.get(cat, 0.10)*100:.0f}%)"
        for cat, amt in category_summary.items()
    ])

    overspent_text = "\n".join([
        f"- {cat}: spending {pct:.1f}% but benchmark is {bench:.0f}%"
        for cat, amt, pct, bench in overspent
    ]) if overspent else "None"

    if overspent:
        potential_savings = sum(
            amt - (total_spent * CATEGORY_BENCHMARKS.get(cat, 0.10))
            for cat, amt, _, _ in overspent
        )
        savings_pct = min(max((potential_savings / total_spent) * 100, 5), 40)
    else:
        potential_savings = total_spent * 0.10
        savings_pct = 10

    prompt = f"""You are a practical personal finance advisor for Indian users.

User's spending breakdown:
{spending_lines}
Total spent: ₹{total_spent:.2f}

Categories where user is overspending vs healthy benchmarks:
{overspent_text}

Potential monthly savings if benchmarks are met: ₹{potential_savings:.2f} ({savings_pct:.1f}%)

Give exactly 3 specific, actionable tips. Each tip must:
1. Reference a specific category from their data
2. Give a concrete action (not generic advice)
3. Be relevant to Indian context (UPI, SIP, Zomato, etc.)

Format as 3 numbered points. Be direct and specific."""

    llm = get_llm()
    response = llm.invoke(prompt)
    advice = response.content

    return advice, round(potential_savings, 2)


def build_rag_from_pdf(pdf_path: str) -> RetrievalQA:
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = splitter.split_documents(documents)

    embeddings = FakeEmbeddings(size=384)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    chain = RetrievalQA.from_chain_type(
        llm=get_llm(),
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )
    return chain


def load_existing_rag() -> RetrievalQA:
    if not os.path.exists(CHROMA_DIR):
        return None
    embeddings = FakeEmbeddings(size=384)
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings
    )
    chain = RetrievalQA.from_chain_type(
        llm=get_llm(),
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )
    return chain


def query_rag(question: str, spending_context: str = "") -> dict:
    chain = load_existing_rag()
    if chain is None:
        return {
            "result": "No financial book uploaded yet. Please upload a PDF first.",
            "source_documents": []
        }
    full_question = question
    if spending_context:
        full_question = f"{question}\n\nUser's spending context: {spending_context}"
    return chain.invoke({"query": full_question})