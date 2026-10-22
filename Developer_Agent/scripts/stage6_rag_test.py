import hashlib
from langchain_core.embeddings import Embeddings
import re, math
from app.schemas.developer import FileChange
from app.tools.workspace import Workspace
from app.rag.store import ProjectIndex, format_chunks


class FakeEmbeddings(Embeddings):
    """Bag-of-words hashing, normalized. No API."""

    DIM = 256

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.DIM
        # Split on non-alphanumerics so "password):" becomes "password"
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            v[h % self.DIM] += 1.0
        # Normalize so length doesn't dominate similarity
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


ws = Workspace("rag_test")
ws.apply_changes([
    FileChange(path="app/auth.py", action="create", explanation="x",
               content="def login(user, password):\n    # verify password hash and return token\n    return token\n"),
    FileChange(path="app/db.py", action="create", explanation="x",
               content="engine = create_engine(DATABASE_URL)\nSessionLocal = sessionmaker(bind=engine)\n"),
    FileChange(path="app/menu.py", action="create", explanation="x",
               content="def list_menu_items(restaurant_id):\n    return items_for_restaurant\n"),
])

index = ProjectIndex("rag_test", embeddings=FakeEmbeddings())
print("Chunks indexed:", index.rebuild())

hits = index.search("verify password login token", k=2)
print()
print(format_chunks(hits))