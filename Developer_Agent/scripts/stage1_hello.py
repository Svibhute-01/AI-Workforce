from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.llm import get_llm

llm = get_llm()

# 1. The template: {task} is a placeholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a poet. Be concise. Reply with code only."),
    ("human", "Write a function for this task: {task}"),
])

# 2. The parser: turns the AIMessage into a plain string
parser = StrOutputParser()

# 3. The chain: prompt -> llm -> parser
chain = prompt | llm | parser

# 4. Run it, filling in the placeholder with a dictionary
result = chain.invoke({"task": "write poem on friend"})

print("TYPE:  ", type(result))
print("RESULT:")
print(result)