import ast
from app.schemas.developer import FileChange


def validate_python_syntax(changes: list[FileChange]) -> list[str]:
    """Check every created/modified .py file for syntax errors."""
    errors = []

    for change in changes:
        # Deleted files have no content to check; non-Python files are skipped
        if change.action == "delete" or not change.path.endswith(".py"):
            continue

        try:
            ast.parse(change.content)
        except SyntaxError as e:
            errors.append(f"{change.path}: line {e.lineno}: {e.msg}")

    return errors