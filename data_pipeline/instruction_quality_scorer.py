"""
Instruction Quality Scorer - Evaluate educational/instructional quality of teaching videos

This module uses an LLM to evaluate how effectively videos explain mathematical concepts
to learners, considering clarity, examples, visual explanations, and engagement.

Scoring is designed as a one-time batch process (not runtime) with results stored for
use in video ranking.
"""

import json
import os
import csv
import time
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv
import random


class InstructionQualityScorer:
    """
    Scores videos for instructional/educational quality using LLM evaluation
    """
    
    # Evaluation prompt for LLM
    EVALUATION_PROMPT = """You are evaluating mathematics teaching videos for instructional quality.

Evaluate how effectively the transcript explains mathematical ideas to learners who are new to the topic.

Learners:
Age 5-6

Target curriculum objective:
White Rose small step: Addition and subtraction within 10 C – Fact families (the eight facts).

Target curriculum objective description: 
Children learn addition fact families and the commutative property of addition, understanding that the order of numbers in an addition sentence can change without affecting the result. They use concrete resources like ten frames, counters, and cubes, and different colours to visualise and form addition sentences.

Consider:
- Parsimony of Conceptual explanation
- Focus on single concept throughout the video
- Pictographic or diagrammatic analogical examples to illustrate concepts
- Worked examples that show step-by-step reasoning
- Complexity of language appropriate for the age of learners receiving this instruction
- Do terms used contribute to explain the core concept or distract from it?
- Introduction of new terms is accompanied by clear definitions and examples
- Student engagement prompts

Return a score from 0–100 and a short justification (2-3 sentences max).

Respond in JSON format with exactly these fields:
{
  "score": <number 0-100>,
  "justification": "<2-3 sentence explanation>"
}"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        output_file: str = "data/video_instruction_quality.json",
        runtime_cache_file: str = "data/instruction_quality_runtime_cache.json",
        captions_dir: str = "data/captions_output",
        transcript_index_cache_file: str = "data/cache/transcript_index.json",
        max_retries: int = 3,
        delay_between_requests: float = 1.0,
        runtime_cache_save_interval_entries: int = 50,
        runtime_cache_save_interval_seconds: float = 30.0,
    ):
        """
        Initialize the instruction quality scorer
        
        Args:
            api_key: OpenAI API key (loads from .env if None)
            model: OpenAI model to use (default: gpt-4o-mini)
            output_file: Path to output JSON file
            runtime_cache_file: Path to runtime cache JSON file
            captions_dir: Directory containing caption files
            transcript_index_cache_file: Path to cached video_id -> caption path map
            max_retries: Maximum retry attempts for API failures
            delay_between_requests: Seconds to wait between API calls
            runtime_cache_save_interval_entries: Save runtime cache after this many new entries
            runtime_cache_save_interval_seconds: Save runtime cache after this many seconds
        """
        # Load API key
        if api_key is None:
            load_dotenv()
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key or api_key == 'your_api_key_here':
            raise ValueError("OpenAI API key not provided or not found in environment")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.output_file = Path(output_file)
        self.runtime_cache_file = Path(runtime_cache_file)
        self.captions_dir = Path(captions_dir)
        self.transcript_index_cache_file = Path(transcript_index_cache_file)
        self.max_retries = max_retries
        self.delay_between_requests = delay_between_requests
        self.runtime_cache_save_interval_entries = max(1, int(runtime_cache_save_interval_entries))
        self.runtime_cache_save_interval_seconds = max(1.0, float(runtime_cache_save_interval_seconds))
        
        # Load existing scores
        self.scores = self._load_existing_scores()
        
        # Load runtime cache for curriculum-context scoring
        self.runtime_cache = self._load_runtime_cache()
        self._runtime_cache_pending_entries = 0
        self._runtime_cache_last_save_time = time.time()

        # Build transcript index once to avoid repeated recursive directory scans.
        self.transcript_index, transcript_index_source = self._load_or_build_transcript_index()
        self.transcript_text_cache: Dict[str, Optional[str]] = {}
        
        print(f"✓ Instruction Quality Scorer initialized")
        print(f"  Model: {model}")
        print(f"  Output: {output_file}")
        print(f"  Existing scores: {len(self.scores)}")
        print(f"  Runtime cache: {len(self.runtime_cache)} entries")
        print(f"  Transcript index: {len(self.transcript_index)} entries ({transcript_index_source})")
    
    def _load_existing_scores(self) -> Dict:
        """Load existing scores from JSON file"""
        if self.output_file.exists():
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Could not load existing scores: {e}")
                return {}
        return {}
    
    def _save_scores(self):
        """Save scores to JSON file"""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(self.scores, indent=2, fp=f)
    
    def _load_transcript(self, video_id: str) -> Optional[str]:
        """
        Load full transcript for a video
        
        Args:
            video_id: Video ID or filename pattern
        
        Returns:
            Full transcript text or None if not found
        """
        if video_id in self.transcript_text_cache:
            return self.transcript_text_cache[video_id]

        caption_path = self.transcript_index.get(video_id)
        if caption_path is None:
            # Legacy fallback for nonstandard filenames; memoize result to avoid repeat scans.
            fallback_matches = list(self.captions_dir.rglob(f"*{video_id}*.json"))
            if fallback_matches:
                caption_path = fallback_matches[0]
                self.transcript_index[video_id] = caption_path

        if caption_path is None:
            self.transcript_text_cache[video_id] = None
            return None

        # Load the matching file
        try:
            with open(caption_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract full text from caption data
            # Try full_text field first (if it's been pre-computed)
            if 'full_text' in data and isinstance(data['full_text'], str):
                transcript_text = data['full_text']
                self.transcript_text_cache[video_id] = transcript_text
                return transcript_text
            
            # Try transcript field (could be string or list)
            if 'transcript' in data:
                transcript = data['transcript']
                if isinstance(transcript, str):
                    self.transcript_text_cache[video_id] = transcript
                    return transcript
                elif isinstance(transcript, list):
                    # Extract text from list of segment dictionaries
                    transcript_text = ' '.join(seg.get('text', '') for seg in transcript if isinstance(seg, dict))
                    self.transcript_text_cache[video_id] = transcript_text
                    return transcript_text
            
            # Try text field
            if 'text' in data and isinstance(data['text'], str):
                transcript_text = data['text']
                self.transcript_text_cache[video_id] = transcript_text
                return transcript_text
            
            # Try segments field
            if 'segments' in data and isinstance(data['segments'], list):
                transcript_text = ' '.join(seg.get('text', '') for seg in data['segments'] if isinstance(seg, dict))
                self.transcript_text_cache[video_id] = transcript_text
                return transcript_text
                
            self.transcript_text_cache[video_id] = None
            return None
            
        except Exception as e:
            print(f"⚠️  Error loading transcript for {video_id}: {e}")
            self.transcript_text_cache[video_id] = None
            return None

    def _extract_video_id_from_caption_filename(self, file_path: Path) -> Optional[str]:
        """Extract the video id from caption filename convention: Title_VIDEOID.json."""
        stem = file_path.stem.strip()
        if not stem:
            return None
        if "_" not in stem:
            return None
        candidate = stem.rsplit("_", 1)[-1].strip()
        if not candidate:
            return None
        return candidate

    def _build_transcript_index(self) -> Dict[str, Path]:
        """Build a one-time map of video_id -> transcript JSON path."""
        index: Dict[str, Path] = {}
        if not self.captions_dir.exists():
            return index

        for caption_file in self.captions_dir.rglob("*.json"):
            video_id = self._extract_video_id_from_caption_filename(caption_file)
            if not video_id:
                continue
            if video_id not in index:
                index[video_id] = caption_file
        return index

    def _caption_dir_mtimes(self) -> Dict[str, int]:
        """mtime of every directory under captions_dir. A directory's mtime changes whenever an entry
        is added, removed or renamed in it, so these detect any change to the set of caption files."""
        mtimes: Dict[str, int] = {}
        for dirpath, _, _ in os.walk(self.captions_dir):
            rel = os.path.relpath(dirpath, self.captions_dir)
            mtimes[rel] = os.stat(dirpath).st_mtime_ns
        return mtimes

    def _load_or_build_transcript_index(self) -> Tuple[Dict[str, Path], str]:
        """Reuse the cached transcript index while no caption directory has changed; else rebuild it."""
        if not self.captions_dir.exists():
            return {}, "no captions dir"

        captions_root = str(self.captions_dir.resolve())
        if self.transcript_index_cache_file.exists():
            try:
                with open(self.transcript_index_cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                dir_mtimes = cached.get("dir_mtimes") or {}
                if cached.get("captions_root") == captions_root and dir_mtimes and all(
                    os.stat(self.captions_dir / rel).st_mtime_ns == mtime for rel, mtime in dir_mtimes.items()
                ):
                    index = {video_id: self.captions_dir / rel for video_id, rel in cached["index"].items()}
                    return index, "cached"
            except (OSError, ValueError, KeyError, TypeError):
                pass

        # Snapshot mtimes before scanning so a change made mid-scan forces a rebuild next time.
        dir_mtimes = self._caption_dir_mtimes()
        index = self._build_transcript_index()
        try:
            self.transcript_index_cache_file.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.transcript_index_cache_file.with_suffix(".json.tmp")
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        "captions_root": captions_root,
                        "dir_mtimes": dir_mtimes,
                        "index": {
                            video_id: os.path.relpath(path, self.captions_dir) for video_id, path in index.items()
                        },
                    },
                    f,
                )
            os.replace(temp_path, self.transcript_index_cache_file)
        except OSError as e:
            print(f"⚠️  Could not save transcript index cache: {e}")
        return index, "rebuilt"
    
    def _should_skip_video(self, video_metadata: Dict) -> Tuple[bool, Optional[str]]:
        """
        Determine if a video should be skipped
        
        Args:
            video_metadata: Video metadata dict
        
        Returns:
            (should_skip, reason)
        """
        # Skip songs
        if video_metadata.get('is_song', False):
            return True, "song"
        
        # Skip non-English
        language = video_metadata.get('language', 'en')
        if language != 'en':
            return True, f"non-english ({language})"
        
        return False, None
    
    def _score_single_video(self, video_id: str, transcript: str) -> Optional[Dict]:
        """
        Score a single video using LLM
        
        Args:
            video_id: Video identifier
            transcript: Full transcript text
        
        Returns:
            Dict with score and justification, or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                # Call OpenAI API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.EVALUATION_PROMPT},
                        {"role": "user", "content": f"Transcript:\n\n{transcript}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,  # Lower temperature for more consistent scoring
                    max_tokens=200
                )
                
                # Parse response
                result = json.loads(response.choices[0].message.content)
                
                # Validate response format
                if 'score' not in result or 'justification' not in result:
                    raise ValueError(f"Invalid response format: {result}")
                
                # Ensure score is in valid range
                score = int(result['score'])
                if not (0 <= score <= 100):
                    raise ValueError(f"Score {score} out of range")
                
                return {
                    'score': score,
                    'justification': result['justification'],
                    'model': self.model,
                    'scored_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
            except Exception as e:
                print(f"  ⚠️  Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"  ❌ Failed to score video {video_id} after {self.max_retries} attempts")
                    return None
        
        return None
    
    def score_videos(
        self,
        video_list: List[Tuple[str, Dict]],
        save_interval: int = 10,
        verbose: bool = True
    ) -> Dict:
        """
        Score a list of videos
        
        Args:
            video_list: List of (video_id, metadata) tuples
            save_interval: Save progress every N videos
            verbose: Print progress details
        
        Returns:
            Stats dict with counts
        """
        stats = {
            'processed': 0,
            'scored': 0,
            'skipped': 0,
            'already_scored': 0,
            'failed': 0,
            'skip_reasons': {}
        }
        
        total = len(video_list)
        
        for idx, (video_id, metadata) in enumerate(video_list, 1):
            if verbose:
                print(f"\n[{idx}/{total}] Processing: {metadata.get('title', video_id)[:60]}...")
            
            # Check if already scored
            if video_id in self.scores:
                if verbose:
                    print(f"  ⏭️  Already scored: {self.scores[video_id]['score']}/100")
                stats['already_scored'] += 1
                stats['processed'] += 1
                continue
            
            # Check if should skip
            should_skip, skip_reason = self._should_skip_video(metadata)
            if should_skip:
                if verbose:
                    print(f"  ⏭️  Skipped: {skip_reason}")
                stats['skipped'] += 1
                stats['processed'] += 1
                stats['skip_reasons'][skip_reason] = stats['skip_reasons'].get(skip_reason, 0) + 1
                continue
            
            # Load transcript
            transcript = self._load_transcript(video_id)
            if not transcript or len(transcript.strip()) < 50:
                if verbose:
                    print(f"  ⏭️  Skipped: no transcript or too short")
                stats['skipped'] += 1
                stats['processed'] += 1
                stats['skip_reasons']['no_transcript'] = stats['skip_reasons'].get('no_transcript', 0) + 1
                continue
            
            # Score the video
            if verbose:
                print(f"  🤖 Scoring with {self.model}... (transcript: {len(transcript)} chars)")
            
            result = self._score_single_video(video_id, transcript)
            
            if result:
                self.scores[video_id] = {
                    'video_id': video_id,
                    'title': metadata.get('title', 'Unknown'),
                    **result
                }
                stats['scored'] += 1
                if verbose:
                    print(f"  ✅ Score: {result['score']}/100")
                    print(f"     {result['justification'][:100]}...")
            else:
                stats['failed'] += 1
            
            stats['processed'] += 1
            
            # Save progress periodically
            if stats['scored'] % save_interval == 0:
                self._save_scores()
                if verbose:
                    print(f"  💾 Progress saved ({stats['scored']} videos scored)")
            
            # Rate limiting
            time.sleep(self.delay_between_requests)
        
        # Final save
        self._save_scores()
        
        return stats
    
    def get_video_list_from_cache(self, cache_file: str = "data/api_cache.json") -> List[Tuple[str, Dict]]:
        """
        Load video list from API cache
        
        Args:
            cache_file: Path to API cache JSON
        
        Returns:
            List of (video_id, metadata) tuples
        """
        cache_path = Path(cache_file)
        if not cache_path.exists():
            raise FileNotFoundError(f"API cache not found: {cache_file}")
        
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        # Extract videos from nested structure
        # API cache format: {"channels": {...}, "videos": {"channel_key": [video_objects]}}
        video_list = []
        
        if 'videos' in cache:
            # New nested format
            for channel_key, videos in cache['videos'].items():
                if isinstance(videos, list):
                    for video in videos:
                        video_id = video.get('video_id')
                        if video_id:
                            video_list.append((video_id, video))
        else:
            # Fallback: old flat format
            for video_id, metadata in cache.items():
                if isinstance(metadata, dict) and 'video_id' in metadata:
                    actual_id = metadata.get('video_id', video_id)
                    video_list.append((actual_id, metadata))
        
        return video_list
    
    def get_video_list_from_inventory(self, inventory_file: str = "video_inventory.csv") -> List[Tuple[str, Dict]]:
        """
        Load video list from video_inventory.csv (the indexed videos)
        
        Args:
            inventory_file: Path to video inventory CSV
        
        Returns:
            List of (video_id, metadata) tuples
        """
        inventory_path = Path(inventory_file)
        if not inventory_path.exists():
            raise FileNotFoundError(f"Video inventory not found: {inventory_file}")
        
        video_list = []
        
        with open(inventory_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                video_id = row.get('video_id', '').strip()
                if not video_id:
                    continue
                
                # Convert CSV row to metadata dict
                metadata = {
                    'video_id': video_id,
                    'title': row.get('title', ''),
                    'channel': row.get('channel', ''),
                    'language': row.get('language', 'en'),
                    'is_song': row.get('is_song', '').lower() == 'true',
                    'duration': int(row.get('duration', 0)) if row.get('duration', '').isdigit() else 0,
                    'duration_formatted': row.get('duration_formatted', '')
                }
                
                video_list.append((video_id, metadata))
        
        return video_list
    
    def sample_videos(
        self,
        video_list: List[Tuple[str, Dict]],
        sample_size: int = 50,
        random_seed: int = 42
    ) -> List[Tuple[str, Dict]]:
        """
        Randomly sample videos from list
        
        Args:
            video_list: Full list of videos
            sample_size: Number of videos to sample
            random_seed: Random seed for reproducibility
        
        Returns:
            Sampled list of videos
        """
        # Filter out already scored videos
        unscored = [(vid, meta) for vid, meta in video_list if vid not in self.scores]
        
        if len(unscored) <= sample_size:
            return unscored
        
        # Random sample
        random.seed(random_seed)
        sample = random.sample(unscored, sample_size)
        
        print(f"📊 Sampled {sample_size} videos from {len(unscored)} unscored videos")
        
        return sample
    
    def print_statistics(self):
        """Print statistics about scored videos"""
        if not self.scores:
            print("No videos scored yet.")
            return
        
        scores_list = [v['score'] for v in self.scores.values()]
        
        print(f"\n{'='*60}")
        print(f"INSTRUCTION QUALITY SCORING STATISTICS")
        print(f"{'='*60}")
        print(f"Total scored videos: {len(scores_list)}")
        print(f"Average score: {sum(scores_list)/len(scores_list):.1f}/100")
        print(f"Highest score: {max(scores_list)}/100")
        print(f"Lowest score: {min(scores_list)}/100")
        
        # Distribution
        ranges = [(0, 29), (30, 49), (50, 69), (70, 89), (90, 100)]
        print(f"\nScore Distribution:")
        for low, high in ranges:
            count = sum(1 for s in scores_list if low <= s <= high)
            pct = count / len(scores_list) * 100
            print(f"  {low:3d}-{high:3d}: {count:4d} videos ({pct:5.1f}%)")
        
        print(f"{'='*60}\n")
    
    def print_sample_results(self, num_samples: int = 5):
        """Print sample scored videos for review"""
        if not self.scores:
            print("No videos scored yet.")
            return
        
        print(f"\n{'='*60}")
        print(f"SAMPLE SCORED VIDEOS (Random {num_samples})")
        print(f"{'='*60}\n")
        
        sample_ids = random.sample(list(self.scores.keys()), min(num_samples, len(self.scores)))
        
        for video_id in sample_ids:
            video = self.scores[video_id]
            print(f"Title: {video['title']}")
            print(f"Score: {video['score']}/100")
            print(f"Justification: {video['justification']}")
            print(f"Video ID: {video_id}")
            print("-" * 60 + "\n")
    
    # ==================== RUNTIME CURRICULUM-CONTEXT SCORING ====================
    
    def _load_runtime_cache(self) -> Dict:
        """Load runtime cache for curriculum-context scoring"""
        if self.runtime_cache_file.exists():
            try:
                with open(self.runtime_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Could not load runtime cache: {e}")
                return {}
        return {}
    
    def _save_runtime_cache(self):
        """Save runtime cache to JSON file"""
        self.runtime_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.runtime_cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.runtime_cache, indent=2, fp=f)

    def _build_runtime_cache_key(
        self,
        *,
        video_id: str,
        age: str,
        topic: str,
        small_step: str,
        small_step_desc: str,
        score_type: str,
    ) -> str:
        """Build versioned runtime cache key scoped to full curriculum context."""
        desc_fingerprint = hashlib.sha1((small_step_desc or "").strip().encode("utf-8")).hexdigest()[:16]
        parts = [
            "v2",
            score_type,
            (video_id or "").strip(),
            (age or "").strip(),
            (topic or "").strip(),
            (small_step or "").strip(),
            desc_fingerprint,
        ]
        return "|".join(parts)

    def _mark_runtime_cache_dirty(self):
        self._runtime_cache_pending_entries += 1
        self._flush_runtime_cache_if_needed()

    def _flush_runtime_cache_if_needed(self, force: bool = False):
        if force:
            self._save_runtime_cache()
            self._runtime_cache_pending_entries = 0
            self._runtime_cache_last_save_time = time.time()
            return

        now = time.time()
        if self._runtime_cache_pending_entries >= self.runtime_cache_save_interval_entries:
            self._save_runtime_cache()
            self._runtime_cache_pending_entries = 0
            self._runtime_cache_last_save_time = now
            return

        if (now - self._runtime_cache_last_save_time) >= self.runtime_cache_save_interval_seconds:
            self._save_runtime_cache()
            self._runtime_cache_pending_entries = 0
            self._runtime_cache_last_save_time = now
    
    def _build_curriculum_prompt(self, age: str, topic: str, small_step: str, small_step_desc: str) -> str:
        """
        Build dynamic prompt with curriculum context
        
        Args:
            age: Learner age (e.g., "5-6")
            topic: Curriculum topic
            small_step: Small step name
            small_step_desc: Small step description
        
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are evaluating mathematics teaching videos for instructional quality.

Evaluate how effectively the transcript explains mathematical ideas to learners who are new to the topic.

Learners:
Age {age}

Target curriculum objective:
White Rose small step: {topic} – {small_step}

Target curriculum objective description: 
{small_step_desc}

Consider:
- Parsimony of Conceptual explanation
- Focus on single concept throughout the video
- Pictographic or diagrammatic analogical examples to illustrate concepts
- Worked examples that show step-by-step reasoning
- Complexity of language appropriate for the age of learners receiving this instruction
- Do terms used contribute to explain the core concept or distract from it?
- Introduction of new terms is accompanied by clear definitions and examples
- Student engagement prompts

Return a score from 0–100 and a short justification (2-3 sentences max).

Respond in JSON format with exactly these fields:
{{
  "score": <number 0-100>,
  "justification": "<2-3 sentence explanation>"
}}"""
        return prompt

    def _build_alignment_prompt(self, age: str, topic: str, small_step: str, small_step_desc: str) -> str:
        """Build prompt focused only on curriculum-objective alignment."""
        return f"""You are evaluating mathematics teaching videos for alignment to a curriculum objective.

Evaluate how well the transcript content aligns with the specific target objective for learners who are new to the topic.

Learners:
Age {age}

Target curriculum objective:
White Rose small step: {topic} – {small_step}

Target curriculum objective description:
{small_step_desc}

Consider:
- Objective match: does the main teaching focus directly match the target objective?
- Scope discipline: does the video avoid drifting into different or broader objectives?
- Age suitability for objective focus.

Return a score from 0-100 and a short justification (2-3 sentences max).

Respond in JSON format with exactly these fields:
{{
    "score": <number 0-100>,
    "justification": "<2-3 sentence explanation>"
}}"""
    
    async def score_for_curriculum_context_async(
        self,
        video_id: str,
        age: str,
        topic: str,
        small_step: str,
        small_step_desc: str,
        use_cache: bool = True
    ) -> Optional[Dict]:
        """
        Score a single video for a specific curriculum context at runtime (async)
        
        Args:
            video_id: Video identifier
            age: Learner age (e.g., "5-6")
            topic: Curriculum topic
            small_step: Small step name
            small_step_desc: Small step description
            use_cache: Whether to use/update cache
        
        Returns:
            Dict with score, justification, cached status, or None if failed
        """
        # Generate cache key
        cache_key = self._build_runtime_cache_key(
            video_id=video_id,
            age=age,
            topic=topic,
            small_step=small_step,
            small_step_desc=small_step_desc,
            score_type="instruction",
        )
        
        # Check cache
        if use_cache and cache_key in self.runtime_cache:
            cached = self.runtime_cache[cache_key]
            return {**cached, 'from_cache': True, 'error': None}
        
        # Load transcript
        transcript = self._load_transcript(video_id)
        if not transcript:
            return {
                'video_id': video_id,
                'score': None,
                'justification': 'Transcript not found',
                'from_cache': False,
                'error': 'no_transcript'
            }
        
        # Build dynamic prompt
        prompt = self._build_curriculum_prompt(age, topic, small_step, small_step_desc)
        
        # Score with LLM (with retries)
        for attempt in range(self.max_retries):
            try:
                # Call OpenAI API (synchronous call in async function)
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Transcript:\n\n{transcript}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=200
                )
                
                # Parse response
                result = json.loads(response.choices[0].message.content)
                
                # Validate response format
                if 'score' not in result or 'justification' not in result:
                    raise ValueError(f"Invalid response format: {result}")
                
                # Ensure score is in valid range
                score = int(result['score'])
                if not (0 <= score <= 100):
                    raise ValueError(f"Score {score} out of range")
                
                result_dict = {
                    'video_id': video_id,
                    'score': score,
                    'justification': result['justification'],
                    'model': self.model,
                    'scored_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'age': age,
                    'topic': topic,
                    'small_step': small_step
                }
                
                # Cache result
                if use_cache:
                    self.runtime_cache[cache_key] = result_dict
                    self._mark_runtime_cache_dirty()
                
                return {**result_dict, 'from_cache': False, 'error': None}
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Failed after all retries
                    return {
                        'video_id': video_id,
                        'score': None,
                        'justification': f'Scoring failed: {str(e)}',
                        'from_cache': False,
                        'error': str(e)
                    }
        
        return None
    
    async def score_videos_for_curriculum_batch_async(
        self,
        video_ids: List[str],
        age: str,
        topic: str,
        small_step: str,
        small_step_desc: str,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Score multiple videos for curriculum context in parallel (async)
        
        Args:
            video_ids: List of video IDs to score
            age: Learner age
            topic: Curriculum topic
            small_step: Small step name
            small_step_desc: Small step description
            use_cache: Whether to use/update cache
        
        Returns:
            List of result dicts (includes successes and failures)
        """
        # Create tasks for all videos
        tasks = [
            self.score_for_curriculum_context_async(
                video_id, age, topic, small_step, small_step_desc, use_cache
            )
            for video_id in video_ids
        ]
        
        # Run all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'video_id': video_ids[i],
                    'score': None,
                    'justification': f'Exception: {str(result)}',
                    'from_cache': False,
                    'error': str(result)
                })
            elif result is not None:
                processed_results.append(result)
        
        return processed_results

    async def score_alignment_for_curriculum_context_async(
        self,
        video_id: str,
        age: str,
        topic: str,
        small_step: str,
        small_step_desc: str,
        use_cache: bool = True,
    ) -> Optional[Dict]:
        """Score a single video for curriculum-objective alignment at runtime (async)."""
        cache_key = self._build_runtime_cache_key(
            video_id=video_id,
            age=age,
            topic=topic,
            small_step=small_step,
            small_step_desc=small_step_desc,
            score_type="alignment",
        )

        if use_cache and cache_key in self.runtime_cache:
            cached = self.runtime_cache[cache_key]
            return {**cached, 'from_cache': True, 'error': None}

        transcript = self._load_transcript(video_id)
        if not transcript:
            return {
                'video_id': video_id,
                'score': None,
                'justification': 'Transcript not found',
                'from_cache': False,
                'error': 'no_transcript'
            }

        prompt = self._build_alignment_prompt(age, topic, small_step, small_step_desc)

        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Transcript:\n\n{transcript}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=200
                )

                result = json.loads(response.choices[0].message.content)
                if 'score' not in result or 'justification' not in result:
                    raise ValueError(f"Invalid response format: {result}")

                score = int(result['score'])
                if not (0 <= score <= 100):
                    raise ValueError(f"Score {score} out of range")

                result_dict = {
                    'video_id': video_id,
                    'score': score,
                    'justification': result['justification'],
                    'model': self.model,
                    'scored_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'age': age,
                    'topic': topic,
                    'small_step': small_step,
                    'score_type': 'alignment'
                }

                if use_cache:
                    self.runtime_cache[cache_key] = result_dict
                    self._mark_runtime_cache_dirty()

                return {**result_dict, 'from_cache': False, 'error': None}

            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return {
                        'video_id': video_id,
                        'score': None,
                        'justification': f'Scoring failed: {str(e)}',
                        'from_cache': False,
                        'error': str(e)
                    }

        return None
    
    def clear_runtime_cache(self):
        """Clear the runtime cache"""
        self.runtime_cache = {}
        self._flush_runtime_cache_if_needed(force=True)
        print("✓ Runtime cache cleared")

    def flush_runtime_cache(self):
        """Force-save pending runtime-cache updates."""
        self._flush_runtime_cache_if_needed(force=True)
