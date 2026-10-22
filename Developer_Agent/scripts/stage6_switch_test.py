import app.tools.context as ctx
from app.schemas.developer import FileChange
from app.tools.workspace import Workspace

ws = Workspace("rag_test")   # still has auth.py, db.py, menu.py from before

ctx.CONTEXT_MODE = "all_files"
print("ALL FILES:", len(ctx.build_context(ws, "verify password login")), "chars")

# RAG mode with the fake embeddings from the previous test
from scripts.stage6_rag_test import FakeEmbeddings
from app.rag.store import ProjectIndex

ctx.CONTEXT_MODE = "rag"
index = ProjectIndex("rag_test", embeddings=FakeEmbeddings())
print("RAG:      ", len(ctx.build_context(ws, "verify password login", index=index)), "chars")