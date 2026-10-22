from app.schemas.developer import FileChange
from app.tools.validators import validate_python_syntax

good = FileChange(
    path="app/good.py",
    action="create",
    content="def add(a, b):\n    return a + b\n",
    explanation="a fine file",
)

bad = FileChange(
    path="app/bad.py",
    action="create",
    content="def add(a, b)\n    return a + b\n",   # missing colon
    explanation="a broken file",
)

notes = FileChange(
    path="requirements.txt",
    action="create",
    content="fastapi\n",
    explanation="not python, should be skipped",
)

print("Good only:   ", validate_python_syntax([good, notes]))
print("With broken: ", validate_python_syntax([good, bad, notes]))