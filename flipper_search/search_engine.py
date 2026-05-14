"""
Search engine: lexical retrieval + semantic rerank.

Two-stage retrieval:
  Stage A: Fast lexical (TF-IDF) retrieval → top 30-50 candidates
  Stage B: Semantic rerank via embeddings → top 5-10 results
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import os
from dotenv import load_dotenv

from sklearn.feature_extraction.text import TfidfVectorizer

from .curriculum_index import CurriculumIndex


class SearchEngine:
    """
    Hybrid search: lexical (TF-IDF) + semantic rerank.
    """
    
    def __init__(
        self,
        curriculum_index: CurriculumIndex,
        embeddings_path: Optional[str] = None,
        use_semantic: bool = True,
    ):
        """
        Initialize search engine.
        
        Args:
            curriculum_index: CurriculumIndex instance
            embeddings_path: Path to precomputed embeddings .npy file
            use_semantic: Whether to use semantic reranking
        """
        self.curriculum_index = curriculum_index
        self.embeddings_path = Path(embeddings_path) if embeddings_path else None
        self.use_semantic = use_semantic
        
        self.vectorizer = None
        self.tfidf_matrix = None
        self.embeddings = None  # Shape: (n_steps, embedding_dim)
        self.embedding_ids = []  # List of small_step_ids corresponding to embeddings rows
        self.embedder = None
        
        # Initialize embedder if semantic search requested
        if self.use_semantic:
            try:
                from query_embedder import QueryEmbedder
                load_dotenv()
                api_key = os.getenv('OPENAI_API_KEY')
                self.embedder = QueryEmbedder(api_key=api_key)
            except Exception as e:
                print(f"⚠ Warning: Could not initialize QueryEmbedder: {e}")
                print("  Falling back to lexical-only search")
                self.use_semantic = False
        
        self._build_lexical_index()
        self._load_semantic_index()
    
    def _build_lexical_index(self):
        """Build TF-IDF vectorizer and matrix."""
        searchable_text_dict = self.curriculum_index.get_searchable_text_all()
        
        if not searchable_text_dict:
            raise ValueError("No searchable text in curriculum index")
        
        # Maintain order: (small_step_id, text)
        self.embedding_ids = list(searchable_text_dict.keys())
        texts = [searchable_text_dict[ss_id] for ss_id in self.embedding_ids]
        
        # Build TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            max_features=10000,
            ngram_range=(1, 2),  # Unigrams and bigrams
            min_df=1,
            max_df=0.95,
        )
        
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        print(f"✓ Built TF-IDF index: {len(self.embedding_ids)} documents")
    
    def _load_semantic_index(self):
        """Load precomputed embeddings if available and semantic search enabled."""
        if not self.use_semantic:
            return
        
        if not self.embeddings_path or not self.embeddings_path.exists():
            print(f"ℹ Semantic embeddings not found at {self.embeddings_path}")
            print("  Semantic reranking will be skipped until embeddings are precomputed")
            self.use_semantic = False
            return
        
        try:
            # Load embeddings: shape (n_steps, embedding_dim)
            self.embeddings = np.load(str(self.embeddings_path))
            print(f"✓ Loaded semantic embeddings: {self.embeddings.shape}")
        except Exception as e:
            print(f"⚠ Warning: Could not load embeddings: {e}")
            print("  Falling back to lexical-only search")
            self.use_semantic = False
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        lexical_candidates_k: int = 50,
    ) -> List[Dict]:
        """
        Two-stage search: lexical retrieval + semantic rerank.
        
        Args:
            query: User search query (natural language)
            top_k: Number of results to return
            lexical_candidates_k: Number of lexical candidates for semantic reranking
        
        Returns:
            List of dicts with keys:
              - small_step_id
              - topic, small_step_name, ss_desc, ss_wr_desc
              - year, age, term, difficulty
              - lexical_score (0-1)
              - semantic_score (0-1, if available)
              - combined_score (0-1, weighted blend)
        """
        if not query or not query.strip():
            return []
        
        query = query.strip()
        
        # Stage A: Lexical retrieval
        lexical_results = self._lexical_search(query, top_k=lexical_candidates_k)
        
        if not lexical_results:
            return []
        
        # Stage B: Semantic rerank (optional)
        if self.use_semantic and self.embeddings is not None and self.embedder:
            results = self._semantic_rerank(query, lexical_results, top_k=top_k)
        else:
            # Fallback: return top lexical results
            results = lexical_results[:top_k]
        
        # Attach curriculum metadata
        results = self._attach_curriculum_data(results)
        
        return results
    
    def _lexical_search(self, query: str, top_k: int = 50) -> List[Dict]:
        """
        Lexical retrieval using TF-IDF similarity.
        
        Args:
            query: Search query
            top_k: Number of results
        
        Returns:
            List of dicts with small_step_id and lexical_score
        """
        # Vectorize query using same vocabulary
        query_vec = self.vectorizer.transform([query])
        
        # Cosine similarity
        similarities = (self.tfidf_matrix * query_vec.T).toarray().flatten()
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Build results
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # Only include non-zero matches
                results.append({
                    'small_step_id': self.embedding_ids[idx],
                    'lexical_score': float(similarities[idx]),
                })
        
        return results
    
    def _semantic_rerank(
        self,
        query: str,
        lexical_results: List[Dict],
        top_k: int = 10,
    ) -> List[Dict]:
        """
        Rerank lexical results using semantic similarity.
        
        Args:
            query: Search query
            lexical_results: Results from lexical search
            top_k: Number of final results
        
        Returns:
            Reranked results with semantic_score and combined_score
        """
        if not lexical_results or self.embeddings is None or self.embedder is None:
            return lexical_results[:top_k]
        
        try:
            # Embed query
            query_embedding = self.embedder.embed_query(query)  # Shape: (1, dim)
            query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
            
            # Compute semantic similarity for lexical results
            for result in lexical_results:
                ss_id = result['small_step_id']
                
                # Find index in embedding_ids list
                try:
                    emb_idx = self.embedding_ids.index(ss_id)
                except ValueError:
                    result['semantic_score'] = 0.0
                    continue
                
                # Get embedding and normalize
                embedding = self.embeddings[emb_idx].reshape(1, -1)
                embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
                
                # Cosine similarity
                similarity = float(np.dot(query_embedding, embedding.T)[0, 0])
                result['semantic_score'] = max(0.0, min(1.0, (similarity + 1) / 2))  # Normalize to [0,1]
            
            # Compute combined score: 60% semantic + 40% lexical
            for result in lexical_results:
                semantic = result.get('semantic_score', 0.0)
                lexical = result.get('lexical_score', 0.0)
                combined = 0.6 * semantic + 0.4 * lexical
                result['combined_score'] = combined
            
            # Sort by combined score
            lexical_results = sorted(
                lexical_results,
                key=lambda x: x['combined_score'],
                reverse=True
            )
            
            return lexical_results[:top_k]
        
        except Exception as e:
            print(f"⚠ Warning: Semantic reranking failed: {e}")
            return lexical_results[:top_k]
    
    def _attach_curriculum_data(self, results: List[Dict]) -> List[Dict]:
        """Attach full curriculum metadata to results."""
        final_results = []
        
        for result in results:
            ss_id = result['small_step_id']
            curriculum_data = self.curriculum_index.get_curriculum_row(ss_id)
            
            if curriculum_data:
                result.update({
                    'topic': curriculum_data.get('topic', ''),
                    'small_step_name': curriculum_data.get('small_step_name', ''),
                    'ss_desc': curriculum_data.get('ss_desc', ''),
                    'ss_wr_desc': curriculum_data.get('ss_wr_desc', ''),
                    'year': curriculum_data.get('year', ''),
                    'age': curriculum_data.get('age', ''),
                    'term': curriculum_data.get('term', ''),
                    'difficulty': curriculum_data.get('difficulty', ''),
                })
                final_results.append(result)
        
        return final_results


def search_curriculum(
    curriculum_index: CurriculumIndex,
    query: str,
    epoch_name: Optional[str] = None,
    embeddings_path: Optional[str] = None,
    use_semantic: bool = True,
    top_k: int = 10,
) -> List[Dict]:
    """
    Convenience function: search curriculum with optional epoch filtering.
    
    Args:
        curriculum_index: CurriculumIndex instance
        query: Search query
        epoch_name: Optional epoch to filter by
        embeddings_path: Path to precomputed embeddings
        use_semantic: Whether to use semantic reranking
        top_k: Number of results
    
    Returns:
        List of search results
    """
    # Initialize search engine (cached per session in real usage)
    engine = SearchEngine(
        curriculum_index,
        embeddings_path=embeddings_path,
        use_semantic=use_semantic,
    )
    
    # If epoch specified, filter searchable text before search
    if epoch_name and epoch_name != 'All':
        # TODO: Implement epoch filtering in search
        pass
    
    # Run search
    results = engine.search(query, top_k=top_k)
    
    return results
