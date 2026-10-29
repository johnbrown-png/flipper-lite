"""
Diagnostic Report Generator - Analyze pipeline status without YouTube API calls
"""
import os
import json
from pathlib import Path

def analyze_pipeline_status():
    """Analyze the complete pipeline status"""
    
    print("=" * 70)
    print("YOUTUBE CAPTION EXTRACTION PIPELINE - DIAGNOSTIC REPORT")
    print("=" * 70)
    print()
    
    # 1. Check captions
    captions_dir = Path("captions_output/numberblocks")
    caption_files = list(captions_dir.glob("*.json")) if captions_dir.exists() else []
    caption_video_ids = [f.stem.split('_')[-1] for f in caption_files]
    
    print(f"📹 STEP 1: Caption Extraction")
    print(f"   Extracted captions: {len(caption_files)} videos")
    if caption_files:
        print(f"   Latest: {caption_files[-1].stem[:60]}...")
    print()
    
    # 2. Check chunked
    chunked_dir = Path("data/chunked_output")
    chunked_files = list(chunked_dir.glob("*_chunked.json")) if chunked_dir.exists() else []
    chunked_video_ids = [f.stem.replace('_chunked', '') for f in chunked_files]
    
    print(f"✂️  STEP 2: Chunking")
    print(f"   Chunked files: {len(chunked_files)} videos")
    
    # Check which captions need chunking
    captions_not_chunked = [vid for vid in caption_video_ids if vid not in chunked_video_ids]
    chunked_but_no_captions = [vid for vid in chunked_video_ids if vid not in caption_video_ids]
    
    if captions_not_chunked:
        print(f"   ⚠️  Needs chunking: {len(captions_not_chunked)} videos")
        print(f"      Example: {captions_not_chunked[0] if captions_not_chunked else 'N/A'}")
    else:
        print(f"   ✓ All captions are chunked")
    
    if chunked_but_no_captions:
        print(f"   ℹ️  Extra chunked files: {len(chunked_but_no_captions)} (may be from deleted captions)")
    print()
    
    # 3. Check embeddings
    embeddings_dir = Path("data/embeddings_output")
    embedding_files = list(embeddings_dir.glob("*_embeddings.json")) if embeddings_dir.exists() else []
    embedding_video_ids = [f.stem.replace('_embeddings', '') for f in embedding_files]
    
    print(f"🔢 STEP 3: Embeddings")
    print(f"   Embedding files: {len(embedding_files)} videos")
    
    chunked_not_embedded = [vid for vid in chunked_video_ids if vid not in embedding_video_ids]
    
    if chunked_not_embedded:
        print(f"   ⚠️  Needs embeddings: {len(chunked_not_embedded)} videos")
        print(f"      Example: {chunked_not_embedded[0] if chunked_not_embedded else 'N/A'}")
    else:
        print(f"   ✓ All chunks have embeddings")
    print()
    
    # 4. Check FAISS index
    faiss_dir = Path("data/faiss_index")
    index_file = faiss_dir / "faiss_index.index"
    metadata_file = faiss_dir / "faiss_index_metadata.json"
    
    print(f"🔍 STEP 4: FAISS Search Index")
    if index_file.exists() and metadata_file.exists():
        print(f"   ✓ Index exists: {index_file.name}")
        
        # Read metadata to get vector count
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                total_vectors = len(metadata.get('chunks', []))
                unique_videos = len(set(chunk['video_id'] for chunk in metadata.get('chunks', [])))
                print(f"   Indexed vectors: {total_vectors}")
                print(f"   Unique videos: {unique_videos}")
                
                embedded_not_indexed = len(embedding_video_ids) - unique_videos
                if embedded_not_indexed > 0:
                    print(f"   ⚠️  Needs re-indexing: ~{embedded_not_indexed} videos")
                else:
                    print(f"   ✓ Index appears up to date")
        except Exception as e:
            print(f"   ⚠️  Could not read metadata: {e}")
    else:
        print(f"   ❌ Index missing - needs building")
    print()
    
    # Summary
    print("=" * 70)
    print("PIPELINE STATUS SUMMARY")
    print("=" * 70)
    
    pipeline_ok = True
    
    if captions_not_chunked:
        print(f"⚠️  ACTION NEEDED: Run 'python -m data_pipeline.run_pipeline --extract=false' to chunk {len(captions_not_chunked)} videos")
        pipeline_ok = False
    
    if chunked_not_embedded:
        print(f"⚠️  ACTION NEEDED: Run 'python -m data_pipeline.run_pipeline --extract=false --chunk=false' to embed {len(chunked_not_embedded)} videos")
        pipeline_ok = False
    
    if not index_file.exists():
        print(f"⚠️  ACTION NEEDED: Run 'python -m data_pipeline.run_pipeline --extract=false --chunk=false --embed=false' to create search index")
        pipeline_ok = False
    
    if pipeline_ok:
        print("✅ Pipeline is complete and up to date!")
        print(f"   You can search {len(embedding_video_ids)} videos using the search interface")
    
    print()
    
    # Check for potential issues
    print("=" * 70)
    print("POTENTIAL ISSUES CHECK")
    print("=" * 70)
    
    issues_found = False
    
    # Check for very small chunks
    if chunked_files:
        sample_chunked = chunked_files[0]
        try:
            with open(sample_chunked, 'r', encoding='utf-8') as f:
                sample_data = json.load(f)
                chunk_count = sample_data.get('total_chunks', 0)
                if chunk_count == 0:
                    print("⚠️  Sample video has 0 chunks - check chunking logic")
                    issues_found = True
        except:
            pass
    
    # Check for empty caption files
    if caption_files:
        try:
            sample_caption = caption_files[0]
            with open(sample_caption, 'r', encoding='utf-8') as f:
                sample_cap = json.load(f)
                if not sample_cap.get('captions'):
                    print("⚠️  Sample caption file has no captions - check extraction")
                    issues_found = True
        except:
            pass
    
    if not issues_found:
        print("✓ No obvious issues detected in sampled files")
    
    print()
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    
    if not caption_files:
        print("1. Run GUI to extract captions: python launch_gui.py")
    elif captions_not_chunked:
        print(f"1. Chunk the {len(captions_not_chunked)} new captions: python -m data_pipeline.run_pipeline --extract=false")
    elif chunked_not_embedded:
        print(f"1. Generate embeddings for {len(chunked_not_embedded)} chunks: python -m data_pipeline.run_pipeline --extract=false --chunk=false")
    elif not index_file.exists():
        print("1. Build search index: python -m data_pipeline.run_pipeline --extract=false --chunk=false --embed=false")
    else:
        print("1. Start searching: python search_demo.py")
        print("   OR run GUI: python launch_gui.py")
    
    print()

if __name__ == "__main__":
    analyze_pipeline_status()
