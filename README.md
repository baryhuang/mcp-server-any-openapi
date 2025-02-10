# MCP Server: Scalable OpenAPI Endpoint Discovery and API Request Tool
[![Docker Hub](https://img.shields.io/docker/v/buryhuang/mcp-server-any-openapi?label=Docker%20Hub)](https://hub.docker.com/r/buryhuang/mcp-server-any-openapi)
[![smithery badge](https://smithery.ai/badge/@baryhuang/mcp-server-any-openapi)](https://smithery.ai/server/@baryhuang/mcp-server-any-openapi)

## TL'DR
**Why I create this**: I want to serve my private API, whose swagger openapi docs is a few hundreds KB in size.
- Claude MCP simply error on processing these size of file
- I attempted convert the result to YAML, not small enough and a lot of errors. FAILED
- I attempted to provide a API category, then ask MCP Client (Claude Desktop) to get the api doc by group. Still too big, FAILED.

Eventually I came down to this solution:
- It uses in-memory semantic search to find relevant Api endpoints by natural language (such as list products)
- It returns the complete end-point docs (as I designed it to store one endpoint as one chunk) in millionseconds (as it's in memory)

**Boom**, Claude now knows what API to call, with the **full parameters**!

Wait I have to create another tool in this server to make the actual restful request, because "fetch" server simply don't work, and I don't want to debug why.

https://github.com/user-attachments/assets/484790d2-b5a7-475d-a64d-157e839ad9b0

Technical highlights:
```python
query -> [Embedding] -> FAISS TopK -> OpenAPI docs -> MCP Client (Claude Desktop)
MCP Client -> Construct OpenAPI Request -> Execute Request -> Return Response
```

## Features

- 🧠 Use remote openapi json file as source, no local file system access, no updating required for API changes
- 🔍 Semantic search using optimized MiniLM-L3 model (43MB vs original 90MB)
- 🚀 FastAPI-based server with async support
- 🧠 Endpoint based chunking OpenAPI specs (handles 100KB+ documents), no loss of endpoint context
- ⚡ In-memory FAISS vector search for instant endpoint discovery

## Limitations
- 🐢 Cold start penalty (~15s for model loading) if not using docker image
- Current docker image disabled downloading models. You have a dependency over huggingface. When you load the Claude Desktop, it takes some time to download the model. If huggingface is down, your server will not start.


## Multi-instance config example

Here is the multi-instance config example. I design it so it can more flexibly used for multiple set of apis:
```
{
  "mcpServers": {
    "finance_openapi": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "OPENAPI_JSON_DOCS_URL=https://api.finance.com/openapi.json",
        "-e",
        "MCP_API_PREFIX=finance",
        "buryhuang/mcp-server-any-openapi:latest"
      ]
    },
    "healthcare_openapi": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "OPENAPI_JSON_DOCS_URL=https://api.healthcare.com/openapi.json",
        "-e",
        "MCP_API_PREFIX=healthcare",
        "buryhuang/mcp-server-any-openapi:latest"
      ]
    }
  }
}
```

## Claude Desktop Usage Example
Claude Desktop Project Prompt:
```
You should get the api spec details from tools financial_api_request_schema

You task is use financial_make_request tool to make the requests to get response. You should follow the api spec to add authorization header:
Authorization: Bearer <xxxxxxxxx>

The api base_url is https://api.example.com
```
In chat, you can do:
```
Get prices for all stocks
```


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

### Installing via Smithery

To install Scalable OpenAPI Endpoint Discovery and API Request Tool for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@baryhuang/mcp-server-any-openapi):

```bash
npx -y @smithery/cli install @baryhuang/mcp-server-any-openapi --client claude
```

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

### Multi-Architecture Builds
Official images support 3 platforms:
```bash
# Build and push using buildx
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t buryhuang/mcp-server-any-openapi:latest \
  --push .
```

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

### Option 1: Use Prebuilt Image (Docker Hub)

```bash
docker pull buryhuang/mcp-server-any-openapi:latest
```

### Option 2: Local Development Build

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
