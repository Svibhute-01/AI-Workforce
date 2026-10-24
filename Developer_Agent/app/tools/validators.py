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

LOCAL_REFERENCE = __import__("re").compile(r"""(?:src|href)\s*=\s*["']([^"'#?]+)""", __import__("re").IGNORECASE)


def validate_static_site(workspace) -> list[str]:
    """A static site needs index.html, and every local file it links to must exist."""
    files = set(workspace.list_files())
    if "index.html" not in files:
        return ["index.html is missing from the project root."]

    errors = []
    for page in sorted(path for path in files if path.endswith(".html")):
        folder = page.rsplit("/", 1)[0] if "/" in page else ""
        for reference in LOCAL_REFERENCE.findall(workspace.read_file(page)):
            if reference.startswith(("http:", "https:", "//", "mailto:", "tel:", "data:", "javascript:")):
                continue
            target = reference.lstrip("/") if reference.startswith("/") else "/".join(filter(None, [folder, reference]))
            parts = []
            for part in target.split("/"):
                if part == "..":
                    if parts:
                        parts.pop()
                elif part not in ("", "."):
                    parts.append(part)
            if "/".join(parts) not in files:
                errors.append(f"{page} links to '{reference}', which does not exist in the project.")
    return errors
