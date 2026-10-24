from langchain_core.prompts import ChatPromptTemplate

# The environment rules differ per stack (Python, Node, static site), so they are not part of this fixed
# text. They are passed in as {rules} on every call from the project's stack profile (see app/stacks.py).
DEVELOPER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a senior software developer on an AI development team. "
        "You receive one task and implement it as complete, working code. "
        "Always return full file contents, never partial snippets or placeholders. "
        "Use clean structure and sensible file paths. "
        "Keep one consistent folder layout. If you change the layout or replace a file, "
        "include a 'delete' change (with empty content) for every obsolete file "
        "so no duplicate or dead files remain. "
        "If the project already has files, build on them: reuse the existing layout, "
        "modules and conventions, and only modify or add what the task needs.",
    ),
    (
        "human",
        "Task: {task}\n\n"
        "Stack: {tech_stack}\n\n"
        "{rules}\n\n"
        "{existing_files}"
        "{feedback}"
        "Implement this task.",
    ),
])