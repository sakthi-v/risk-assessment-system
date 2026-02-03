"""
Configuration settings for Risk Resolver
"""
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
SAMPLE_DATA_DIR = PROJECT_ROOT / "sample_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Ensure outputs directory exists
OUTPUTS_DIR.mkdir(exist_ok=True)

# API Configuration
GEMINI_MODEL = "gemini-3-flash-preview"

# RAG Configuration
RAG_TOP_K = 7
RAG_SIMILARITY_THRESHOLD = 0.03