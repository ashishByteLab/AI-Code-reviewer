import os
import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from app.config import CHROMA_DIR

class ExperienceStore:
    """
    ChromaDB-backed persistent experience storage.
    Stores and semantically retrieves code patterns, past bugs, 
    unnecessary iteration antipatterns, and optimized alternative solutions.
    """
    def __init__(self, persist_directory: str = str(CHROMA_DIR)):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="code_sentinel_experiences",
            metadata={"description": "Code bug, iteration antipattern, and optimization memory"}
        )
        self._seed_default_experiences_if_empty()

    def _seed_default_experiences_if_empty(self):
        count = self.collection.count()
        if count == 0:
            default_experiences = [
                {
                    "title": "O(N^2) Nested Loop to O(N) Hash Map Lookup",
                    "category": "ITERATION_OPTIMIZATION",
                    "bug_snippet": "duplicates = []\nfor item in list_a:\n    for candidate in list_b:\n        if item == candidate:\n            duplicates.append(item)",
                    "fix_snippet": "set_b = set(list_b)\nduplicates = [item for item in list_a if item in set_b]",
                    "explanation": "Replacing nested linear scan O(N*M) with O(1) average hash set membership tests achieves O(N + M) complexity and eliminates massive CPU iterations.",
                    "tags": "loops, time-complexity, set, hash-map"
                },
                {
                    "title": "Serverless Cold-Start: Heavy Imports Inside Handler",
                    "category": "SERVERLESS_HOTSPOT",
                    "bug_snippet": "def lambda_handler(event, context):\n    import pandas as pd\n    import numpy as np\n    df = pd.DataFrame(event['data'])\n    return df.describe().to_dict()",
                    "fix_snippet": "import pandas as pd\nimport numpy as np\n\ndef lambda_handler(event, context):\n    df = pd.DataFrame(event['data'])\n    return df.describe().to_dict()",
                    "explanation": "Moving module imports outside the handler execution scope leverages execution environment container warming, reducing cold start latency by up to 800ms per invocation (IEEE Access 2024).",
                    "tags": "serverless, cold-start, aws-lambda, imports"
                },
                {
                    "title": "Un-memoized Exponential Recursion to LRU Cache / DP",
                    "category": "COMPUTATIONAL_COST",
                    "bug_snippet": "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
                    "fix_snippet": "from functools import lru_cache\n\n@lru_cache(maxsize=None)\ndef fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
                    "explanation": "Recursion tree has O(2^N) redundant recalculations. Decorating with @lru_cache memoizes overlapping subproblems into O(N) linear time and drastically lowers compute cost.",
                    "tags": "recursion, memoization, lru_cache, dynamic-programming"
                },
                {
                    "title": "Metamorphic Relation Invariant: Symmetry under Reverse (COMER)",
                    "category": "METAMORPHIC_INVARIANT",
                    "bug_snippet": "def compute_bag_checksum(items):\n    acc = 0\n    for idx, x in enumerate(items):\n        acc += x * (idx + 1) # Depends on ordering, fails commutativity!\n    return acc",
                    "fix_snippet": "def compute_bag_checksum(items):\n    return sum(hash(x) for x in items)",
                    "explanation": "According to COMER (IEEE TSE 2022), bag and multiset functions must satisfy the Permutation & Reverse Metamorphic Relation: f(reverse(x)) == f(x). Index coupling breaks symmetry.",
                    "tags": "metamorphic, comer, reverse, invariant"
                },
                {
                    "title": "SQL Injection & Dangerous Shell Execution Prevention",
                    "category": "SECURITY",
                    "bug_snippet": "query = f'SELECT * FROM users WHERE username = \"{username}\"'\ncursor.execute(query)",
                    "fix_snippet": "cursor.execute('SELECT * FROM users WHERE username = ?', (username,))",
                    "explanation": "Parameterized queries protect against SQL injection (Bandit B608 / CWE-89) by separating SQL code from user-supplied untrusted data.",
                    "tags": "security, bandit, sql-injection, cwe-89"
                },
                {
                    "title": "Quantum Transform Reversibility: Non-Invertible Normalization",
                    "category": "QUANTUM_REVERSIBILITY",
                    "bug_snippet": "def normalize_state(vector):\n    # Dropping sign information makes inversion impossible\n    return [abs(x) ** 2 for x in vector]",
                    "fix_snippet": "import math\ndef normalize_state(vector):\n    norm = math.sqrt(sum(abs(x) ** 2 for x in vector)) or 1.0\n    return [x / norm for x in vector]",
                    "explanation": "Wang et al. (IEEE Software 2025) highlights transform-based detection. Unitary and state operations must maintain reversibility properties f_inv(f(state)) == state without losing phase or amplitude signs.",
                    "tags": "quantum, reversibility, transform-detection, unitary"
                }
            ]
            
            for exp in default_experiences:
                self.add_experience(
                    title=exp["title"],
                    category=exp["category"],
                    bug_snippet=exp["bug_snippet"],
                    fix_snippet=exp["fix_snippet"],
                    explanation=exp["explanation"],
                    tags=exp.get("tags", "")
                )

    def add_experience(self, title: str, category: str, bug_snippet: str, fix_snippet: str, explanation: str, tags: str = "") -> str:
        doc_id = str(uuid.uuid4())
        document_text = f"Title: {title}\nCategory: {category}\nTags: {tags}\nBug Pattern:\n{bug_snippet}\nFix/Optimization:\n{fix_snippet}\nExplanation:\n{explanation}"
        
        self.collection.add(
            ids=[doc_id],
            documents=[document_text],
            metadatas=[{
                "title": title,
                "category": category,
                "bug_snippet": bug_snippet,
                "fix_snippet": fix_snippet,
                "explanation": explanation,
                "tags": tags
            }]
        )
        return doc_id

    def query_similar_experiences(self, query_code: str, n_results: int = 3) -> List[Dict[str, Any]]:
        try:
            results = self.collection.query(
                query_texts=[query_code],
                n_results=min(n_results, max(1, self.collection.count()))
            )
            
            output = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                for idx, doc_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][idx] if results.get("metadatas") else {}
                    distance = results["distances"][0][idx] if results.get("distances") else 0.0
                    similarity_pct = max(0.0, round((1.0 - float(distance)) * 100, 1)) if distance is not None else 85.0
                    output.append({
                        "id": doc_id,
                        "title": meta.get("title", "Experience"),
                        "category": meta.get("category", "General"),
                        "bug_snippet": meta.get("bug_snippet", ""),
                        "fix_snippet": meta.get("fix_snippet", ""),
                        "explanation": meta.get("explanation", ""),
                        "tags": meta.get("tags", ""),
                        "similarity_pct": similarity_pct
                    })
            return output
        except Exception as e:
            return []

    def get_all_experiences(self) -> List[Dict[str, Any]]:
        try:
            results = self.collection.get()
            output = []
            if results and results.get("ids"):
                for idx, doc_id in enumerate(results["ids"]):
                    meta = results["metadatas"][idx] if results.get("metadatas") else {}
                    output.append({
                        "id": doc_id,
                        "title": meta.get("title", ""),
                        "category": meta.get("category", ""),
                        "bug_snippet": meta.get("bug_snippet", ""),
                        "fix_snippet": meta.get("fix_snippet", ""),
                        "explanation": meta.get("explanation", ""),
                        "tags": meta.get("tags", "")
                    })
            return output
        except Exception:
            return []

# Singleton instance
_store_instance = None

def get_experience_store() -> ExperienceStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = ExperienceStore()
    return _store_instance
