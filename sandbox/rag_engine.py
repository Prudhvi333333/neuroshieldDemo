import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SafePromptRAG:
    def __init__(self, data_path="data/safe_prompts.json"):
        self.data_path = data_path
        self.prompts = []
        self.rewrites = []
        self.vectorizer = TfidfVectorizer()
        self.vectors = None
        self._load_data()

    def _load_data(self):
        if not os.path.exists(self.data_path):
            with open(self.data_path, "w") as f:
                json.dump([], f)

        with open(self.data_path, "r") as f:
            data = json.load(f)
            self.prompts = [entry["prompt"] for entry in data]
            self.rewrites = [entry["rewrite"] for entry in data]

        if self.prompts:
            self.vectors = self.vectorizer.fit_transform(self.prompts)
        else:
            self.vectors = None

    def query(self, input_prompt, threshold=0.8):
        if not self.vectors or not self.prompts:
            return None, 0.0

        query_vec = self.vectorizer.transform([input_prompt])
        similarity = cosine_similarity(query_vec, self.vectors).flatten()
        max_idx = similarity.argmax()
        max_score = similarity[max_idx]

        if max_score >= threshold:
            return self.rewrites[max_idx], max_score
        return None, max_score

    def append_to_json(self, original, rewritten):
        try:
            with open(self.data_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []

        data.append({"prompt": original, "rewrite": rewritten})

        with open(self.data_path, "w") as f:
            json.dump(data, f, indent=2)

        print("✅ New prompt added to RAG.")

    def rebuild_index(self):
        self._load_data()
        print("🔄 RAG index rebuilt.")