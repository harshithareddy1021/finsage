from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_groq import ChatGroq
from database.db import get_db_path, create_table
from utils.helpers import GROQ_API_KEY

def get_sql_agent():
    create_table()
    db_path = get_db_path()
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model="llama-3.3-70b-versatile",
        temperature=0
    )

    agent = create_sql_agent(
        llm=llm,
        db=db,
        verbose=False,
        handle_parsing_errors=True
    )
    return agent

def query_expenses(question: str) -> str:
    try:
        agent = get_sql_agent()
        instruction = (
            f"All amounts in the database are in Indian Rupees (₹). "
            f"Always use the ₹ symbol in your answer. "
            f"Use the 'amount' column for all calculations — it is always in INR. "
            f"Question: {question}"
        )
        response = agent.invoke({"input": instruction})
        return response.get("output", "Could not generate a response.")
    except Exception as e:
        return f"Error querying expenses: {str(e)}"