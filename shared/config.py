"""
Shared configuration for both data pipeline and search app
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
CAPTIONS_DIR = DATA_DIR / "captions_output"
CHUNKED_DIR = DATA_DIR / "chunked_output"
EMBEDDINGS_DIR = DATA_DIR / "embeddings_output"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"

# Cache and metadata files
API_CACHE_FILE = DATA_DIR / "api_cache.json"
EMBEDDINGS_CONSOLIDATED_FILE = DATA_DIR / "embeddings_consolidated.json"
FAISS_METADATA_FILE = FAISS_INDEX_DIR / "faiss_index_metadata.json"
DELETED_VIDEOS_FILE = DATA_DIR / "deleted_videos.json"

# Deletion thresholds
DELETION_REBUILD_THRESHOLD = 0.05  # Warn when 5% of videos are soft-deleted

# Input files
CHANNELS_CSV = PROJECT_ROOT / "channels.csv"

# API Keys
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# OpenAI Configuration
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')
EMBEDDING_DIMENSIONS = int(os.getenv('EMBEDDING_DIMENSIONS', 3072))

# Pipeline Configuration
MAX_VIDEOS_PER_CHANNEL = int(os.getenv('MAX_VIDEOS_PER_CHANNEL', 20))  # Reduced from 100 to process in smaller batches
MAX_VIDEO_DURATION = 1200  # seconds (20 minutes)

# Rate Limiting Configuration (to prevent IP blocking)
# More conservative delays to avoid bot detection
DELAY_BETWEEN_VIDEOS = float(os.getenv('DELAY_BETWEEN_VIDEOS', 10.0))  # Increased from 3.0 to 10.0 seconds
DELAY_BETWEEN_API_CALLS = float(os.getenv('DELAY_BETWEEN_API_CALLS', 2.0))  # Increased from 1.0 to 2.0 seconds

# Randomization to make requests look more human
RANDOM_DELAY_MIN = float(os.getenv('RANDOM_DELAY_MIN', 8.0))  # Minimum random delay (seconds)
RANDOM_DELAY_MAX = float(os.getenv('RANDOM_DELAY_MAX', 15.0))  # Maximum random delay (seconds)

# Session break configuration (pause after batch to avoid detection)
VIDEOS_PER_BATCH = int(os.getenv('VIDEOS_PER_BATCH', 5))  # Process this many videos before taking a break
BREAK_DURATION_MIN = float(os.getenv('BREAK_DURATION_MIN', 60.0))  # Minimum break duration (seconds)
BREAK_DURATION_MAX = float(os.getenv('BREAK_DURATION_MAX', 180.0))  # Maximum break duration (seconds)

# Chunking Configuration
CHUNK_SIZE = 100  # words per chunk
CHUNK_OVERLAP = 20  # words overlap between chunks

# Search Configuration
DEFAULT_SEARCH_RESULTS = 5
SIMILARITY_THRESHOLD = 0.7

def ensure_directories():
    """Create all necessary directories if they don't exist"""
    for directory in [DATA_DIR, CAPTIONS_DIR, CHUNKED_DIR, EMBEDDINGS_DIR, FAISS_INDEX_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

def validate_config():
    """Validate that required configuration is present"""
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not found in .env file")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in .env file")
    return True
