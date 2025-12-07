# TemporalMemAI

A temporal-aware AI memory engine that extracts, stores, and retrieves long-term user memories with built-in decay, versioning, and freshness scoring.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Temporal Awareness**: Built-in memory decay, versioning, and freshness scoring
- **Semantic Search**: Vector-based search using OpenAI embeddings and Qdrant
- **Reranking Support**: Optional reranking with Cohere, HuggingFace, or LLM-based rerankers
- **Dual Storage**: SQLite for metadata and Qdrant for vector embeddings
- **Conflict Resolution**: Slot-based superseding for handling memory updates
- **Fact Extraction**: LLM-powered extraction of structured facts from conversations
- **User Isolation**: Multi-user support with per-user memory management

## Installation

### Basic Installation

```bash
pip install temporalmemai
```

### With Optional Dependencies

```bash
# With Cohere reranker support
pip install temporalmemai[cohere]

# With HuggingFace reranker support
pip install temporalmemai[huggingface]

# With all optional dependencies
pip install temporalmemai[all]
```

### Development Installation

```bash
git clone https://github.com/29m10/temporalmemai.git
cd temporalmemai
pip install -e .
```

## Prerequisites

- Python 3.13+
- Qdrant (local or cloud)
- OpenAI API key (for embeddings and fact extraction)

## Quick Start

```python
from temporalmemai import Memory

# Configure the memory engine
config = {
    "sqlite_path": "./my_memory.db",
    "qdrant_host": "localhost",
    "qdrant_port": 6333,
    "openai_api_key": "your-api-key",
}

# Create memory instance
memory = Memory(config)

# Add memories
memory.add("I love hiking on weekends.", user_id="user123")
memory.add("My favorite programming language is Python.", user_id="user123")

# Search memories
results = memory.search(
    query="what are my hobbies?",
    user_id="user123",
    limit=5
)

for result in results["results"]:
    print(result["memory"]["memory"])
```

## Configuration

### Environment Variables

You can configure the system using environment variables:

```bash
export SQLITE_PATH="./my_memory.db"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
export QDRANT_URL="https://your-cluster.qdrant.io"  # For Qdrant Cloud
export QDRANT_API_KEY="your-qdrant-api-key"
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_EMBED_MODEL="text-embedding-3-small"
export OPENAI_LLM_MODEL="gpt-4o-mini"
```

### Configuration Dictionary

```python
config = {
    # SQLite database path
    "sqlite_path": "./my_memory.db",
    
    # Qdrant configuration (choose one)
    "qdrant_host": "localhost",      # For local Qdrant
    "qdrant_port": 6333,
    # OR
    "qdrant_url": "https://...",      # For Qdrant Cloud
    "qdrant_api_key": "your-key",
    "qdrant_collection": "temporalmemai_default",
    
    # OpenAI configuration
    "openai_api_key": "your-key",
    "embed_model": "text-embedding-3-small",
    "llm_model": "gpt-4o-mini",
    "llm_temperature": 0.0,
    
    # Optional: Reranker configuration
    "reranker": {
        "provider": "huggingface",  # or "cohere" or "llm_reranker"
        "config": {
            "model": "BAAI/bge-reranker-base",
            "device": "cpu",
            "batch_size": 8,
        }
    }
}
```

## Usage Examples

### Adding Memories

```python
# Single message
memory.add("I live in San Francisco.", user_id="user123")

# Conversation history
messages = [
    {"role": "user", "content": "I'm planning a trip to Japan."},
    {"role": "assistant", "content": "That sounds exciting!"},
    {"role": "user", "content": "I'll be there for two weeks in March."}
]
memory.add(messages, user_id="user123", metadata={"turn_id": "conv_001"})
```

### Searching Memories

```python
# Basic search
results = memory.search(
    query="where do I live?",
    user_id="user123",
    limit=10
)

# Search with reranking
results = memory.search(
    query="what are my travel plans?",
    user_id="user123",
    rerank=True,  # Enable reranking if configured
    limit=5
)

# Search with filters
results = memory.search(
    query="my preferences",
    user_id="user123",
    filters={"type": "preference", "status": "active"},
    limit=10
)
```

### Listing Memories

```python
# List all active memories
memories = memory.list(user_id="user123", status="active")

# List archived memories
archived = memory.list(user_id="user123", status="archived")
```

### Managing Memories

```python
# Update a memory
memory.update(memory_id="mem_123", new_content="I live in New York.")

# Delete a memory
memory.delete(memory_id="mem_123")

# Reindex user memories (rebuild Qdrant index)
stats = memory.reindex_user(user_id="user123")
print(f"Reindexed: {stats['indexed']}/{stats['total']}")
```

### Memory Expiry and Temporal Behavior

TemporalMemAI automatically handles memory expiry based on temporal information extracted from messages. Memories with explicit durations are automatically expired when they pass their `valid_until` timestamp.

```python
# Memories with explicit durations are automatically expired
# Example: Temporary location with duration
memory.add("I'm at the airport, will be here for 2 hours.", user_id="user123")
# This memory will automatically expire after 2 hours

# Example: Short-term travel plans
memory.add("I'm staying in Tokyo for 3 days.", user_id="user123")
# This memory expires after 3 days

# Example: Very short-term state
memory.add("I'm waiting for my cab, it will arrive in 30 minutes.", user_id="user123")
# This memory expires after 30 minutes

# The system automatically expires memories when you call add(), list(), or search()
# Expired memories are marked as "expired" status and excluded from active searches
```

**How Expiry Works:**

1. **Automatic Duration Detection**: When you add a memory, the system extracts explicit durations (minutes, hours, days) from the text
2. **TTL Assignment**: Memories with durations get a `valid_until` timestamp automatically set
3. **Lazy Expiration**: Memories are checked and expired when you call `add()`, `list()`, or `search()`
4. **Type-Based Defaults**: Different memory types have different default expiry behaviors:
   - `temp_state`: Short-lived, expires quickly
   - `episodic_event`: Time-stamped, doesn't decay but may become less relevant
   - `profile_fact`: Long-lived, rarely expires
   - `preference`: Medium-lived, may change over time

**Checking Memory Expiry:**

```python
# List all memories (including expired ones)
all_memories = memory.list(user_id="user123", status="active")

# Check individual memory expiry
for mem in all_memories["results"]:
    if mem.get("valid_until"):
        print(f"Memory '{mem['memory']}' expires at {mem['valid_until']}")
    else:
        print(f"Memory '{mem['memory']}' has no expiry (persistent)")
```

## Architecture

TemporalMemAI uses a dual-storage architecture:

- **SQLite**: Stores metadata, relationships, and temporal information
- **Qdrant**: Stores vector embeddings for semantic search

The system processes memories through:
1. **Fact Extraction**: LLM extracts structured facts from conversations
2. **Temporal Processing**: Applies decay, versioning, and conflict resolution
3. **Vector Indexing**: Embeds and indexes memories in Qdrant
4. **Search & Reranking**: Semantic search with optional reranking

## Rerankers

TemporalMemAI supports multiple reranking strategies:

### HuggingFace Reranker (Recommended for Local)

```python
config = {
    "reranker": {
        "provider": "huggingface",
        "config": {
            "model": "BAAI/bge-reranker-base",
            "device": "cpu",  # or "cuda"
            "batch_size": 8,
            "max_length": 512,
        }
    }
}
```

### Cohere Reranker

```python
config = {
    "reranker": {
        "provider": "cohere",
        "config": {
            "model": "rerank-english-v3.0",
            "api_key": "your-cohere-api-key",
        }
    }
}
```

### LLM Reranker (OpenAI)

```python
config = {
    "reranker": {
        "provider": "llm_reranker",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 50,
        }
    }
}
```

## Memory Types

The system supports different memory types with temporal characteristics:

- **`profile_fact`**: Long-lived profile information
- **`preference`**: User preferences (medium-lived)
- **`episodic_event`**: Time-stamped events
- **`temp_state`**: Short-lived temporary state
- **`task_state`**: Task-specific state

## API Reference

### `Memory(config: dict[str, Any] | None = None)`

Main memory engine class.

**Methods:**

- `add(messages: str | list[dict], user_id: str, metadata: dict | None = None) -> dict`
  - Add memories from text or conversation history

- `search(query: str, user_id: str, filters: dict | None = None, limit: int = 10, rerank: bool = False) -> dict`
  - Search memories semantically

- `list(user_id: str, status: str = "active") -> dict`
  - List memories for a user

- `update(memory_id: str, new_content: str) -> dict | None`
  - Update an existing memory

- `delete(memory_id: str) -> None`
  - Delete a memory

- `reindex_user(user_id: str, status: str = "active") -> dict`
  - Rebuild Qdrant index for a user

## Development

### Setup Development Environment

```bash
git clone https://github.com/29m10/temporalmemai.git
cd temporalmemai
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[all]"
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy temporalmemai
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Links

- **Repository**: [https://github.com/29m10/temporalmemai](https://github.com/29m10/temporalmemai)
- **Issues**: [https://github.com/29m10/temporalmemai/issues](https://github.com/29m10/temporalmemai/issues)
- **Documentation**: [https://github.com/29m10/temporalmemai#readme](https://github.com/29m10/temporalmemai#readme)

## Acknowledgments

- Built with [OpenAI](https://openai.com/) for embeddings and LLM
- Uses [Qdrant](https://qdrant.tech/) for vector storage
- Inspired by temporal memory systems in cognitive science
