from langchain_ollama import ChatOllama

MODEL_NAME = "gemma4:e2b"

llm = ChatOllama(
    model=MODEL_NAME,
    temperature=0,
    num_predict=2048,
)