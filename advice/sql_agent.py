from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_groq import ChatGroq
from database.db import get_db_path, create_table
from utils.helpers import GROQ_API_KEY

def get_sql_agent():
    """
    Creates a LangChain SQL Agent that converts natural language
    questions into SQL queries over the expenses database.
    """
    create_table()  # Ensure table exists

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
    """
    Takes a natural language question and returns an answer
    based on the expenses database.
    """
    try:
        agent = get_sql_agent()
        response = agent.invoke({"input": question})
        return response.get("output", "Could not generate a response.")
    except Exception as e:
        return f"Error querying expenses: {str(e)}"