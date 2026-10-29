"""
Cleanup Long Videos Script

Removes videos longer than a specified duration from the entire pipeline:
- Caption files
- Chunked files
- Embedding files
- Extraction state records
- Rebuilds FAISS index

Usage: python cleanup_long_videos.py [--max-duration SECONDS] [--dry-run]
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse


class LongVideoCleanup:
    """Remove long videos from the pipeline"""
    
    def __init__(self, max_duration: int = 1200, dry_run: bool = False):
        """
        Initialize cleanup
        
        Args:
            max_duration: Maximum video duration in seconds (default 1200 = 20 minutes)
            dry_run: If True, only report what would be deleted without actually deleting
        """
        self.max_duration = max_duration
        self.dry_run = dry_run
        self.videos_to_remove = []
        self.stats = {
            'captions_removed': 0,
            'chunks_removed': 0,
            'embeddings_removed': 0,
            'total_duration_removed': 0
        }
        
    def find_long_videos(self):
        """Scan caption files to find videos exceeding max duration"""
        print(f"\n{'='*70}")
        print(f"SCANNING FOR VIDEOS LONGER THAN {self.max_duration} SECONDS ({self.max_duration/60:.1f} minutes)")
        print(f"{'='*70}\n")
        
        captions_dir = Path("data/captions_output")
        if not captions_dir.exists():
            print("❌ Captions directory not found")
            return
        
        # Scan all caption JSON files
        caption_files = list(captions_dir.rglob("*.json"))
        print(f"📹 Scanning {len(caption_files)} caption files...\n")
        
        for caption_file in caption_files:
            try:
                with open(caption_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                duration = data.get('duration', 0)
                video_id = data.get('video_id', '')
                title = data.get('title', 'Unknown')
                
                if duration > self.max_duration:
                    self.videos_to_remove.append({
                        'video_id': video_id,
                        'title': title,
                        'duration': duration,
                        'caption_file': caption_file
                    })
                    
            except Exception as e:
                print(f"⚠️  Error reading {caption_file.name}: {e}")
        
        # Sort by duration (longest first)
        self.videos_to_remove.sort(key=lambda x: x['duration'], reverse=True)
        
        # Report findings
        if self.videos_to_remove:
            print(f"🔍 Found {len(self.videos_to_remove)} videos exceeding {self.max_duration}s:\n")
            for i, video in enumerate(self.videos_to_remove, 1):
                duration_mins = video['duration'] / 60
                print(f"  {i}. {video['video_id']}")
                print(f"     Duration: {duration_mins:.1f} minutes ({video['duration']}s)")
                print(f"     Title: {video['title'][:70]}...")
                print()
        else:
            print(f"✅ No videos found exceeding {self.max_duration} seconds")
            
    def backup_extraction_state(self):
        """Backup extraction_state.json"""
        extraction_state = Path("extraction_state.json")
        if extraction_state.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = Path(f"extraction_state_backup_{timestamp}.json")
            
            if not self.dry_run:
                shutil.copy2(extraction_state, backup_path)
                print(f"💾 Backed up extraction state to: {backup_path}")
            else:
                print(f"[DRY RUN] Would backup extraction state to: {backup_path}")
    
    def remove_caption_files(self):
        """Remove caption files for long videos"""
        print(f"\n{'='*70}")
        print("REMOVING CAPTION FILES")
        print(f"{'='*70}\n")
        
        for video in self.videos_to_remove:
            caption_file = video['caption_file']
            txt_file = caption_file.with_suffix('.txt')
            
            if self.dry_run:
                print(f"[DRY RUN] Would remove: {caption_file.name}")
                if txt_file.exists():
                    print(f"[DRY RUN] Would remove: {txt_file.name}")
            else:
                if caption_file.exists():
                    caption_file.unlink()
                    print(f"✓ Removed: {caption_file.name}")
                    self.stats['captions_removed'] += 1
                
                if txt_file.exists():
                    txt_file.unlink()
                    print(f"✓ Removed: {txt_file.name}")
            
            self.stats['total_duration_removed'] += video['duration']
    
    def remove_chunked_files(self):
        """Remove chunked files for long videos"""
        print(f"\n{'='*70}")
        print("REMOVING CHUNKED FILES")
        print(f"{'='*70}\n")
        
        chunked_dir = Path("data/chunked_output")
        if not chunked_dir.exists():
            print("ℹ️  No chunked_output directory found")
            return
        
        for video in self.videos_to_remove:
            video_id = video['video_id']
            chunked_file = chunked_dir / f"{video_id}_chunked.json"
            
            if chunked_file.exists():
                if self.dry_run:
                    print(f"[DRY RUN] Would remove: {chunked_file.name}")
                else:
                    chunked_file.unlink()
                    print(f"✓ Removed: {chunked_file.name}")
                    self.stats['chunks_removed'] += 1
    
    def remove_embedding_files(self):
        """Remove embedding files for long videos"""
        print(f"\n{'='*70}")
        print("REMOVING EMBEDDING FILES")
        print(f"{'='*70}\n")
        
        embeddings_dir = Path("data/embeddings_output")
        if not embeddings_dir.exists():
            print("ℹ️  No embeddings_output directory found")
            return
        
        for video in self.videos_to_remove:
            video_id = video['video_id']
            embedding_file = embeddings_dir / f"{video_id}_embeddings.json"
            
            if embedding_file.exists():
                if self.dry_run:
                    print(f"[DRY RUN] Would remove: {embedding_file.name}")
                else:
                    embedding_file.unlink()
                    print(f"✓ Removed: {embedding_file.name}")
                    self.stats['embeddings_removed'] += 1
    
    def update_extraction_state(self):
        """Remove entries from extraction_state.json"""
        print(f"\n{'='*70}")
        print("UPDATING EXTRACTION STATE")
        print(f"{'='*70}\n")
        
        extraction_state_path = Path("extraction_state.json")
        if not extraction_state_path.exists():
            print("ℹ️  No extraction_state.json found")
            return
        
        with open(extraction_state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        video_ids_to_remove = {v['video_id'] for v in self.videos_to_remove}
        removed_count = 0
        
        # Remove from videos_extracted
        for channel_id, videos in state.get('videos_extracted', {}).items():
            original_count = len(videos)
            state['videos_extracted'][channel_id] = [
                v for v in videos if v.get('video_id') not in video_ids_to_remove
            ]
            removed = original_count - len(state['videos_extracted'][channel_id])
            if removed > 0:
                removed_count += removed
                if self.dry_run:
                    print(f"[DRY RUN] Would remove {removed} videos from channel {channel_id}")
                else:
                    print(f"✓ Removed {removed} videos from channel {channel_id}")
        
        if not self.dry_run and removed_count > 0:
            with open(extraction_state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print(f"\n✓ Updated extraction_state.json")
    
    def rebuild_faiss_index(self):
        """Rebuild FAISS index without the removed videos"""
        print(f"\n{'='*70}")
        print("REBUILDING FAISS INDEX")
        print(f"{'='*70}\n")
        
        if self.dry_run:
            print("[DRY RUN] Would rebuild FAISS index from remaining embeddings")
            print("           Run: python -m data_pipeline.indexer")
            return
        
        print("🔧 Rebuilding FAISS index from remaining embeddings...")
        
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from data_pipeline.indexer import FAISSIndexBuilder
            
            indexer = FAISSIndexBuilder(
                embeddings_dir="data/embeddings_output",
                output_dir="data/faiss_index",
                dimension=3072
            )
            
            stats = indexer.build_index()
            
            print(f"\n✅ FAISS index rebuilt successfully!")
            print(f"   Total vectors: {stats['total_vectors']}")
            print(f"   Unique videos: {stats['unique_videos']}")
            
        except Exception as e:
            print(f"\n⚠️  Error rebuilding index: {e}")
            print("   You can manually rebuild with: python -m data_pipeline.run_pipeline --extract-only=false --chunk-only=false --embed-only=false")
    
    def print_summary(self):
        """Print cleanup summary"""
        print(f"\n{'='*70}")
        print("CLEANUP SUMMARY")
        print(f"{'='*70}\n")
        
        if self.dry_run:
            print("🔍 DRY RUN COMPLETE - No files were actually deleted\n")
        else:
            print("✅ CLEANUP COMPLETE\n")
        
        print(f"Videos identified: {len(self.videos_to_remove)}")
        print(f"Caption files removed: {self.stats['captions_removed']}")
        print(f"Chunked files removed: {self.stats['chunks_removed']}")
        print(f"Embedding files removed: {self.stats['embeddings_removed']}")
        
        total_hours = self.stats['total_duration_removed'] / 3600
        print(f"Total duration removed: {total_hours:.1f} hours ({self.stats['total_duration_removed']} seconds)")
        
        if self.videos_to_remove:
            print(f"\nRemoved videos:")
            for video in self.videos_to_remove:
                print(f"  • {video['video_id']} ({video['duration']/60:.1f} min)")
    
    def run(self):
        """Execute the cleanup process"""
        print(f"\n{'='*70}")
        print("LONG VIDEO CLEANUP TOOL")
        print(f"{'='*70}")
        print(f"Max duration: {self.max_duration} seconds ({self.max_duration/60:.1f} minutes)")
        print(f"Mode: {'DRY RUN (no changes will be made)' if self.dry_run else 'LIVE (files will be deleted)'}")
        print(f"{'='*70}")
        
        # Step 1: Find long videos
        self.find_long_videos()
        
        if not self.videos_to_remove:
            print("\n✅ No cleanup needed!")
            return
        
        # Confirm if not dry run
        if not self.dry_run:
            print(f"\n⚠️  WARNING: This will permanently delete {len(self.videos_to_remove)} videos and their data!")
            response = input("\nContinue? (yes/no): ")
            if response.lower() != 'yes':
                print("\n❌ Cleanup cancelled")
                return
        
        # Step 2: Backup
        self.backup_extraction_state()
        
        # Step 3: Remove files
        self.remove_caption_files()
        self.remove_chunked_files()
        self.remove_embedding_files()
        
        # Step 4: Update extraction state
        self.update_extraction_state()
        
        # Step 5: Rebuild index
        self.rebuild_faiss_index()
        
        # Step 6: Summary
        self.print_summary()
        
        print(f"\n{'='*70}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Remove videos longer than specified duration from pipeline"
    )
    parser.add_argument(
        '--max-duration',
        type=int,
        default=1200,
        help='Maximum video duration in seconds (default: 1200 = 20 minutes)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    cleanup = LongVideoCleanup(
        max_duration=args.max_duration,
        dry_run=args.dry_run
    )
    cleanup.run()


if __name__ == "__main__":
    main()
