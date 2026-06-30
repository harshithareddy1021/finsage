from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import FakeEmbeddings
from langchain.chains import RetrievalQA
from utils.helpers import GROQ_API_KEY
import os

CHROMA_DIR = "data/chroma_db"

def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        
        model="llama-3.3-70b-versatile",
        temperature=0.3
    )

def generate_financial_advice(category_summary: dict, total_spent: float) -> tuple:
    """
    Generates financial advice using Groq LLM based on spending patterns.
    Returns (advice_text, suggested_savings)
    """
    spending_lines = "\n".join([
        f"- {cat}: ₹{amt:.2f}"
        for cat, amt in category_summary.items()
    ])

    prompt = f"""You are a helpful personal finance advisor for Indian users.

A user's spending summary this period:
{spending_lines}
Total spent: ₹{total_spent:.2f}

Give 3 specific, actionable financial tips based on their actual spending pattern.
Keep it concise, practical, and relevant to Indian context (UPI, SIP, savings).
Do not use generic advice. Reference their specific spending categories."""

    llm = get_llm()
    response = llm.invoke(prompt)
    advice = response.content

    suggested_savings = total_spent * 0.20
    return advice, suggested_savings


def build_rag_from_pdf(pdf_path: str) -> RetrievalQA:
    """
    Builds a RAG pipeline from a financial PDF book.
    Chunks the PDF, embeds it, stores in ChromaDB,
    and returns a RetrievalQA chain.
    """
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

    llm = get_llm()

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(
            search_kwargs={"k": 3}
        ),
        return_source_documents=True
    )
    return chain


def load_existing_rag() -> RetrievalQA:
    """
    Loads an already-built RAG chain from ChromaDB.
    Returns None if no book has been uploaded yet.
    """
    if not os.path.exists(CHROMA_DIR):
        return None

    
    embeddings = FakeEmbeddings(size=384)

    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings
    )

    llm = get_llm()

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(
            search_kwargs={"k": 3}
        ),
        return_source_documents=True
    )
    return chain


def query_rag(question: str, spending_context: str = "") -> dict:
    """
    Queries the RAG chain with a financial question.
    Optionally includes user spending context for personalized advice.
    """
    chain = load_existing_rag()
    if chain is None:
        return {
            "result": "No financial book uploaded yet. Please upload a PDF first.",
            "source_documents": []

        }

    full_question = question
    if spending_context:
        full_question = f"{question}\n\nUser's current spending context: {spending_context}"

    return chain.invoke({"query": full_question})
