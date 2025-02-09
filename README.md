# MCP Server: Scalable OpenAPI Endpoint Discovery and API Request Tool

**Production-grade solution for API spec analysis** - An async FastAPI service that indexes and queries OpenAPI endpoints using endpoint-centric semantic search. Solves Claude MCP's silent failures with large specs (>100KB) through:
- **Vectorized endpoint indexing**: 384D MiniLM-L3 embeddings (43MB) + FAISS in-memory search
- **Streamlined parsing**: Processes 10MB specs (~5k endpoints) in <3s via parallel JSON decoding
- **Reliable execution**: Built-in `make_request` tool handles complex API calls that break naive implementations

Technical highlights:
```python
query -> [Embedding] -> FAISS TopK -> OpenAPI docs -> MCP Client (Claude Desktop)
MCP Client -> Construct OpenAPI Request -> Execute Request -> Return Response
```

## Usage Example
Claude Desktop Project Prompt:
```
You should get the api spec details from tools financial_api_request_schema

You task is use financial_make_request tool to make the requests to get response. You should follow the api spec to add authorization header:
Authorization: Bearer <xxxxxxxxx>
```
In chat, you can do:
```
Get prices for all stocks
```


## Features

- 🏗️ Multiple deployment options:
  - Public Docker image (`buryhuang/mcp-server-any-openapi`)
  - Local Python package (`pip install`)
- 🔍 Semantic search using optimized MiniLM-L3 model (43MB vs original 90MB)
- 📚 Comprehensive endpoint documentation including parameters, request bodies, and responses
- 🚀 FastAPI-based server with async support
- 🐳 Multi-platform Docker support
- 🧠 Intelligent chunking for large OpenAPI specs (handles 100KB+ documents)
- ⚡ In-memory FAISS vector search for instant endpoint discovery
- 🐢 Cold start penalty (~15s for model loading)

## Challenges Addressed

This server specifically solves:
1. **Oversized OpenAPI Processing**  
   Fixes Claude MCP's silent failures with API specs >100KB through:
   - Per-endpoint semantic indexing (avoids whole-doc processing)
   - Streamlined JSON parsing that ignores non-essential fields
   - Error-resistant chunking that maintains endpoint context

2. **Scalable Vector Search**  
   In-memory indexing enables:
   - Instant search across complex API landscapes
   - Async processing of 100+ concurrent queries
   - Efficient memory usage (~10KB per endpoint)

## Known Limitations

1. **Initialization Delay**  
   First startup requires:
   - ~15s for embedding model download (one-time)
   - ~3s model loading on each server start
   - Mitigation: Keep container warm or use larger instance types

2. **Embedding Quality Tradeoff**  
   Smaller model has:
   - 384-dim vs original 768-dim embeddings
   - 5% lower accuracy on technical text
   - Still outperforms whole-document processing

## Installation

### Using pip

```bash
pip install mcp-server-any-openapi
```

## Configuration

Customize through environment variables:

- `OPENAPI_JSON_DOCS_URL`: URL to the OpenAPI specification JSON (defaults to https://api.staging.readymojo.com/openapi.json)
- `MCP_API_PREFIX`: Customizable tool namespace (default "any_openapi"):
  ```bash
  # Creates tools: custom_api_request_schema and custom_make_request
  docker run -e MCP_API_PREFIX=finance ...
  ```

## Available Tools

The server provides the following tools (where `{prefix}` is determined by `MCP_API_PREFIX`):

### {prefix}_api_request_schema
Get API endpoint schemas that match your intent. Returns endpoint details including path, method, parameters, and response formats.

**Input Schema:**
```json
{
    "query": {
        "type": "string",
        "description": "Describe what you want to do with the API (e.g., 'Get user profile information', 'Create a new job posting')"
    }
}
```

### {prefix}_make_request
**Essential for reliable execution** with complex APIs where simplified implementations fail. Provides:

**Input Schema:**
```json
{
    "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
    },
    "url": {
        "type": "string",
        "description": "Fully qualified API URL (e.g., https://api.example.com/users/123)"
    },
    "headers": {
        "type": "object",
        "description": "Request headers (optional)",
        "additionalProperties": {
            "type": "string"
        }
    },
    "query_params": {
        "type": "object",
        "description": "Query parameters (optional)",
        "additionalProperties": {
            "type": "string"
        }
    },
    "body": {
        "type": "object",
        "description": "Request body for POST, PUT, PATCH (optional)"
    }
}
```

**Response Format:**
```json
{
    "status_code": 200,
    "headers": {
        "content-type": "application/json",
        ...
    },
    "body": {
        // Response data
    }
}
```

## Docker Support

### Flexible Tool Naming
Control tool names through `MCP_API_PREFIX`:
```bash
# Produces tools with "finance_api" prefix:
docker run -e MCP_API_PREFIX=finance_ ...
```

### Supported Platforms
- linux/amd64
- linux/arm64
- linux/arm/v7

### Option 1: Pull from Docker Hub

```bash
docker pull buryhuang/mcp-server-any-openapi:latest
```

### Option 2: Build Locally

```bash
docker build -t mcp-server-any-openapi .
```

### Running the Container

```bash
docker run \
  -e OPENAPI_JSON_DOCS_URL=https://api.example.com/openapi.json \
  -e MCP_API_PREFIX=finance \
  buryhuang/mcp-server-any-openapi:latest
```


### Key Components

1. **EndpointSearcher**: Core class that handles:
   - OpenAPI specification parsing
   - Semantic search index creation
   - Endpoint documentation formatting
   - Natural language query processing

2. **Server Implementation**:
   - Async FastAPI server
   - MCP protocol support
   - Tool registration and invocation handling

### Running from Source

```bash
python -m mcp_server_any_openapi
```

## Integration with Claude Desktop

Configure the MCP server in your Claude Desktop settings:

```json
{
  "mcpServers": {
    "any_openapi": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "OPENAPI_JSON_DOCS_URL=https://api.example.com/openapi.json",
        "-e",
        "MCP_API_PREFIX=finance",
        "buryhuang/mcp-server-any-openapi:latest"
      ]
    }
  }
}
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the terms included in the LICENSE file.

## Implementation Notes

- **Endpoint-Centric Processing**: Unlike document-level analysis that struggles with large specs, we index individual endpoints with:
  - Path + Method as unique identifiers
  - Parameter-aware embeddings
  - Response schema context
- **Optimized Spec Handling**: Processes OpenAPI specs up to 10MB (~5,000 endpoints) through:
  - Lazy loading of schema components
  - Parallel parsing of path items
  - Selective embedding generation (omits redundant descriptions)
