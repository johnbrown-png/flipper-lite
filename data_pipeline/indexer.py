"""
Prepare embeddings for FAISS vector search index.

This script:
1. Loads embeddings from JSON
2. Converts to NumPy arrays with float32 precision
3. Creates FAISS index
4. Saves index and metadata for retrieval
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import faiss


class FAISSIndexBuilder:
    """Build and manage FAISS index for vector search"""
    
    def __init__(self, embeddings_dir: str = None, output_dir: str = None, dimension: int = 3072):
        """
        Initialize the FAISS index builder
        
        Args:
            embeddings_dir: Directory containing embedding files
            output_dir: Directory to save FAISS index
            dimension: Vector dimension (3072 for text-embedding-3-large)
        """
        self.embeddings_dir = Path(embeddings_dir) if embeddings_dir else None
        self.output_dir = Path(output_dir) if output_dir else None
        self.dimension = dimension
        self.index = None
        self.metadata = []
        
        print(f"✓ Initialized FAISS index builder")
        print(f"  Dimension: {dimension}")
    
    def load_embeddings(self, json_path: Path) -> Tuple[np.ndarray, List[Dict]]:
        """
        Load embeddings from consolidated JSON file
        
        Args:
            json_path: Path to embeddings JSON file
        
        Returns:
            Tuple of (embeddings array, metadata list)
        """
        print(f"\n📄 Loading embeddings from: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        embeddings_list = []
        metadata_list = []
        
        for item in data['embeddings']:
            # Extract embedding vector
            embedding = item['embedding']
            embeddings_list.append(embedding)
            
            # Store metadata (without the large embedding vector)
            metadata_list.append(item['metadata'])
        
        # Convert to NumPy array with float32 precision
        embeddings_array = np.array(embeddings_list).astype('float32')
        
        print(f"  ✓ Loaded {len(embeddings_list)} embeddings")
        print(f"  ✓ Array shape: {embeddings_array.shape}")
        print(f"  ✓ Array dtype: {embeddings_array.dtype}")
        print(f"  ✓ Memory size: {embeddings_array.nbytes / (1024**2):.2f} MB")
        
        return embeddings_array, metadata_list
    
    def create_index(
        self,
        embeddings: np.ndarray,
        index_type: str = "Flat"
    ) -> faiss.Index:
        """
        Create FAISS index
        
        Args:
            embeddings: NumPy array of embeddings (float32)
            index_type: Type of FAISS index
                - "Flat": Exact search (best quality, slower for large datasets)
                - "IVF": Inverted file index (faster, slight quality trade-off)
                - "HNSW": Hierarchical NSW (fast approximate search)
        
        Returns:
            FAISS index
        """
        print(f"\n🔧 Creating FAISS index: {index_type}")
        
        n_vectors, dimension = embeddings.shape
        
        if index_type == "Flat":
            # Exact L2 distance search (best for small to medium datasets)
            index = faiss.IndexFlatL2(dimension)
            
        elif index_type == "IVF":
            # Inverted file index with 100 clusters
            n_clusters = min(100, n_vectors // 10)
            quantizer = faiss.IndexFlatL2(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, n_clusters)
            
            # Train the index
            print(f"  → Training IVF index with {n_clusters} clusters...")
            index.train(embeddings)
            
        elif index_type == "HNSW":
            # HNSW index (fast approximate nearest neighbor)
            index = faiss.IndexHNSWFlat(dimension, 32)  # 32 = number of links
            index.hnsw.efConstruction = 40
            
        else:
            raise ValueError(f"Unknown index type: {index_type}")
        
        # Add vectors to index
        print(f"  → Adding {n_vectors} vectors to index...")
        index.add(embeddings)
        
        print(f"  ✓ Index created successfully")
        print(f"  ✓ Total vectors: {index.ntotal}")
        
        return index
    
    def build_from_file(
        self,
        embeddings_file: Path,
        index_type: str = "Flat"
    ) -> Tuple[faiss.Index, List[Dict]]:
        """
        Build FAISS index from embeddings file
        
        Args:
            embeddings_file: Path to consolidated embeddings JSON
            index_type: Type of FAISS index to create
        
        Returns:
            Tuple of (FAISS index, metadata list)
        """
        # Load embeddings
        embeddings, metadata = self.load_embeddings(embeddings_file)
        
        # Create index
        index = self.create_index(embeddings, index_type)
        
        self.index = index
        self.metadata = metadata
        
        return index, metadata
    
    def save_index(
        self,
        index: faiss.Index,
        metadata: List[Dict],
        output_dir: Path,
        index_name: str = "faiss_index"
    ):
        """
        Save FAISS index and metadata to disk
        
        Args:
            index: FAISS index to save
            metadata: Metadata list to save
            output_dir: Directory to save files
            index_name: Base name for output files
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Save FAISS index
        index_path = output_dir / f"{index_name}.index"
        faiss.write_index(index, str(index_path))
        print(f"\n💾 Saved FAISS index: {index_path}")
        
        # Save metadata as pickle
        metadata_path = output_dir / f"{index_name}_metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
        print(f"💾 Saved metadata: {metadata_path}")
        
        # Save metadata as JSON (human-readable)
        metadata_json_path = output_dir / f"{index_name}_metadata.json"
        with open(metadata_json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved metadata (JSON): {metadata_json_path}")
    
    def search(
        self,
        query_vector: np.ndarray,
        k: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search the index for nearest neighbors
        
        Args:
            query_vector: Query vector (1D array)
            k: Number of results to return
        
        Returns:
            Tuple of (distances, indices)
        """
        if self.index is None:
            raise ValueError("Index not built. Call build_from_file() first.")
        
        # Ensure query is 2D array with float32
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        query_vector = query_vector.astype('float32')
        
        # Search
        distances, indices = self.index.search(query_vector, k)
        
        return distances, indices
    
    def get_results_with_metadata(
        self,
        distances: np.ndarray,
        indices: np.ndarray
    ) -> List[Dict]:
        """
        Get search results with metadata
        
        Args:
            distances: Distance array from search
            indices: Index array from search
        
        Returns:
            List of result dictionaries with metadata and scores
        """
        results = []
        
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # FAISS returns -1 for invalid results
                continue
            
            result = {
                'rank': i + 1,
                'distance': float(dist),
                'metadata': self.metadata[idx]
            }
            results.append(result)
        
        return results
    
    def load_existing_index(self) -> bool:
        """
        Load existing FAISS index and metadata from output directory
        
        Returns:
            True if index was loaded, False if it doesn't exist
        """
        if not self.output_dir:
            raise ValueError("output_dir must be set")
        
        index_path = self.output_dir / "faiss_index.bin"
        metadata_path = self.output_dir / "faiss_index_metadata.json"
        
        if not index_path.exists() or not metadata_path.exists():
            print(f"ℹ️  No existing index found at {index_path}")
            return False
        
        print(f"\n📂 Loading existing FAISS index from: {index_path}")
        self.index = faiss.read_index(str(index_path))
        print(f"  ✓ Loaded index with {self.index.ntotal} vectors")
        
        print(f"📂 Loading metadata from: {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata_json = json.load(f)
            self.metadata = metadata_json['metadata']
        print(f"  ✓ Loaded {len(self.metadata)} metadata entries")
        
        return True
    
    def add_embeddings_incremental(
        self,
        embeddings_file: Path,
        force_rebuild: bool = False
    ) -> Dict:
        """
        Add new embeddings to existing index incrementally (no rebuild required!)
        
        This method:
        1. Loads existing index (or creates new one)
        2. Adds only the new embeddings
        3. Appends new metadata
        4. Saves updated index
        
        Args:
            embeddings_file: Path to new embeddings JSON file
            force_rebuild: If True, rebuild entire index instead of incremental add
        
        Returns:
            Dictionary with statistics
        """
        if not self.output_dir:
            raise ValueError("output_dir must be set")
        
        print("\n" + "=" * 70)
        print("📥 Incremental Index Update")
        print("=" * 70)
        
        # Try to load existing index
        index_exists = self.load_existing_index()
        
        if force_rebuild or not index_exists:
            if force_rebuild:
                print("\n🔄 Force rebuild requested")
            else:
                print("\n🆕 No existing index found, creating new one")
            
            # Create new index
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
        
        initial_count = self.index.ntotal if self.index else 0
        
        # Load new embeddings
        print(f"\n📄 Loading new embeddings from: {embeddings_file}")
        with open(embeddings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        new_embeddings = []
        new_metadata = []
        
        for item in data['embeddings']:
            new_embeddings.append(item['embedding'])
            new_metadata.append(item['metadata'])
        
        # Convert to numpy array
        embeddings_array = np.array(new_embeddings, dtype='float32')
        
        print(f"  ✓ Loaded {len(new_embeddings)} new embeddings")
        print(f"  ✓ Array shape: {embeddings_array.shape}")
        
        # Add to index (this is fast - no rebuild required!)
        print(f"\n➕ Adding {len(new_embeddings)} vectors to index...")
        self.index.add(embeddings_array)
        
        # Append metadata
        self.metadata.extend(new_metadata)
        
        print(f"  ✓ Index updated: {initial_count} → {self.index.ntotal} vectors")
        
        # Save updated index
        self._save_index_and_metadata()
        
        # Calculate stats
        unique_video_ids = set()
        for meta in self.metadata:
            if 'video_id' in meta:
                unique_video_ids.add(meta['video_id'])
        
        return {
            'total_vectors': len(self.metadata),
            'unique_videos': len(unique_video_ids),
            'vectors_added': len(new_embeddings),
            'initial_vectors': initial_count
        }
    
    def _save_index_and_metadata(self):
        """Internal method to save index and metadata"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        index_path = self.output_dir / "faiss_index.bin"
        faiss.write_index(self.index, str(index_path))
        
        # Save metadata as JSON
        metadata_path = self.output_dir / "faiss_index_metadata.json"
        metadata_output = {
            'metadata': self.metadata,
            'dimension': self.dimension,
            'total_vectors': len(self.metadata),
            'index_type': 'Flat'
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_output, f, indent=2, ensure_ascii=False)
        
        print(f"  💾 Saved index: {index_path}")
        print(f"  💾 Saved metadata: {metadata_path}")

    def build_index(self, force_rebuild: bool = False):
        """
        Build FAISS index from embeddings directory
        
        If an index already exists and force_rebuild=False, this will
        incrementally add ONLY new embeddings. Otherwise, rebuilds from scratch.
        
        Args:
            force_rebuild: If True, rebuild entire index from scratch
        
        Returns:
            Dictionary with indexing statistics
        """
        if not self.embeddings_dir or not self.output_dir:
            raise ValueError("embeddings_dir and output_dir must be set")
        
        embedding_files = list(self.embeddings_dir.glob('*_embeddings.json'))
        
        if not embedding_files:
            raise FileNotFoundError(f"No embedding files found in {self.embeddings_dir}")
        
        print(f"\n📄 Found {len(embedding_files)} embedding files")
        
        # Try to load existing index
        index_exists = self.load_existing_index() if not force_rebuild else False
        
        if force_rebuild or not index_exists:
            # Full rebuild
            print("\n🔄 Building index from scratch...")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            indexed_video_ids = set()
        else:
            print("\n➕ Incrementally updating existing index...")
            # Track which videos are already indexed to avoid duplicates
            indexed_video_ids = set()
            for meta in self.metadata:
                if 'video_id' in meta:
                    indexed_video_ids.add(meta['video_id'])
            print(f"  ℹ️  Found {len(indexed_video_ids)} videos already indexed")
        
        initial_count = self.index.ntotal
        
        # Filter to only NEW embedding files (skip already indexed videos)
        new_files = []
        skipped_files = []
        for emb_file in embedding_files:
            # Extract video_id from filename (e.g., "abc123_embeddings.json" -> "abc123")
            video_id = emb_file.stem.replace('_embeddings', '')
            if video_id not in indexed_video_ids:
                new_files.append(emb_file)
            else:
                skipped_files.append(emb_file)
        
        if skipped_files:
            print(f"  ⏭️  Skipping {len(skipped_files)} already-indexed videos")
        print(f"  📥 Processing {len(new_files)} new videos")
        
        if not new_files:
            print("  ℹ️  No new videos to index")
            # Calculate stats and return
            unique_video_ids = set()
            for meta in self.metadata:
                if 'video_id' in meta:
                    unique_video_ids.add(meta['video_id'])
            return {
                'total_vectors': len(self.metadata),
                'unique_videos': len(unique_video_ids),
                'vectors_added': 0
            }
        
        # Process ONLY new files in batches to reduce memory usage
        BATCH_SIZE = 1000
        batch_embeddings = []
        new_metadata = []
        
        for file_idx, emb_file in enumerate(new_files, 1):
            print(f"  Processing file {file_idx}/{len(new_files)}: {emb_file.name}")
            
            with open(emb_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data['embeddings']:
                batch_embeddings.append(item['embedding'])
                new_metadata.append(item['metadata'])
                
                # When batch is full, add to index and clear
                if len(batch_embeddings) >= BATCH_SIZE:
                    batch_array = np.array(batch_embeddings, dtype='float32')
                    self.index.add(batch_array)
                    batch_embeddings = []
                    print(f"    Added batch, total vectors: {self.index.ntotal}")
        
        # Add any remaining embeddings
        if batch_embeddings:
            batch_array = np.array(batch_embeddings, dtype='float32')
            self.index.add(batch_array)
        
        # Update metadata (replace or extend based on rebuild)
        if force_rebuild or not index_exists:
            self.metadata = new_metadata
        else:
            self.metadata.extend(new_metadata)
        
        print(f"✓ Index updated: {initial_count} → {self.index.ntotal} vectors")
        
        # Save index
        self._save_index_and_metadata()
        
        # Calculate unique videos
        unique_video_ids = set()
        for meta in self.metadata:
            if 'video_id' in meta:
                unique_video_ids.add(meta['video_id'])
        
        return {
            'total_vectors': len(self.metadata),
            'unique_videos': len(unique_video_ids),
            'vectors_added': self.index.ntotal - initial_count
        }


def load_index(
    index_path: Path,
    metadata_path: Path
) -> Tuple[faiss.Index, List[Dict]]:
    """
    Load a saved FAISS index and metadata
    
    Args:
        index_path: Path to FAISS index file
        metadata_path: Path to metadata pickle file
    
    Returns:
        Tuple of (FAISS index, metadata list)
    """
    print(f"\n📂 Loading FAISS index from: {index_path}")
    index = faiss.read_index(str(index_path))
    print(f"  ✓ Loaded index with {index.ntotal} vectors")
    
    print(f"📂 Loading metadata from: {metadata_path}")
    with open(metadata_path, 'rb') as f:
        metadata = pickle.load(f)
    print(f"  ✓ Loaded {len(metadata)} metadata entries")
    
    return index, metadata


def main():
    """Main entry point"""
    print("=" * 70)
    print("FAISS Vector Index Builder")
    print("=" * 70)
    
    # Configuration
    embeddings_file = Path('embeddings_consolidated.json')
    output_dir = Path('faiss_index')
    index_type = "Flat"  # Options: "Flat", "IVF", "HNSW"
    
    if not embeddings_file.exists():
        print(f"\n✗ Error: Embeddings file not found: {embeddings_file}")
        return
    
    # Build index
    builder = FAISSIndexBuilder(dimension=3072)
    index, metadata = builder.build_from_file(embeddings_file, index_type)
    
    # Save index
    builder.save_index(index, metadata, output_dir)
    
    # Print statistics
    print("\n" + "=" * 70)
    print("✓ FAISS Index Build Complete!")
    print(f"  Total vectors: {index.ntotal}")
    print(f"  Dimension: {builder.dimension}")
    print(f"  Index type: {index_type}")
    print(f"  Output directory: {output_dir.absolute()}")
    print("=" * 70)
    
    # Example: Test search
    print("\n📝 Testing search with first embedding...")
    test_query = np.array(metadata[0]['embedding'] if 'embedding' in metadata[0] else [0] * 3072).astype('float32')
    
    # Note: For actual queries, you'd generate embeddings from text using OpenAI API
    print("  (For real queries, generate embeddings from text using OpenAI API)")


if __name__ == '__main__':
    main()
