"""
Chunking configuration.

This module contains all configurable parameters used by the chunking
pipeline. No business logic should be added here.
"""

# =============================================================================
# Chunk Size Configuration
# =============================================================================

# Preferred maximum number of tokens per chunk.
MAX_TOKENS = 800

# Minimum number of tokens before considering a split.
MIN_TOKENS = 150

# Token overlap between adjacent chunks.
TOKEN_OVERLAP = 100


# =============================================================================
# Semantic Parsing
# =============================================================================

# Merge consecutive paragraphs inside the same section.
MERGE_PARAGRAPHS = True

# Merge sections that continue across page boundaries.
MERGE_ACROSS_PAGES = True

# Preserve document hierarchy (Section -> Subsection -> Content).
PRESERVE_HIERARCHY = True


# =============================================================================
# Object Preservation
# =============================================================================

# Keep tables as independent semantic objects.
PRESERVE_TABLES = True

# Keep code blocks intact.
PRESERVE_CODE_BLOCKS = True

# Preserve ordered and unordered lists.
PRESERVE_LISTS = True


# =============================================================================
# Heading Detection
# =============================================================================

# Markdown heading detection.
MARKDOWN_HEADINGS = ("#", "##", "###", "####")

# Regex patterns for numbered headings.
NUMBERED_HEADING_PATTERNS = (
    r"^\d+\.$",                 # 1.
    r"^\d+\.\d+$",              # 1.1
    r"^\d+\.\d+\.\d+$",         # 1.1.1
)

# Detect ALL CAPS headings.
DETECT_UPPERCASE_HEADINGS = True


# =============================================================================
# Metadata
# =============================================================================

# Include page information in chunk metadata.
INCLUDE_PAGE_NUMBERS = True

# Include full heading hierarchy.
INCLUDE_HEADING_PATH = True

# Include document name.
INCLUDE_DOCUMENT_NAME = True

# Include source file path / URL.
INCLUDE_SOURCE = True


# =============================================================================
# Supported Object Types
# =============================================================================

OBJECT_TYPES = (
    "text",
    "table",
    "code",
    "list",
    "image_caption",
)


# =============================================================================
# Tokenizer
# =============================================================================

# Tokenizer used only for estimating chunk size.
TOKENIZER_NAME = "cl100k_base"


# =============================================================================
# Logging
# =============================================================================

LOG_LEVEL = "INFO"

VERBOSE = False