# Technical Documentation

## System Architecture

### Overview

`temporal-mem` implements a dual-storage architecture with temporal awareness. The system processes conversational input through a pipeline that extracts facts, applies temporal logic, and stores both structured metadata and vector embeddings.

### Component Flow

```
User Input (messages)
    ↓
FactExtractor (LLM-based extraction)
    ↓
FactCandidate[] (structured facts)
    ↓
TemporalEngine (temporal processing, conflict resolution)
    ↓
MemoryModel[] (temporal-aware memories)
    ↓
    ├─→ SqliteStore (metadata, relationships)
    └─→ QdrantStore (vector embeddings via OpenAIEmbedder)
```

## Core Components

### 1. Memory (Facade)

**Location**: `temporal_mem/memory.py`

The `Memory` class serves as the public API facade. It orchestrates all components and provides a unified interface.

**Responsibilities:**
- Component initialization and configuration
- Request routing to appropriate components
- Result aggregation

**Initialization Flow:**
1. Parse configuration with defaults
2. Initialize `SqliteStore` for metadata
3. Initialize `TemporalEngine` with metadata store
4. Initialize `FactExtractor` with LLM configuration
5. Initialize `OpenAIEmbedder` for embeddings
6. Initialize `QdrantStore` for vector storage

**Configuration Parameters:**
- `sqlite_path`: File path for SQLite database (default: `~/.temporal_mem/history.db`)
- `qdrant_host`: Qdrant server hostname (default: `localhost`)
- `qdrant_port`: Qdrant server port (default: `6333`)
- `qdrant_collection`: Collection name in Qdrant (default: `temporal_mem_default`)
- `openai_api_key`: API key for OpenAI services
- `embed_model`: Embedding model identifier (default: `text-embedding-3-small`)
- `llm_model`: LLM model for fact extraction (default: `gpt-4.1-mini`)
- `llm_temperature`: Temperature for LLM generation (default: `0.0`)

### 2. FactExtractor

**Location**: `temporal_mem/llm/extractor.py`

Extracts structured facts from natural language using LLM calls.

**Interface:**
```python
class FactExtractor:
    def extract_from_message(message: str) -> list[FactCandidate]
    def extract_from_messages(messages: list[dict[str, str]]) -> list[FactCandidate]
```

**Design Notes:**
- Uses OpenAI API for fact extraction
- Returns `FactCandidate` objects with structured data
- Supports both single message and conversation history
- Configurable model and temperature

**Current Status:** Stub implementation (Day 1)

### 3. TemporalEngine

**Location**: `temporal_mem/temporal/engine.py`

Core temporal logic engine that handles:
- Fact-to-Memory transformation
- Conflict resolution via slot-based superseding
- Temporal filtering and ranking

**Interface:**
```python
class TemporalEngine:
    def process_write_batch(
        facts: list[FactCandidate],
        user_id: str,
        source_turn_id: str | None = None
    ) -> list[MemoryModel]
    
    def filter_and_rank(memories: list[MemoryModel]) -> list[MemoryModel]
```

**Key Concepts:**

#### Slot-Based Conflict Resolution
- Memories can have a `slot` identifier (e.g., "favorite_food", "current_location")
- When a new memory with the same slot is created, it supersedes older memories
- The `supersedes` field tracks which memories are replaced
- Old memories are marked as superseded, not deleted

#### Temporal Decay
- Each memory can have a `decay_half_life_days` parameter
- Memories decay over time, reducing their relevance score
- Used in `filter_and_rank` to prioritize fresher memories

#### Memory Types
Different types have different temporal characteristics:
- `profile_fact`: Long-lived, rarely changes
- `preference`: Medium-lived, may change over time
- `episodic_event`: Time-stamped, doesn't decay but may become less relevant
- `temp_state`: Short-lived, expires quickly
- `task_state`: Task-specific, expires when task completes

**Current Status:** Stub implementation (Day 1)

### 4. OpenAIEmbedder

**Location**: `temporal_mem/embedding/openai_embedder.py`

Generates vector embeddings for semantic search.

**Interface:**
```python
class OpenAIEmbedder:
    def embed(text: str) -> list[float]
```

**Technical Details:**
- Uses OpenAI's embedding API
- Default model: `text-embedding-3-small`
- Returns fixed-size vector (1536 dimensions for default model)
- Embeddings are used for semantic similarity search in Qdrant

**Current Status:** Stub implementation (Day 1) - returns dummy vectors

### 5. SqliteStore

**Location**: `temporal_mem/storage/sqlite_store.py`

Stores metadata and relationships for memories.

**Interface:**
```python
class SqliteStore:
    def insert(mem: MemoryModel) -> None
    def get_by_id(mem_id: str) -> MemoryModel | None
    def update_status(mem_id: str, new_status: str) -> None
    def get_active_by_slot(user_id: str, slot: str) -> list[MemoryModel]
    def list_by_user(user_id: str, status: str = "active") -> list[MemoryModel]
    def list_by_ids(ids: list[str]) -> list[MemoryModel]
```

**Schema Design (Planned):**

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    memory TEXT NOT NULL,
    type TEXT NOT NULL,
    slot TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    valid_until TEXT,
    decay_half_life_days INTEGER,
    confidence REAL DEFAULT 1.0,
    source_turn_id TEXT,
    extra TEXT,  -- JSON
    FOREIGN KEY (supersedes) REFERENCES memories(id)
);

CREATE TABLE supersedes (
    memory_id TEXT,
    superseded_id TEXT,
    PRIMARY KEY (memory_id, superseded_id),
    FOREIGN KEY (memory_id) REFERENCES memories(id),
    FOREIGN KEY (superseded_id) REFERENCES memories(id)
);

CREATE INDEX idx_user_status ON memories(user_id, status);
CREATE INDEX idx_user_slot ON memories(user_id, slot) WHERE status = 'active';
CREATE INDEX idx_created_at ON memories(created_at);
```

**Key Operations:**
- `get_active_by_slot`: Critical for conflict resolution - finds existing active memories in a slot
- `list_by_user`: Retrieves all memories for a user, filtered by status
- `list_by_ids`: Batch retrieval for vector search results

**Current Status:** Stub implementation (Day 1)

### 6. QdrantStore

**Location**: `temporal_mem/storage/qdrant_store.py`

Stores and searches vector embeddings using Qdrant.

**Interface:**
```python
class QdrantStore:
    def upsert(mem: MemoryModel, embedding: list[float]) -> None
    def delete(mem_id: str) -> None
    def search(
        user_id: str,
        query_embedding: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[str, float]]  # (memory_id, similarity_score)
```

**Technical Details:**
- Uses Qdrant's Python client
- Stores vectors with memory IDs as payload
- Supports filtering by user_id and other metadata
- Returns similarity scores (cosine similarity by default)
- Vector size: 1536 (for `text-embedding-3-small`)

**Qdrant Collection Structure:**
- Vector dimension: 1536
- Distance metric: Cosine (default)
- Payload includes: `user_id`, `memory_id`, `type`, `status`, etc.

**Current Status:** Stub implementation (Day 1)

## Data Models

### FactCandidate

**Location**: `temporal_mem/models.py`

Represents a fact extracted from text.

```python
class FactCandidate(BaseModel):
    text: str                    # The fact text
    category: str                # Fact category
    slot: str | None = None      # Optional slot for conflict resolution
    confidence: float = 1.0      # Extraction confidence (0.0-1.0)
```

**Categories:**
- `"profile"`: User profile information
- `"preference"`: User preferences
- `"event"`: Specific events
- `"temp_state"`: Temporary state
- `"other"`: Uncategorized

**Usage:**
- Output of `FactExtractor`
- Input to `TemporalEngine.process_write_batch`

### MemoryModel

**Location**: `temporal_mem/models.py`

Represents a stored memory with full temporal metadata.

```python
class MemoryModel(BaseModel):
    id: str                      # Unique identifier (UUID)
    user_id: str                 # User identifier
    memory: str                  # Memory content text
    type: str                    # Memory type
    slot: str | None = None      # Slot for conflict resolution
    status: str = "active"       # Status: "active" | "archived" | "deleted"
    created_at: str              # ISO 8601 timestamp
    valid_until: str | None = None  # Expiration timestamp
    decay_half_life_days: int | None = None  # Decay rate
    confidence: float = 1.0      # Confidence score
    supersedes: list[str] = []   # IDs of superseded memories
    source_turn_id: str | None = None  # Source conversation turn ID
    extra: dict = {}             # Additional metadata (JSON)
```

**Memory Types:**
- `"profile_fact"`: Long-term profile information
- `"preference"`: User preferences
- `"episodic_event"`: Time-stamped events
- `"temp_state"`: Temporary state
- `"task_state"`: Task-related state
- `"other"`: Uncategorized

**Temporal Fields:**
- `created_at`: When the memory was created
- `valid_until`: Optional expiration time
- `decay_half_life_days`: Half-life for exponential decay calculation
- `supersedes`: Tracks which memories this one replaces

## Data Flow

### Write Path (add)

```
1. User calls memory.add(messages, user_id, metadata)
   ↓
2. FactExtractor.extract_from_messages(messages)
   → Returns: list[FactCandidate]
   ↓
3. TemporalEngine.process_write_batch(facts, user_id, source_turn_id)
   → For each fact:
     a. Check for existing memories in same slot (SqliteStore.get_active_by_slot)
     b. Create MemoryModel with temporal metadata
     c. Mark old memories as superseded
   → Returns: list[MemoryModel]
   ↓
4. For each MemoryModel:
   a. OpenAIEmbedder.embed(memory.memory)
     → Returns: list[float] (embedding vector)
   b. SqliteStore.insert(memory)
   c. QdrantStore.upsert(memory, embedding)
   ↓
5. Return results with created memory IDs
```

### Read Path (search)

```
1. User calls memory.search(query, user_id, filters, limit)
   ↓
2. OpenAIEmbedder.embed(query)
   → Returns: list[float] (query embedding)
   ↓
3. QdrantStore.search(user_id, query_embedding, limit, filters)
   → Returns: list[tuple[str, float]] (memory_id, similarity_score)
   ↓
4. SqliteStore.list_by_ids([memory_id, ...])
   → Returns: list[MemoryModel]
   ↓
5. TemporalEngine.filter_and_rank(memories)
   → Apply temporal decay
   → Rank by freshness and relevance
   → Returns: list[MemoryModel] (sorted)
   ↓
6. Return results
```

### List Path

```
1. User calls memory.list(user_id, status)
   ↓
2. SqliteStore.list_by_user(user_id, status)
   → Returns: list[MemoryModel]
   ↓
3. TemporalEngine.filter_and_rank(memories)
   → Apply temporal filtering
   → Returns: list[MemoryModel] (sorted)
   ↓
4. Return results
```

## Temporal Logic

### Decay Calculation

Memories decay over time using exponential decay:

```
relevance_score = base_score * (0.5 ^ (days_since_creation / half_life_days))
```

Where:
- `base_score`: Initial confidence or similarity score
- `days_since_creation`: Time elapsed since `created_at`
- `half_life_days`: Decay rate from `decay_half_life_days`

If `decay_half_life_days` is `None`, no decay is applied.

### Conflict Resolution

When a new memory is created with a `slot` that already has active memories:

1. Retrieve existing active memories in the slot: `SqliteStore.get_active_by_slot(user_id, slot)`
2. Create new memory with `supersedes` field containing IDs of old memories
3. Update old memories: set `status = "archived"` (or mark as superseded)
4. Insert new memory as `status = "active"`

This ensures only the most recent memory in a slot is active, while preserving history.

### Ranking Algorithm

The `filter_and_rank` method combines multiple factors:

1. **Similarity Score**: From vector search (for search queries)
2. **Temporal Decay**: Based on age and half-life
3. **Confidence**: Extraction confidence score
4. **Status**: Only "active" memories are considered
5. **Validity**: Memories past `valid_until` are excluded

Final score calculation (planned):
```
final_score = similarity * decay_factor * confidence
```

## Storage Architecture

### Dual Storage Design

The system uses two storage backends:

1. **SQLite (Metadata)**
   - Fast relational queries
   - ACID transactions
   - Slot-based lookups
   - User filtering
   - Relationship tracking (supersedes)

2. **Qdrant (Vectors)**
   - Semantic similarity search
   - High-dimensional vector operations
   - Fast approximate nearest neighbor search
   - Metadata filtering

**Why Dual Storage?**
- SQLite excels at structured queries (user_id, slot, status)
- Qdrant excels at vector similarity search
- Combining both provides optimal performance for different query patterns

### Data Consistency

- Memory IDs are used as foreign keys between stores
- Write operations should be atomic (transactional)
- Vector store is updated after metadata store (to ensure referential integrity)
- On read, both stores are queried and results are merged

## Error Handling

### Current Status

Most components are stubs and raise `NotImplementedError`. Future implementation should handle:

- **API Failures**: OpenAI API rate limits, network errors
- **Storage Failures**: Database connection errors, Qdrant unavailability
- **Data Validation**: Invalid memory types, malformed timestamps
- **Conflict Errors**: Concurrent writes to same slot

### Planned Error Handling Strategy

- Retry logic for transient failures
- Graceful degradation (e.g., fallback to metadata-only search if Qdrant unavailable)
- Validation at API boundaries
- Transaction rollback on partial failures

## Performance Considerations

### Optimization Opportunities

1. **Batch Operations**: Process multiple facts in single batch
2. **Embedding Caching**: Cache embeddings for repeated queries
3. **Indexing**: Proper database indexes on user_id, slot, status
4. **Vector Search**: Tune Qdrant HNSW parameters for speed/accuracy tradeoff
5. **Connection Pooling**: Reuse database and API connections

### Scalability

- SQLite: Suitable for single-machine deployments, may need migration to PostgreSQL for scale
- Qdrant: Horizontally scalable, supports clustering
- Stateless design: Components can be distributed across services

## Future Implementation Notes

### FactExtractor Implementation

Should:
- Use OpenAI's function calling or structured output
- Parse LLM response into `FactCandidate` objects
- Handle extraction errors gracefully
- Support custom prompts via `base_prompt` parameter

### TemporalEngine Implementation

Should:
- Implement decay calculation in `filter_and_rank`
- Implement conflict resolution in `process_write_batch`
- Handle edge cases (no half-life, expired memories, etc.)
- Support custom ranking strategies

### Storage Implementations

**SqliteStore:**
- Use SQLAlchemy or raw SQL with proper schema
- Implement connection pooling
- Add migration support
- Handle concurrent access

**QdrantStore:**
- Use `qdrant-client` library
- Implement collection creation if missing
- Handle connection errors
- Support batch upserts

## Testing Strategy

### Unit Tests
- Component isolation
- Mock external dependencies (OpenAI, Qdrant)
- Test temporal logic calculations
- Test conflict resolution scenarios

### Integration Tests
- End-to-end write/read flows
- Multi-user scenarios
- Concurrent access patterns
- Error recovery

### Performance Tests
- Vector search latency
- Batch write throughput
- Memory usage under load

