"""
Batch Curriculum Quality Audit

Systematically search and score all curriculum small steps to identify
which have sufficient high-quality video coverage.

This script:
1. Reads curriculum CSV (all rows and small steps 1-7)
2. For each small step: semantically searches FAISS index using Flipper's algorithm
3. Scores top 5 videos with instruction quality LLM
4. Outputs detailed CSV with all scores
5. Generates summary report of small steps with <3 good videos

Output CSV columns:
- UniqueRow, Topic, SmallStep_Num, SmallStep_Label, SmallStep_Name, SmallStep_Desc
- VideoID, Video_Title, Video_Channel, Video_Duration
- Semantic_Match (highest chunk similarity)
- Ranking_Score (Flipper's algorithm: median + good_chunks_bonus)
- Median_Similarity, Good_Chunks_Count (ranking metrics)
- Instruction_Quality (0-100)
- Combined_Score (Flipper's final ranking: 60% semantic + 40% instruction)
- Combined_Score_Rank (1-5 for each small step, ordered by combined_score)
- Rank (1-5 for each small step, ordered by ranking_score)

Usage:
  python batch_curriculum_quality_audit.py --curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv"
  python batch_curriculum_quality_audit.py --curriculum "path/to/curriculum.csv" --output "audit_results.csv" --sample 10
  python batch_curriculum_quality_audit.py --first-50-steps
"""

import sys
import argparse
import asyncio
import csv
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json
import numpy as np
import faiss
from datetime import datetime
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from query_embedder import QueryEmbedder
from data_pipeline.instruction_quality_scorer import InstructionQualityScorer
from data_pipeline.deletion_tracker import DeletionTracker
from shared.curriculum_schema import curriculum_to_long_df


class CurriculumQualityAuditor:
    """Batch audit curriculum coverage with semantic search and instruction quality scoring"""
    
    def __init__(
        self,
        curriculum_path: str,
        faiss_index_path: str = "data/faiss_index/faiss_index.bin",
        faiss_metadata_path: str = "data/faiss_index/faiss_index_metadata.json",
        top_k: int = 40,
        top_n_to_score: int = 5
    ):
        """
        Initialize the auditor
        
        Args:
            curriculum_path: Path to curriculum CSV file
            faiss_index_path: Path to FAISS index
            faiss_metadata_path: Path to FAISS metadata JSON
            top_k: Number of results to get from semantic search
            top_n_to_score: Number of top results to score with LLM
        """
        self.curriculum_path = Path(curriculum_path)
        self.top_k = top_k
        self.top_n_to_score = top_n_to_score
        
        # Load FAISS index and metadata
        print("Loading FAISS index...")
        self.index = faiss.read_index(str(faiss_index_path))
        with open(faiss_metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.metadata = data['metadata']
        print(f"✓ Loaded FAISS index with {len(self.metadata)} vectors")
        
        # Initialize embedder and scorer
        print("Initializing embedder and scorer...")
        self.embedder = QueryEmbedder()
        self.scorer = InstructionQualityScorer()
        print("✓ Initialized")
        
        # Get deleted videos
        self.deletion_tracker = DeletionTracker()
        self.deleted_videos = self.deletion_tracker.get_deleted_video_ids()
        print(f"✓ Loaded {len(self.deleted_videos)} deleted videos to filter")
        
    def load_curriculum(self) -> List[Dict]:
        """Load curriculum from CSV"""
        print(f"\nLoading curriculum from {self.curriculum_path}...")
        rows = curriculum_to_long_df(pd.read_csv(self.curriculum_path)).to_dict('records')
        print(f"✓ Loaded {len(rows)} curriculum rows")
        return rows
    
    def extract_small_steps(self, row: Dict) -> List[Dict]:
        """Extract all non-empty small steps from a curriculum row"""
        if row.get('small_step_name'):
            return [{
                'num': int(row.get('small_step_num_in_topic', 0)),
                'global_num': int(row.get('small_step_num', 0)),
                'name': row.get('small_step_name', '').strip(),
                'desc_short': row.get('ss_desc', '').strip(),
                'desc_full': row.get('ss_wr_desc', '').strip(),
                'small_step_id': row.get('small_step_id', ''),
                'small_step_key': row.get('small_step_key', ''),
            }]

        small_steps = []
        for i in range(1, 8):  # Small Steps 1-7
            step_name = row.get(f'Small Step {i}', '').strip()
            step_desc_short = row.get(f'SS{i}_desc_short', '').strip()
            
            if step_name and step_desc_short:
                small_steps.append({
                    'num': i,
                    'name': step_name,
                    'desc_short': step_desc_short,
                    'desc_full': row.get(f'SS{i}_desc', '').strip()
                })
        return small_steps
    
    def calculate_cosine_similarity(self, l2_distance: float) -> float:
        """Convert L2 distance to cosine similarity (for normalized vectors)"""
        return 1 - (l2_distance ** 2 / 2)
    
    def semantic_search(self, query: str) -> List[Dict]:
        """
        Perform semantic search using FAISS
        
        Returns:
            List of result dicts with video metadata and scores
        """
        # Generate query embedding
        query_vector = self.embedder.embed_query(query)
        
        # Search FAISS index
        distances, indices = self.index.search(query_vector, self.top_k)
        
        # Format results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            
            meta = self.metadata[idx]
            
            # Skip deleted videos
            if meta['video_id'] in self.deleted_videos:
                continue
            
            cosine_sim = self.calculate_cosine_similarity(dist)
            
            result = {
                'cosine_similarity': float(cosine_sim),
                'l2_distance': float(dist),
                'video_id': meta['video_id'],
                'title': meta['title'],
                'channel': meta.get('channel', 'Unknown'),
                'duration': meta.get('duration', 0),
                'language': meta.get('language', 'en'),
                'is_song': meta.get('is_song', False),
                'chunk_index': meta['chunk_index'],
                'text': meta['text']
            }
            results.append(result)
        
        return results
    
    def deduplicate_videos(self, results: List[Dict]) -> List[Dict]:
        """
        Deduplicate by video_id using Flipper's ranking algorithm:
        - Group chunks by video_id
        - Calculate ranking_score = median_similarity + (good_chunks_count × 0.02)
        - Keep highest similarity chunk per video
        - Sort by ranking_score (not by highest similarity!)
        
        Returns:
            List of unique video results, sorted by ranking_score
        """
        # Group chunks by video_id
        video_chunks = {}
        for result in results:
            video_id = result['video_id']
            if video_id not in video_chunks:
                video_chunks[video_id] = []
            video_chunks[video_id].append(result)
        
        # Calculate ranking statistics for each video
        video_stats = {}
        for video_id, chunks in video_chunks.items():
            sims = [c['cosine_similarity'] for c in chunks]
            # Count chunks above quality threshold (0.6 = 60%)
            good_chunks = [c for c in chunks if c['cosine_similarity'] >= 0.6]
            median_sim = sorted(sims)[len(sims)//2]
            ranking_score = median_sim + (len(good_chunks) * 0.02)  # Median + bonus for good chunks
            video_stats[video_id] = {
                'chunk_count': len(chunks),
                'max_similarity': max(sims),
                'median_similarity': median_sim,
                'good_chunks_count': len(good_chunks),
                'ranking_score': ranking_score
            }
        
        # Deduplicate: keep highest similarity chunk per video
        seen_videos = {}
        for result in results:
            video_id = result['video_id']
            if video_id not in seen_videos:
                seen_videos[video_id] = result
            elif result['cosine_similarity'] > seen_videos[video_id]['cosine_similarity']:
                seen_videos[video_id] = result
        
        # Add ranking_score to each result
        for video_id, result in seen_videos.items():
            result['ranking_score'] = video_stats[video_id]['ranking_score']
            result['median_similarity'] = video_stats[video_id]['median_similarity']
            result['good_chunks_count'] = video_stats[video_id]['good_chunks_count']
        
        # Sort by ranking_score (Flipper's algorithm), not by highest similarity!
        unique_results = sorted(
            seen_videos.values(),
            key=lambda x: x['ranking_score'],
            reverse=True
        )
        
        return unique_results
    
    async def audit_small_step(
        self,
        row: Dict,
        small_step: Dict,
        progress_info: str
    ) -> List[Dict]:
        """
        Audit a single small step: semantic search + instruction quality scoring
        
        Returns:
            List of result dicts (one per video in top N)
        """
        print(f"\n{progress_info}")
        print(f"  Small Step {small_step['num']}: {small_step['name']}")
        
        # Step 1: Semantic search - match Flipper's exact query format
        # Flipper uses: "**{step_name}** Example: {desc_short}"
        query = f"**{small_step['name']}** Example: {small_step['desc_short']}"
        print(f"  🔍 Semantic search: '{query[:80]}...'")
        search_results = self.semantic_search(query)
        
        # Deduplicate by video_id
        unique_videos = self.deduplicate_videos(search_results)
        print(f"  ✓ Found {len(unique_videos)} unique videos")
        
        if not unique_videos:
            print(f"  ⚠️  No videos found")
            return []
        
        # Step 2: Get top N for instruction quality scoring
        top_n = unique_videos[:self.top_n_to_score]
        video_ids = [v['video_id'] for v in top_n]
        
        print(f"  🤖 Scoring top {len(top_n)} videos with LLM...")
        
        # Step 3: Batch score with instruction quality (async)
        age = row.get('age', row.get('Age', ''))
        topic = row.get('topic', row.get('Topic', ''))
        
        instruction_scores = await self.scorer.score_videos_for_curriculum_batch_async(
            video_ids=video_ids,
            age=age,
            topic=topic,
            small_step=small_step['name'],
            small_step_desc=small_step['desc_short'],
            use_cache=True
        )
        
        # Step 4: Combine semantic search results with instruction quality scores
        results = []
        for rank, video in enumerate(top_n, 1):
            # Find matching instruction score
            instruction_result = next(
                (s for s in instruction_scores if s['video_id'] == video['video_id']),
                None
            )
            
            result = {
                'unique_row': row.get('unique_row', row.get('UniqueRow', '')),
                'year': row.get('year', row.get('Year', '')),
                'age': age,
                'topic': topic,
                'small_step_num': small_step['num'],
                'small_step_num_global': small_step.get('global_num'),
                'small_step_id': small_step.get('small_step_id', ''),
                'small_step_key': small_step.get('small_step_key', ''),
                'small_step_name': small_step['name'],
                'small_step_desc_short': small_step['desc_short'],
                'video_id': video['video_id'],
                'video_title': video['title'],
                'video_channel': video['channel'],
                'video_duration': video['duration'],
                'video_language': video['language'],
                'video_is_song': video['is_song'],
                'semantic_match': video['cosine_similarity'],
                'ranking_score': video.get('ranking_score', video['cosine_similarity']),
                'median_similarity': video.get('median_similarity', video['cosine_similarity']),
                'good_chunks_count': video.get('good_chunks_count', 0),
                'instruction_quality': instruction_result['score'] if instruction_result else None,
                'instruction_justification': instruction_result.get('justification', '') if instruction_result else '',
                'instruction_from_cache': instruction_result.get('from_cache', False) if instruction_result else False,
                'instruction_error': instruction_result.get('error', '') if instruction_result else '',
                'rank': rank,
                'chunk_index': video['chunk_index']
            }
            
            # Calculate combined score (Flipper's final ranking: 60% semantic + 40% instruction)
            # Matches Flipper's exact formula from flipper.py
            SEMANTIC_WEIGHT = 0.6
            INSTRUCTION_WEIGHT = 0.4
            if result['instruction_quality'] is not None:
                semantic_score = result['semantic_match']
                instruction_score_normalized = result['instruction_quality'] / 100.0
                result['combined_score'] = (semantic_score * SEMANTIC_WEIGHT) + (instruction_score_normalized * INSTRUCTION_WEIGHT)
            else:
                # Fallback to semantic only if instruction scoring failed
                result['combined_score'] = result['semantic_match']
            
            results.append(result)
        
        # Step 5: Re-sort by combined_score and assign final rank (Flipper's final ranking)
        results.sort(key=lambda x: x['combined_score'], reverse=True)
        for final_rank, result in enumerate(results, 1):
            result['combined_score_rank'] = final_rank
            result['small_step_label'] = f"Small Step {small_step['num']}"
            
            # Log result with ranking details
            sem_score = result['semantic_match'] * 100
            rank_score = result['ranking_score'] * 100
            inst_score = result['instruction_quality'] if result['instruction_quality'] is not None else -1
            combined_score = result['combined_score'] * 100
            cache_icon = "💾" if result['instruction_from_cache'] else "🆕"
            print(f"    #{final_rank} {result['video_title'][:50]:50s} | Comb: {combined_score:5.1f}% | Sem: {sem_score:5.1f}% | Inst: {inst_score:3.0f}% {cache_icon}")
        
        return results
    
    async def audit_first_n_steps(self, n_steps: int = 50) -> Tuple[List[Dict], Dict]:
        """
        Audit first N small steps in order (for cross-referencing with flipper)
        
        Args:
            n_steps: Number of small steps to audit
        
        Returns:
            Tuple of (all_results, summary_stats)
        """
        curriculum = self.load_curriculum()
        
        # Collect all small steps in order
        all_small_steps = []
        for row in curriculum:
            small_steps = self.extract_small_steps(row)
            for step in small_steps:
                all_small_steps.append((row, step))
        
        # Take first N steps
        steps_to_audit = all_small_steps[:n_steps]
        
        print(f"\n⚠️  FIRST {n_steps} STEPS MODE: Processing first {len(steps_to_audit)} small steps in order")
        print(f"Total available small steps: {len(all_small_steps)}")
        
        all_results = []
        stats = {
            'total_rows': len(set(row.get('UniqueRow', '') for row, _ in steps_to_audit)),
            'total_small_steps': 0,
            'total_videos_scored': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'small_steps_with_insufficient_videos': []
        }
        
        print(f"\n{'='*80}")
        print(f"STARTING BATCH AUDIT - FIRST {n_steps} STEPS")
        print(f"{'='*80}")
        print(f"Steps to audit: {len(steps_to_audit)}")
        print(f"Top K semantic search results: {self.top_k}")
        print(f"Top N to score with LLM: {self.top_n_to_score}")
        print(f"{'='*80}")
        
        for idx, (row, step) in enumerate(steps_to_audit, 1):
            stats['total_small_steps'] += 1
            progress_info = f"[Step {idx}/{len(steps_to_audit)}] {row.get('UniqueRow', 'Unknown')}"
            
            step_results = await self.audit_small_step(row, step, progress_info)
            all_results.extend(step_results)
            
            # Update stats
            stats['total_videos_scored'] += len(step_results)
            stats['cache_hits'] += sum(1 for r in step_results if r['instruction_from_cache'])
            stats['cache_misses'] += sum(1 for r in step_results if not r['instruction_from_cache'])
            
            # Check if this small step has insufficient good videos
            good_videos = [
                r for r in step_results
                if r['semantic_match'] >= 0.6  # 60% semantic match
                and r['instruction_quality'] is not None
                and r['instruction_quality'] >= 60  # 60/100 instruction quality
            ]
            
            if len(good_videos) < 3:
                stats['small_steps_with_insufficient_videos'].append({
                    'unique_row': row.get('UniqueRow', ''),
                    'topic': row.get('Topic', ''),
                    'small_step_num': step['num'],
                    'small_step_name': step['name'],
                    'good_video_count': len(good_videos),
                    'total_video_count': len(step_results)
                })
        
        return all_results, stats
    
    async def audit_all(self, sample_size: Optional[int] = None) -> Tuple[List[Dict], Dict]:
        """
        Audit all curriculum small steps
        
        Args:
            sample_size: If provided, only audit first N curriculum rows (for testing)
        
        Returns:
            Tuple of (all_results, summary_stats)
        """
        curriculum = self.load_curriculum()
        
        if sample_size:
            curriculum = curriculum[:sample_size]
            print(f"\n⚠️  SAMPLE MODE: Processing only first {sample_size} rows")
        
        all_results = []
        stats = {
            'total_rows': len(curriculum),
            'total_small_steps': 0,
            'total_videos_scored': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'small_steps_with_insufficient_videos': []
        }
        
        print(f"\n{'='*80}")
        print(f"STARTING BATCH AUDIT")
        print(f"{'='*80}")
        print(f"Curriculum rows: {len(curriculum)}")
        print(f"Top K semantic search results: {self.top_k}")
        print(f"Top N to score with LLM: {self.top_n_to_score}")
        print(f"{'='*80}")
        
        for row_idx, row in enumerate(curriculum, 1):
            print(f"\n{'='*80}")
            print(f"ROW {row_idx}/{len(curriculum)}: {row.get('UniqueRow', 'Unknown')}")
            print(f"Topic: {row.get('Topic', 'Unknown')}")
            print(f"{'='*80}")
            
            small_steps = self.extract_small_steps(row)
            
            if not small_steps:
                print(f"  ⚠️  No small steps found in this row")
                continue
            
            for step in small_steps:
                stats['total_small_steps'] += 1
                progress_info = f"[Row {row_idx}/{len(curriculum)}] [Step {step['num']}/7]"
                
                step_results = await self.audit_small_step(row, step, progress_info)
                all_results.extend(step_results)
                
                # Update stats
                stats['total_videos_scored'] += len(step_results)
                stats['cache_hits'] += sum(1 for r in step_results if r['instruction_from_cache'])
                stats['cache_misses'] += sum(1 for r in step_results if not r['instruction_from_cache'])
                
                # Check if this small step has insufficient good videos
                good_videos = [
                    r for r in step_results
                    if r['semantic_match'] >= 0.6  # 60% semantic match
                    and r['instruction_quality'] is not None
                    and r['instruction_quality'] >= 60  # 60/100 instruction quality
                ]
                
                if len(good_videos) < 3:
                    stats['small_steps_with_insufficient_videos'].append({
                        'unique_row': row.get('UniqueRow', ''),
                        'topic': row.get('Topic', ''),
                        'small_step_num': step['num'],
                        'small_step_name': step['name'],
                        'good_video_count': len(good_videos),
                        'total_video_count': len(step_results)
                    })
        
        return all_results, stats
    
    def save_results(self, results: List[Dict], output_path: str):
        """Save results to CSV"""
        print(f"\n{'='*80}")
        print(f"SAVING RESULTS")
        print(f"{'='*80}")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not results:
            print("⚠️  No results to save")
            return
        
        # Define CSV columns
        fieldnames = [
            'unique_row', 'year', 'age', 'topic',
            'small_step_num', 'small_step_label', 'small_step_name', 'small_step_desc_short',
            'video_id', 'video_title', 'video_channel', 'video_duration',
            'video_language', 'video_is_song',
            'semantic_match', 'ranking_score', 'median_similarity', 'good_chunks_count',
            'instruction_quality', 'combined_score', 'combined_score_rank',
            'instruction_justification',
            'instruction_from_cache', 'instruction_error',
            'rank', 'chunk_index'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✓ Saved {len(results)} results to: {output_path}")
    
    def save_summary(self, stats: Dict, output_path: str):
        """Save summary report"""
        summary_path = Path(output_path).with_suffix('.summary.txt')
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("CURRICULUM QUALITY AUDIT SUMMARY\n")
            f.write("="*80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Curriculum: {self.curriculum_path}\n")
            f.write("\n")
            
            f.write("OVERALL STATISTICS\n")
            f.write("-"*80 + "\n")
            f.write(f"Total curriculum rows processed: {stats['total_rows']}\n")
            f.write(f"Total small steps audited: {stats['total_small_steps']}\n")
            f.write(f"Total videos scored: {stats['total_videos_scored']}\n")
            f.write(f"LLM cache hits: {stats['cache_hits']} ({stats['cache_hits']/max(stats['total_videos_scored'],1)*100:.1f}%)\n")
            f.write(f"LLM cache misses (new API calls): {stats['cache_misses']}\n")
            f.write("\n")
            
            f.write("SMALL STEPS WITH INSUFFICIENT GOOD VIDEOS\n")
            f.write("-"*80 + "\n")
            f.write(f"Criteria: <3 videos with ≥60% semantic match AND ≥60/100 instruction quality\n")
            f.write(f"Count: {len(stats['small_steps_with_insufficient_videos'])}\n")
            f.write("\n")
            
            if stats['small_steps_with_insufficient_videos']:
                for item in stats['small_steps_with_insufficient_videos']:
                    f.write(f"  • {item['unique_row']}\n")
                    f.write(f"    Topic: {item['topic']}\n")
                    f.write(f"    Small Step {item['small_step_num']}: {item['small_step_name']}\n")
                    f.write(f"    Good videos: {item['good_video_count']}/{item['total_video_count']}\n")
                    f.write("\n")
            else:
                f.write("  ✓ All small steps have sufficient good videos!\n")
            
            f.write("="*80 + "\n")
        
        print(f"✓ Saved summary to: {summary_path}")
        
        # Also print summary to console
        print(f"\n{'='*80}")
        print("AUDIT SUMMARY")
        print(f"{'='*80}")
        print(f"Curriculum rows: {stats['total_rows']}")
        print(f"Small steps audited: {stats['total_small_steps']}")
        print(f"Videos scored: {stats['total_videos_scored']}")
        print(f"Cache hits: {stats['cache_hits']} ({stats['cache_hits']/max(stats['total_videos_scored'],1)*100:.1f}%)")
        print(f"Cache misses: {stats['cache_misses']}")
        print(f"\nSmall steps with <3 good videos: {len(stats['small_steps_with_insufficient_videos'])}")
        print(f"{'='*80}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch audit curriculum quality coverage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_curriculum_quality_audit.py --curriculum "Curriculum/Maths/mat_curr_short_import - 08032026.csv"
  
  python batch_curriculum_quality_audit.py --curriculum "path/to/curriculum.csv" --output "audit_results.csv"
  
  python batch_curriculum_quality_audit.py --curriculum "path/to/curriculum.csv" --sample 10
      (Process only first 10 rows for testing)
  
  python batch_curriculum_quality_audit.py --first-50-steps
      (Score first 50 small steps from default curriculum for cross-referencing with flipper)
        """
    )
    
    parser.add_argument(
        '--curriculum',
        help='Path to curriculum CSV file (default: Curriculum/Maths/mat_curr_short_import - 08032026.csv)'
    )
    
    parser.add_argument(
        '--first-50-steps',
        action='store_true',
        help='Score first 50 small steps in order from curriculum for cross-referencing with flipper'
    )
    
    parser.add_argument(
        '--output',
        default='curriculum_quality_audit.csv',
        help='Output CSV file path (default: curriculum_quality_audit.csv)'
    )
    
    parser.add_argument(
        '--sample',
        type=int,
        help='Process only first N curriculum rows (for testing)'
    )
    
    parser.add_argument(
        '--top-k',
        type=int,
        default=40,
        help='Number of semantic search results to retrieve (default: 40)'
    )
    
    parser.add_argument(
        '--top-n',
        type=int,
        default=5,
        help='Number of top results to score with LLM (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Handle --first-50-steps mode
    if args.first_50_steps:
        if args.curriculum is None:
            args.curriculum = 'Curriculum/Maths/mat_curr_short_import - 08032026.csv'
        if args.output == 'curriculum_quality_audit.csv':
            args.output = 'curriculum_quality_audit_first50.csv'
        print(f"\n📋 First 50 Steps Mode")
        print(f"   Curriculum: {args.curriculum}")
        print(f"   Output: {args.output}")
    elif args.curriculum is None:
        print(f"❌ Error: --curriculum is required (unless using --first-50-steps)")
        return 1
    
    # Validate curriculum path
    curriculum_path = Path(args.curriculum)
    if not curriculum_path.exists():
        print(f"❌ Error: Curriculum file not found: {curriculum_path}")
        return 1
    
    try:
        # Initialize auditor
        auditor = CurriculumQualityAuditor(
            curriculum_path=str(curriculum_path),
            top_k=args.top_k,
            top_n_to_score=args.top_n
        )
        
        # Run audit (async)
        if args.first_50_steps:
            results, stats = asyncio.run(auditor.audit_first_n_steps(n_steps=50))
        else:
            results, stats = asyncio.run(auditor.audit_all(sample_size=args.sample))
        
        # Save results
        auditor.save_results(results, args.output)
        auditor.save_summary(stats, args.output)
        
        print(f"\n✅ Audit complete!")
        print(f"   Results: {args.output}")
        print(f"   Summary: {Path(args.output).with_suffix('.summary.txt')}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
