import json
import logging
from typing import Any, Dict, List
import requests
import numpy as np
import faiss
import os
from urllib.parse import urlparse
from sentence_transformers import SentenceTransformer
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, create_model
from fastapi import FastAPI

from mcp.server import Server
import mcp.types as types
import mcp.server.stdio
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_any_openapi")

def extract_base_url(url: str) -> str:
    """Extract base URL from a full URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

class EndpointSearcher:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
        self.endpoints = []
        self._initialize_endpoints()

    def _parse_schema_ref(self, schema_ref: str, components: Dict) -> Dict:
        """Parse schema reference and return the actual schema"""
        if not schema_ref.startswith('#/components/schemas/'):
            return {}
        
        schema_name = schema_ref.split('/')[-1]
        return components['schemas'].get(schema_name, {})

    def _format_schema(self, schema: Dict, components: Dict, indent: int = 0) -> str:
        """Format schema into readable text"""
        if not schema:
            return ""
            
        lines = []
        
        # Handle reference
        if '$ref' in schema:
            schema = self._parse_schema_ref(schema['$ref'], components)
        
        # Add type
        if 'type' in schema:
            lines.append(f"{'  ' * indent}Type: {schema['type']}")
        
        # Add description
        if 'description' in schema:
            lines.append(f"{'  ' * indent}Description: {schema['description']}")
        
        # Add properties
        if 'properties' in schema:
            lines.append(f"{'  ' * indent}Properties:")
            for prop_name, prop_schema in schema['properties'].items():
                lines.append(f"{'  ' * (indent + 1)}{prop_name}:")
                lines.append(self._format_schema(prop_schema, components, indent + 2))
        
        # Add required fields
        if 'required' in schema:
            lines.append(f"{'  ' * indent}Required: {', '.join(schema['required'])}")
            
        return '\n'.join(lines)

    def _create_endpoint_document(self, path: str, method: str, operation: Dict, components: Dict) -> str:
        """Create a complete document for an endpoint including all its details"""
        doc_parts = []
        
        # Basic info
        doc_parts.append(f"Path: {path}")
        doc_parts.append(f"Method: {method.upper()}")
        
        # Summary and description
        if 'summary' in operation:
            doc_parts.append(f"Summary: {operation['summary']}")
        if 'description' in operation:
            doc_parts.append(f"Description: {operation['description']}")
            
        # Tags
        if 'tags' in operation:
            doc_parts.append(f"Tags: {', '.join(operation['tags'])}")
            
        # Parameters
        if 'parameters' in operation:
            doc_parts.append("Parameters:")
            for param in operation['parameters']:
                param_doc = [f"  - {param['name']} ({param['in']})"]
                if 'description' in param:
                    param_doc.append(f"    Description: {param['description']}")
                if 'required' in param:
                    param_doc.append(f"    Required: {param['required']}")
                if 'schema' in param:
                    param_doc.append(f"    Schema:\n{self._format_schema(param['schema'], components, 3)}")
                doc_parts.append('\n'.join(param_doc))
                
        # Request Body
        if 'requestBody' in operation:
            doc_parts.append("Request Body:")
            body = operation['requestBody']
            if 'description' in body:
                doc_parts.append(f"  Description: {body['description']}")
            if 'content' in body:
                for content_type, content in body['content'].items():
                    doc_parts.append(f"  Content Type: {content_type}")
                    if 'schema' in content:
                        doc_parts.append(f"  Schema:\n{self._format_schema(content['schema'], components, 2)}")
                        
        # Responses
        if 'responses' in operation:
            doc_parts.append("Responses:")
            for status, response in operation['responses'].items():
                resp_doc = [f"  {status}:"]
                if 'description' in response:
                    resp_doc.append(f"    Description: {response['description']}")
                if 'content' in response:
                    for content_type, content in response['content'].items():
                        resp_doc.append(f"    Content Type: {content_type}")
                        if 'schema' in content:
                            resp_doc.append(f"    Schema:\n{self._format_schema(content['schema'], components, 3)}")
                doc_parts.append('\n'.join(resp_doc))
        
        return '\n'.join(doc_parts)

    def _initialize_endpoints(self):
        """Initialize endpoints from OpenAPI spec"""
        # Get OpenAPI spec URL from environment variable
        api_url = os.getenv('OPENAPI_JSON_DOCS_URL', 'https://raw.githubusercontent.com/seriousme/fastify-openapi-glue/refs/heads/master/examples/petstore/petstore-openapi.v3.json')
        
        # Extract base URL from OpenAPI spec URL and use it as default for API_REQUEST_BASE_URL
        default_base_url = extract_base_url(api_url)
        self.base_url = os.getenv('API_REQUEST_BASE_URL', default_base_url)
        
        logger.info(f"Using API base URL: {self.base_url}")
        
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            openapi_spec = response.json()
            
            # Extract endpoints with their full documentation
            for path, path_item in openapi_spec['paths'].items():
                for method, operation in path_item.items():
                    if method.lower() not in ['get', 'post', 'put', 'delete', 'patch']:
                        continue

                    # Create full document for the endpoint
                    doc = self._create_endpoint_document(path, method, operation, openapi_spec.get('components', {}))
                    
                    self.endpoints.append({
                        'path': path,
                        'method': method.upper(),
                        'document': doc,
                        'operation': operation
                    })

            # Create FAISS index
            if self.endpoints:
                # Create embeddings for full endpoint documents
                documents = [ep['document'] for ep in self.endpoints]
                embeddings = self.model.encode(documents)
                dimension = embeddings.shape[1]
                
                self.index = faiss.IndexFlatL2(dimension)
                self.index.add(np.array(embeddings).astype('float32'))
                logger.info(f"Successfully initialized FAISS index with {len(self.endpoints)} endpoints")
            else:
                logger.warning("No endpoints found in OpenAPI spec")

        except Exception as e:
            logger.error(f"Failed to initialize endpoints: {str(e)}")
            raise

    def search(self, query: str, k: int = 3) -> List[Dict]:
        """Search for endpoints matching the query"""
        if not self.index:
            return []

        # Create query embedding
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(np.array(query_embedding).astype('float32'), k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.endpoints):
                endpoint = self.endpoints[idx]
                results.append({
                    'path': endpoint['path'],
                    'method': endpoint['method'],
                    'operation': endpoint['operation'],
                    'document': endpoint['document']
                })
        
        return results


async def main():
    """Run the Any OpenAPI Server"""
    logger.info("Any OpenAPI Server starting")
    
    # Get API prefix from environment variable with default value
    api_prefix = os.getenv('MCP_API_PREFIX', 'any_openapi')
    server = Server(api_prefix)
    endpoint_searcher = EndpointSearcher()

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools"""
        return [
            types.Tool(
                name=f"{api_prefix}_api_request_schema",
                description="Get API endpoint schemas that match your intent. Returns endpoint details including path, method, parameters, and response formats.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Describe what you want to do with the API (e.g., 'Get user profile information', 'Create a new job posting')"
                        }
                    },
                    "required": ["query"]
                },
            ),
            types.Tool(
                name=f"{api_prefix}_make_request",
                description="Make an actual REST API request with full control over method, headers, body, and parameters.",
                inputSchema={
                    "type": "object",
                    "properties": {
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
                            "description": "Request headers",
                            "additionalProperties": {
                                "type": "string"
                            }
                        },
                        "query_params": {
                            "type": "object",
                            "description": "Query parameters",
                            "additionalProperties": {
                                "type": "string"
                            }
                        },
                        "body": {
                            "type": "object",
                            "description": "Request body (for POST, PUT, PATCH)",
                            "additionalProperties": True
                        }
                    },
                    "required": ["method", "url"]
                },
            )
        ]

    @server.call_tool()
    async def handle_invoke_tool(name: str, inputs: Dict[str, Any]) -> str:
        """Handle tool invocations"""
        try:
            schema_tool_name = f"{api_prefix}_api_request_schema"
            request_tool_name = f"{api_prefix}_make_request"

            if name == schema_tool_name:
                query = inputs["query"]
                results = endpoint_searcher.search(query)
                
                return [types.TextContent(type="text", text=json.dumps({
                    "api_base_url": endpoint_searcher.base_url,
                    "matching_endpoints": results
                }, indent=2))]
            elif name == request_tool_name:
                # Prepare request parameters
                method = inputs["method"]
                url = inputs["url"]  # Use the full URL directly
                
                # Optional parameters with defaults
                headers = inputs.get("headers", {})
                query_params = inputs.get("query_params", {})
                body = inputs.get("body", None)

                try:
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=query_params,
                        json=body if body else None
                    )
                    
                    # Try to parse response as JSON
                    try:
                        response_data = response.json()
                    except:
                        response_data = response.text

                    return [types.TextContent(type="text", text=json.dumps({
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response_data
                    }, indent=2))]

                except requests.exceptions.RequestException as e:
                    return [types.TextContent(type="text", text=json.dumps({
                        "error": str(e)
                    }, indent=2))]
            else:
                raise ValueError(f"Unknown tool: {name}")
                
        except Exception as e:
            logger.error(f"Error invoking tool {name}: {str(e)}")
            return [types.TextContent(type="text", text=json.dumps({
                "error": str(e)
            }, indent=2))]

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Server running with stdio transport")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="any_openapi",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
