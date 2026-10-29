"""
Complete Data Pipeline - Extract, Chunk, Embed, and Index

This script runs the complete data pipeline:
1. Extract captions from YouTube videos
2. Chunk the transcripts
3. Generate embeddings
4. Build/update FAISS index

Run this whenever you want to add new videos to the search index.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.config import *
from data_pipeline.caption_extractor import YouTubeCaptionExtractor
from data_pipeline.chunker import TranscriptChunker
from data_pipeline.embedder import EmbeddingGenerator
from data_pipeline.indexer import FAISSIndexBuilder


def run_pipeline(
    extract_captions: bool = True,
    chunk_transcripts: bool = True,
    generate_embeddings: bool = True,
    build_index: bool = True,
    incremental_index: bool = True,
    max_videos: int = None,
    no_duration_limit: bool = False
):
    """
    Run the complete data pipeline
    
    Args:
        extract_captions: Whether to extract new captions
        chunk_transcripts: Whether to chunk transcripts
        generate_embeddings: Whether to generate embeddings
        build_index: Whether to build/update FAISS index
        incremental_index: If True, add to existing index (fast). If False, rebuild from scratch
        max_videos: Maximum number of videos to process (None = use config)
        no_duration_limit: If True, don't filter by video duration
    """
    print("=" * 80)
    print("NUMBERBLOCKS DATA PIPELINE")
    print("=" * 80)
    
    # Ensure directories exist
    ensure_directories()
    
    # Validate configuration
    validate_config()
    
    max_vids = max_videos if max_videos is not None else MAX_VIDEOS_PER_CHANNEL
    
    # Step 1: Extract Captions
    if extract_captions:
        print("\n" + "=" * 80)
        print("STEP 1: EXTRACTING CAPTIONS FROM YOUTUBE")
        print("=" * 80)
        
        extractor = YouTubeCaptionExtractor(
            api_key=YOUTUBE_API_KEY,
            output_dir=str(CAPTIONS_DIR),
            cache_file=str(API_CACHE_FILE),
            delay_between_videos=DELAY_BETWEEN_VIDEOS,
            random_delay_range=(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX),
            videos_per_batch=VIDEOS_PER_BATCH,
            break_duration_range=(BREAK_DURATION_MIN, BREAK_DURATION_MAX)
        )
        
        print(f"  ℹ Rate limiting: {RANDOM_DELAY_MIN}-{RANDOM_DELAY_MAX}s randomized delay between videos")
        print(f"  ℹ Session breaks: Every {VIDEOS_PER_BATCH} videos, pause for {BREAK_DURATION_MIN/60:.1f}-{BREAK_DURATION_MAX/60:.1f} minutes")
        print(f"    (approximately {60/((RANDOM_DELAY_MIN+RANDOM_DELAY_MAX)/2):.1f} videos per minute)")
        
        # Set duration limit
        if no_duration_limit:
            extractor.max_video_duration = None
        else:
            extractor.max_video_duration = MAX_VIDEO_DURATION
        
        extractor.run_pipeline(
            csv_path=str(CHANNELS_CSV),
            max_videos_per_channel=max_vids,
            auto_exclude_downloaded=True
        )
        
        print(f"\n✓ Caption extraction completed")
    else:
        print("\n⊘ Skipping caption extraction")
    
    # Step 2: Chunk Transcripts
    if chunk_transcripts:
        print("\n" + "=" * 80)
        print("STEP 2: CHUNKING TRANSCRIPTS")
        print("=" * 80)
        
        chunker = TranscriptChunker(
            input_dir=str(CAPTIONS_DIR),
            output_dir=str(CHUNKED_DIR),
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        
        stats = chunker.process_all_captions()
        
        print(f"\n✓ Chunking completed: {stats['files_processed']} files, {stats['total_chunks']} chunks")
    else:
        print("\n⊘ Skipping chunking")
    
    # Step 3: Generate Embeddings
    if generate_embeddings:
        print("\n" + "=" * 80)
        print("STEP 3: GENERATING EMBEDDINGS")
        print("=" * 80)
        
        embedder = EmbeddingGenerator(
            api_key=OPENAI_API_KEY,
            input_dir=str(CHUNKED_DIR),
            output_dir=str(EMBEDDINGS_DIR),
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS
        )
        
        stats = embedder.process_all_chunks()
        
        print(f"\n✓ Embedding generation completed: {stats['files_processed']} files, {stats['total_embeddings']} embeddings")
    else:
        print("\n⊘ Skipping embedding generation")
    
    # Step 4: Build FAISS Index
    if build_index:
        print("\n" + "=" * 80)
        index_mode = "INCREMENTALLY UPDATING" if incremental_index else "REBUILDING"
        print(f"STEP 4: {index_mode} FAISS INDEX")
        print("=" * 80)
        
        indexer = FAISSIndexBuilder(
            embeddings_dir=str(EMBEDDINGS_DIR),
            output_dir=str(FAISS_INDEX_DIR),
            dimension=EMBEDDING_DIMENSIONS
        )
        
        # Use incremental update by default (much faster for small batches!)
        stats = indexer.build_index(force_rebuild=not incremental_index)
        
        if 'vectors_added' in stats:
            print(f"\n✓ FAISS index updated: +{stats['vectors_added']} vectors (total: {stats['total_vectors']})")
        else:
            print(f"\n✓ FAISS index built: {stats['total_vectors']} vectors indexed")
        print(f"  Index saved to: {FAISS_INDEX_DIR}")
    else:
        print("\n⊘ Skipping FAISS index building")
    
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print(f"\nData locations:")
    print(f"  Captions:    {CAPTIONS_DIR}")

    print(f"  Chunks:      {CHUNKED_DIR}")
    print(f"  Embeddings:  {EMBEDDINGS_DIR}")
    print(f"  Index:       {FAISS_INDEX_DIR}")
    print("\nYou can now run the search app to query the index!")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the Numberblocks data pipeline")
    parser.add_argument("--skip-extract", action="store_true", help="Skip caption extraction")
    parser.add_argument("--skip-chunk", action="store_true", help="Skip chunking")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation")
    parser.add_argument("--skip-index", action="store_true", help="Skip FAISS index building")
    parser.add_argument("--rebuild-index", action="store_true", help="Force full index rebuild (slower, normally not needed)")
    parser.add_argument("--max-videos", type=int, help="Maximum videos to extract")
    parser.add_argument("--no-duration-limit", action="store_true", help="Don't filter videos by duration")
    parser.add_argument("--extract-only", action="store_true", help="Only extract captions")
    parser.add_argument("--index-only", action="store_true", help="Only run chunking, embedding, and indexing")
    
    args = parser.parse_args()
    
    # Handle quick modes
    if args.extract_only:
        run_pipeline(
            extract_captions=True,
            chunk_transcripts=False,
            generate_embeddings=False,
            build_index=False,
            max_videos=args.max_videos,
            no_duration_limit=args.no_duration_limit
        )
    elif args.index_only:
        run_pipeline(
            extract_captions=False,
            chunk_transcripts=True,
            generate_embeddings=True,
            build_index=True,
            incremental_index=not args.rebuild_index
        )
    else:
        run_pipeline(
            extract_captions=not args.skip_extract,
            chunk_transcripts=not args.skip_chunk,
            generate_embeddings=not args.skip_embed,
            build_index=not args.skip_index,
            incremental_index=not args.rebuild_index,
            max_videos=args.max_videos,
            no_duration_limit=args.no_duration_limit
        )
