"""
Interactive script for deleting videos or channels from Flipper

Usage:
    python delete_content.py
    
Or use command-line options:
    python delete_content.py --video VIDEO_ID [--dry-run] [--rebuild-index]
    python delete_content.py --channel CHANNEL_ID [--dry-run] [--rebuild-index]
    python delete_content.py --batch CSV_FILE [--dry-run] [--rebuild-index]
"""

import sys
import pandas as pd
from pathlib import Path
from data_pipeline.deletion_manager import DataDeletionManager


def confirm_deletion(item_type: str, item_id: str, count: int = 1) -> bool:
    """Ask user to confirm deletion"""
    print(f"\n⚠️  WARNING: You are about to delete:")
    print(f"   Type: {item_type}")
    print(f"   ID: {item_id}")
    if count > 1:
        print(f"   Videos affected: {count}")
    print(f"\n   This will remove all associated data:")
    print(f"   - Caption files (.json, .txt)")
    print(f"   - Chunked transcripts")
    print(f"   - Embeddings")
    print(f"   - Metadata records")
    print(f"   - Search index entries")
    
    response = input(f"\n   Type 'DELETE' to confirm: ").strip()
    return response == 'DELETE'


def batch_delete_from_csv(csv_file: str, dry_run: bool = False, 
                          no_backup: bool = False, rebuild_index: bool = False,
                          skip_confirmation: bool = False) -> None:
    """Delete multiple videos from a CSV file
    
    Args:
        csv_file: Path to CSV file with 'video_id' column
        dry_run: Preview deletions without executing
        no_backup: Skip backup creation
        rebuild_index: Rebuild FAISS index after deletions
        skip_confirmation: Skip confirmation prompt
    """
    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_file}")
        sys.exit(1)
    
    # Read video IDs from CSV
    try:
        df = pd.read_csv(csv_path)
        
        # Support flexible column names
        if 'video_id' in df.columns:
            video_ids = df['video_id'].dropna().astype(str).tolist()
        elif len(df.columns) == 1:
            # If only one column, assume it's video IDs
            df = df.rename(columns={df.columns[0]: 'video_id'})
            video_ids = df.iloc[:, 0].dropna().astype(str).tolist()
        else:
            print(f"❌ CSV must have a 'video_id' column or be a single column")
            sys.exit(1)

        # Ensure optional context columns exist if queue was created by GUI QA.
        if "video_title" not in df.columns:
            df["video_title"] = ""
        if "channel" not in df.columns:
            df["channel"] = ""
        df["video_id"] = df["video_id"].astype(str).map(lambda value: value.strip())
        df = df[df["video_id"] != ""].copy()
        
        # Remove any whitespace
        video_ids = [vid.strip() for vid in video_ids if vid.strip()]
        
        if not video_ids:
            print(f"❌ No video IDs found in CSV file")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        sys.exit(1)
    
    print(f"\n📋 Loaded {len(video_ids)} video IDs from {csv_file}")
    
    # Preview mode or confirmation
    if dry_run:
        print(f"\n🔍 DRY RUN MODE - Previewing deletions...\n")
    elif not skip_confirmation:
        if not confirm_deletion("Batch", f"{len(video_ids)} videos", len(video_ids)):
            print("❌ Batch deletion cancelled")
            sys.exit(1)
    
    # Initialize deletion manager
    manager = DataDeletionManager(
        dry_run=dry_run,
        create_backup=not no_backup
    )
    
    # Delete each video
    print(f"\n🗑️  {'Previewing' if dry_run else 'Deleting'} {len(video_ids)} videos...\n")
    
    success_count = 0
    not_found_count = 0
    error_count = 0
    failed_video_ids: set[str] = set()
    
    for i, video_id in enumerate(video_ids, 1):
        print(f"[{i}/{len(video_ids)}] Processing: {video_id}")
        
        try:
            # Skip index rebuild for batch operations
            results = manager.delete_video(video_id, skip_index_rebuild=True)
            
            if results['success']:
                success_count += 1
            else:
                error_count += 1
                failed_video_ids.add(video_id)
                
            if not results.get('files_deleted') and not manager.get_video_info(video_id):
                not_found_count += 1
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            error_count += 1
            failed_video_ids.add(video_id)
    
    # Save deletion log
    manager.save_deletion_log()
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Batch Deletion Summary")
    print(f"{'='*60}")
    print(f"Total videos processed: {len(video_ids)}")
    print(f"Successfully deleted: {success_count}")
    print(f"Not found: {not_found_count}")
    print(f"Errors: {error_count}")
    print(f"{'='*60}\n")

    if not dry_run:
        if error_count == 0:
            # Queue semantics: after a fully successful batch, the queue should be empty.
            empty_queue_df = pd.DataFrame(columns=["video_id", "video_title", "channel"])
            empty_queue_df.to_csv(csv_path, index=False)
            print(f"🧹 Cleared delete queue: {csv_file}")
        else:
            pending_df = df[df["video_id"].isin(failed_video_ids)].copy()
            pending_df.to_csv(csv_path, index=False)
            print(f"⚠️  Kept {len(pending_df)} pending row(s) in queue due to errors")
    
    # Rebuild index if requested and not dry run
    if rebuild_index and not dry_run:
        print("🔄 Rebuilding FAISS index...")
        print("⚠️  IMPORTANT: Close Flipper and GUI first to free memory!")
        manager.rebuild_faiss_index()
        print("✅ FAISS index rebuilt")
    elif not dry_run:
        print("💡 TIP: Deletions use soft-delete (videos removed from metadata, not index)")
        print("   Index rebuild will be suggested when 5% of videos are deleted.")
        print("   To force rebuild now: python delete_content.py --batch FILE --rebuild-index")


def interactive_mode():
    """Interactive deletion interface"""
    print("="*60)
    print("Flipper Content Deletion Tool")
    print("="*60)
    print("\nWhat would you like to delete?")
    print("  1. Single video")
    print("  2. Entire channel")
    print("  3. Batch delete from CSV")
    print("  4. Preview deletions (dry run)")
    print("  5. Validate deletion")
    print("  6. Exit")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == '1':
        video_id = input("\nEnter video ID: ").strip()
        
        if not video_id:
            print("❌ Video ID required")
            return
        
        # Preview first
        print("\n🔍 Previewing deletion...")
        manager = DataDeletionManager(dry_run=True, create_backup=True)
        video_info = manager.get_video_info(video_id)
        
        if not video_info:
            print(f"❌ Video {video_id} not found in system")
            print(f"   (checked extraction_state.json, disk files, and video_inventory.csv)")
            return
        
        manager.delete_video(video_id)
        
        # Confirm
        if confirm_deletion("Video", video_id):
            print("\n🗑️  Deleting video...")
            manager = DataDeletionManager(dry_run=False, create_backup=True)
            results = manager.delete_video(video_id)
            manager.save_deletion_log()
            
            # Ask about index rebuild
            rebuild = input("\n🔄 Rebuild FAISS index now? (y/n): ").strip().lower()
            if rebuild == 'y':
                manager.rebuild_faiss_index()
            else:
                print("\n⚠️  Remember to rebuild the index later:")
                print("   python delete_content.py --rebuild-index")
        else:
            print("\n❌ Deletion cancelled")
    
    elif choice == '2':
        channel_id = input("\nEnter channel ID: ").strip()
        
        if not channel_id:
            print("❌ Channel ID required")
            return
        
        # Preview first
        print("\n🔍 Previewing deletion...")
        manager = DataDeletionManager(dry_run=True, create_backup=True)
        channel_name = manager._get_channel_name(channel_id)
        video_ids = manager.get_channel_videos(channel_id)
        
        if len(video_ids) == 0:
            print(f"❌ No videos found for channel {channel_id}")
            return
        
        manager.delete_channel(channel_id)
        
        # Confirm
        if confirm_deletion("Channel", channel_id, len(video_ids)):
            print(f"\n🗑️  Deleting channel and {len(video_ids)} videos...")
            manager = DataDeletionManager(dry_run=False, create_backup=True)
            results = manager.delete_channel(channel_id)
            manager.save_deletion_log()
            
            # Ask about index rebuild
            rebuild = input("\n🔄 Rebuild FAISS index now? (y/n): ").strip().lower()
            if rebuild == 'y':
                manager.rebuild_faiss_index()
            else:
                print("\n⚠️  Remember to rebuild the index later:")
                print("   python delete_content.py --rebuild-index")
        else:
            print("\n❌ Deletion cancelled")
    
    elif choice == '3':
        # Use default CSV path
        csv_file = r"C:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\videos_to_delete\videos_to_delete.csv"
        
        print(f"\n📂 Using default CSV file: {csv_file}")
        
        # Check if file exists
        csv_path = Path(csv_file)
        if not csv_path.exists():
            print(f"❌ File not found: {csv_file}")
            print("   Please create the file at the default location.")
            return
        
        # Call batch delete function
        batch_delete_from_csv(
            csv_file=csv_file,
            dry_run=False,
            no_backup=False,
            rebuild_index=False,
            skip_confirmation=False
        )
        
        # Ask about index rebuild
        rebuild = input("\n🔄 Rebuild FAISS index now? (y/n): ").strip().lower()
        if rebuild == 'y':
            manager = DataDeletionManager()
            manager.rebuild_faiss_index()
    
    elif choice == '4':
        print("\nDry run mode: Preview deletions without executing")
        item_type = input("Delete video (v), channel (c), or batch (b)? ").strip().lower()
        
        if item_type == 'v':
            video_id = input("Enter video ID: ").strip()
            manager = DataDeletionManager(dry_run=True, create_backup=True)
            manager.delete_video(video_id)
        elif item_type == 'c':
            channel_id = input("Enter channel ID: ").strip()
            manager = DataDeletionManager(dry_run=True, create_backup=True)
            manager.delete_channel(channel_id)
        elif item_type == 'b':
            csv_file = input("Enter CSV file path: ").strip()
            if csv_file:
                batch_delete_from_csv(
                    csv_file=csv_file,
                    dry_run=True,
                    no_backup=False,
                    rebuild_index=False,
                    skip_confirmation=True
                )
        else:
            print("❌ Invalid choice")
    
    elif choice == '5':
        video_id = input("\nEnter video ID to validate: ").strip()
        
        if not video_id:
            print("❌ Video ID required")
            return
        
        manager = DataDeletionManager()
        results = manager.validate_deletion(video_id)
        
        if results['fully_deleted']:
            print(f"\n✅ Video {video_id} is fully deleted")
        else:
            print(f"\n❌ Video {video_id} still has traces:")
            for trace in results['remaining_traces']:
                print(f"   - {trace}")
    
    elif choice == '6':
        print("\n👋 Goodbye!")
        sys.exit(0)
    
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Delete videos or channels from Flipper")
    parser.add_argument('--video', '-v', help='Video ID to delete')
    parser.add_argument('--channel', '-c', help='Channel ID to delete')
    parser.add_argument('--batch', '-b', help='CSV file with video IDs to delete (one per row)')
    parser.add_argument('--dry-run', action='store_true', help='Preview deletions without executing')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    parser.add_argument('--rebuild-index', action='store_true', help='Rebuild FAISS index only')
    parser.add_argument('--validate', help='Validate deletion of video ID')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Command-line mode
    if any([args.video, args.channel, args.batch, args.rebuild_index, args.validate]):
        # Handle batch deletion separately
        if args.batch:
            batch_delete_from_csv(
                csv_file=args.batch,
                dry_run=args.dry_run,
                no_backup=args.no_backup,
                rebuild_index=args.rebuild_index,
                skip_confirmation=args.yes
            )
            sys.exit(0)
        
        manager = DataDeletionManager(
            dry_run=args.dry_run,
            create_backup=not args.no_backup
        )
        
        if args.validate:
            results = manager.validate_deletion(args.validate)
            if results['fully_deleted']:
                print(f"✅ Video {args.validate} is fully deleted")
            else:
                print(f"❌ Video {args.validate} still has traces:")
                for trace in results['remaining_traces']:
                    print(f"   - {trace}")
        
        elif args.video:
            if not args.dry_run and not args.yes:
                video_info = manager.get_video_info(args.video)
                if not confirm_deletion("Video", args.video):
                    print("❌ Deletion cancelled")
                    sys.exit(1)
            
            results = manager.delete_video(args.video)
            manager.save_deletion_log()
            
            if args.rebuild_index and not args.dry_run:
                manager.rebuild_faiss_index()
        
        elif args.channel:
            if not args.dry_run and not args.yes:
                video_ids = manager.get_channel_videos(args.channel)
                if not confirm_deletion("Channel", args.channel, len(video_ids)):
                    print("❌ Deletion cancelled")
                    sys.exit(1)
            
            results = manager.delete_channel(args.channel)
            manager.save_deletion_log()
            
            if args.rebuild_index and not args.dry_run:
                manager.rebuild_faiss_index()
        
        elif args.rebuild_index:
            print("🔄 Rebuilding FAISS index...")
            manager.rebuild_faiss_index()
    
    else:
        # Interactive mode
        try:
            while True:
                interactive_mode()
                print("\n")
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)
