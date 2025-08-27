"""
Evidence-first verification system using local knowledge base.
Replaces web search with BM25 + rapidfuzz matching against reviewed documents.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
import re

from whoosh import index
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
from whoosh.analysis import StandardAnalyzer
from rapidfuzz import fuzz

from app.utils.json_io import call_llm_json, JsonParseError
from app.schemas.agent_schemas import CLAIMS_EXTRACTION_SCHEMA, RETRIEVAL_VERIFIER_SCHEMA


class RetrievalVerifier:
    """Evidence-first verification using local knowledge base."""
    
    def __init__(self, kb_path: str = "kb/reviewed_docs", threshold: float = 0.6):
        self.kb_path = Path(kb_path)
        self.threshold = threshold
        self.logger = logging.getLogger(__name__)
        self.index_dir = Path("kb/index")
        self.documents = {}
        self._ensure_index()
    
    def _ensure_index(self):
        """Create or load the search index."""
        if not self.index_dir.exists():
            self.index_dir.mkdir(parents=True, exist_ok=True)
            self._create_index()
        else:
            self._load_index()
    
    def _create_index(self):
        """Create a new search index from markdown files."""
        schema = Schema(
            doc_id=ID(stored=True),
            content=TEXT(analyzer=StandardAnalyzer(), stored=True),
            line_num=ID(stored=True)
        )
        
        self.ix = index.create_in(str(self.index_dir), schema)
        writer = self.ix.writer()
        
        # Index all markdown files
        for md_file in self.kb_path.glob("*.md"):
            self._index_document(writer, md_file)
        
        writer.commit()
        self.logger.info(f"Created search index with {len(self.documents)} documents")
    
    def _load_index(self):
        """Load existing search index."""
        self.ix = index.open_dir(str(self.index_dir))
        
        # Reload documents
        for md_file in self.kb_path.glob("*.md"):
            self._load_document(md_file)
        
        self.logger.info(f"Loaded search index with {len(self.documents)} documents")
    
    def _index_document(self, writer, md_file: Path):
        """Index a single markdown document."""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            doc_name = md_file.name
            self.documents[doc_name] = lines
            
            # Index each line separately for precise line number tracking
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and headers
                    writer.add_document(
                        doc_id=f"{doc_name}:{line_num}",
                        content=line,
                        line_num=str(line_num)
                    )
        except Exception as e:
            self.logger.error(f"Error indexing {md_file}: {e}")
    
    def _load_document(self, md_file: Path):
        """Load document content for rapidfuzz fallback."""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            self.documents[md_file.name] = lines
        except Exception as e:
            self.logger.error(f"Error loading {md_file}: {e}")
    
    def extract_claims(self, model_output: str) -> List[str]:
        """Extract factual claims from model output using LLM."""
        extraction_prompt = f"""
Extract all factual claims from the following text. A claim is a statement that can be verified as true or false.

TEXT TO ANALYZE:
{model_output}

Return ONLY JSON with this structure:
{{
"claims": ["claim 1", "claim 2", "claim 3"]
}}

Focus on:
- Specific facts, statistics, or assertions
- Technical statements about security, AI, or software
- Procedural claims about how things work
- Skip opinions, questions, or general statements
"""
        
        try:
            result = call_llm_json(extraction_prompt, CLAIMS_EXTRACTION_SCHEMA)
            claims = result.get("claims", [])
            self.logger.info(f"Extracted {len(claims)} claims from model output")
            return claims
        except JsonParseError as e:
            self.logger.error(f"Failed to extract claims: {e}")
            return []
    
    def search_claim(self, claim: str) -> List[Tuple[str, int, float]]:
        """Search for evidence supporting a claim using BM25."""
        try:
            with self.ix.searcher() as searcher:
                parser = QueryParser("content", self.ix.schema)
                query = parser.parse(claim)
                results = searcher.search(query, limit=10)
                
                evidence = []
                for result in results:
                    doc_id = result["doc_id"]
                    doc_name, line_num = doc_id.split(":", 1)
                    score = result.score
                    evidence.append((doc_name, int(line_num), score))
                
                return evidence
        except Exception as e:
            self.logger.error(f"BM25 search failed for claim '{claim}': {e}")
            return []
    
    def fuzzy_search_claim(self, claim: str) -> List[Tuple[str, int, float]]:
        """Fallback fuzzy search using rapidfuzz."""
        evidence = []
        
        for doc_name, lines in self.documents.items():
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if len(line) < 10:  # Skip very short lines
                    continue
                
                # Calculate fuzzy similarity
                ratio = fuzz.ratio(claim.lower(), line.lower()) / 100.0
                if ratio >= self.threshold:
                    evidence.append((doc_name, line_num, ratio))
        
        # Sort by score descending
        evidence.sort(key=lambda x: x[2], reverse=True)
        return evidence[:5]  # Return top 5 matches
    
    def verify_claim(self, claim: str) -> Dict[str, Any]:
        """Verify a single claim against the knowledge base."""
        # Try BM25 search first
        bm25_evidence = self.search_claim(claim)
        
        # Normalize BM25 scores (rough approximation)
        normalized_evidence = []
        if bm25_evidence:
            max_score = max(score for _, _, score in bm25_evidence)
            for doc, line, score in bm25_evidence:
                normalized_score = score / max_score if max_score > 0 else 0
                if normalized_score >= self.threshold:
                    normalized_evidence.append((doc, line, normalized_score))
        
        # Fallback to fuzzy search if BM25 didn't find good matches
        if not normalized_evidence:
            fuzzy_evidence = self.fuzzy_search_claim(claim)
            normalized_evidence = fuzzy_evidence
        
        # Determine verdict
        if normalized_evidence:
            verdict = "SUPPORTED"
            evidence_items = [
                {"doc": doc, "lines": [line]} 
                for doc, line, _ in normalized_evidence
            ]
        else:
            verdict = "UNVERIFIABLE"
            evidence_items = []
        
        return {
            "text": claim,
            "verdict": verdict,
            "evidence": evidence_items
        }
    
    def verify_response(self, model_output: str) -> Dict[str, Any]:
        """Main verification method - extract claims and verify each one."""
        claims = self.extract_claims(model_output)
        
        if not claims:
            return {
                "claims": [],
                "evidence_score": 0.0
            }
        
        verified_claims = []
        supported_count = 0
        
        for claim in claims:
            verification = self.verify_claim(claim)
            verified_claims.append(verification)
            
            if verification["verdict"] == "SUPPORTED":
                supported_count += 1
        
        # Calculate overall evidence score
        evidence_score = supported_count / len(claims) if claims else 0.0
        
        result = {
            "claims": verified_claims,
            "evidence_score": evidence_score
        }
        
        self.logger.info(f"Verified {len(claims)} claims, {supported_count} supported, score: {evidence_score:.2f}")
        return result


def create_retrieval_verifier(kb_path: str = "kb/reviewed_docs", threshold: float = 0.6) -> RetrievalVerifier:
    """Factory function to create a RetrievalVerifier instance."""
    return RetrievalVerifier(kb_path, threshold)
