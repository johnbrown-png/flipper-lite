"""
Query Embedding Generator

Convert user search queries into vector embeddings using the same
text-embedding-3-large model used for video transcripts.

This module can be used standalone or imported into other applications.
"""

import os
import numpy as np
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv


class QueryEmbedder:
    """Generate embeddings for user search queries"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-large",
        dimensions: int = 3072
    ):
        """
        Initialize the query embedder
        
        Args:
            api_key: OpenAI API key (if None, loads from environment)
            model: Embedding model name
            dimensions: Vector dimensions (must match FAISS index)
        """
        if api_key is None:
            load_dotenv()
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key or api_key == 'your_api_key_here':
            raise ValueError("OpenAI API key not provided or not found in environment")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
        
        print("Query Embedder initialized")
        print(f"  Model: {model}")
        print(f"  Dimensions: {dimensions}")
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        Convert a search query into a vector embedding
        
        Args:
            query: User search query string
        
        Returns:
            NumPy array (float32) with shape (1, dimensions)
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        try:
            # Generate embedding using OpenAI API
            response = self.client.embeddings.create(
                model=self.model,
                input=query.strip(),
                dimensions=self.dimensions
            )
            
            # Extract embedding and convert to float32 NumPy array
            embedding = response.data[0].embedding
            embedding_array = np.array([embedding]).astype('float32')
            
            return embedding_array
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}")
    
    def embed_batch(self, queries: list[str]) -> np.ndarray:
        """
        Convert multiple search queries into embeddings (batch processing)
        
        Args:
            queries: List of query strings
        
        Returns:
            NumPy array (float32) with shape (n_queries, dimensions)
        """
        if not queries:
            raise ValueError("Queries list cannot be empty")
        
        # Filter out empty queries
        valid_queries = [q.strip() for q in queries if q and q.strip()]
        
        if not valid_queries:
            raise ValueError("No valid queries provided")
        
        try:
            # Generate embeddings using OpenAI API (batch)
            response = self.client.embeddings.create(
                model=self.model,
                input=valid_queries,
                dimensions=self.dimensions
            )
            
            # Extract embeddings and convert to float32 NumPy array
            embeddings = [item.embedding for item in response.data]
            embeddings_array = np.array(embeddings).astype('float32')
            
            return embeddings_array
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate batch embeddings: {e}")


def main():
    """Main entry point for standalone usage"""
    print("=" * 80)
    print("Query Embedding Generator")
    print("=" * 80)
    print()
    
    try:
        # Initialize embedder
        embedder = QueryEmbedder()
        print()
        
        # Interactive mode
        print("Enter search queries to generate embeddings")
        print("(Type 'quit' to exit, 'batch' for batch mode)")
        print()
        
        while True:
            query = input("🔍 Search query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            if query.lower() == 'batch':
                print("\n📦 Batch Mode - Enter queries (empty line to finish):")
                queries = []
                while True:
                    q = input(f"  Query {len(queries) + 1}: ").strip()
                    if not q:
                        break
                    queries.append(q)
                
                if queries:
                    print(f"\n⏳ Generating embeddings for {len(queries)} queries...")
                    embeddings = embedder.embed_batch(queries)
                    print("Generated embeddings")
                    print(f"  Shape: {embeddings.shape}")
                    print(f"  Dtype: {embeddings.dtype}")
                    print(f"  Memory: {embeddings.nbytes / 1024:.2f} KB")
                    
                    # Show first few values of first embedding
                    print(f"\n  First embedding sample (first 5 values):")
                    print(f"  {embeddings[0][:5]}")
                else:
                    print("  No queries entered")
                
                print()
                continue
            
            if not query:
                continue
            
            # Generate embedding
            print(f"⏳ Generating embedding...")
            embedding = embedder.embed_query(query)
            
            print("Embedding generated successfully")
            print(f"  Shape: {embedding.shape}")
            print(f"  Dtype: {embedding.dtype}")
            print(f"  Dimensions: {embedding.shape[1]}")
            print(f"  Memory: {embedding.nbytes / 1024:.2f} KB")
            
            # Show first few values
            print(f"\n  Sample (first 10 values):")
            print(f"  {embedding[0][:10]}")
            print()
    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == '__main__':
    main()
