import argparse
import asyncio
import logging
from . import server

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('mcp_server_any_openapi')

def main():
    """Validate command-line arguments and start the MCP server."""
    logger.debug("Starting mcp-server-any-openapi main()")
    parser = argparse.ArgumentParser(description='Any OpenAPI MCP Server')
    parser.parse_args()

    # Run the async main function
    logger.debug("About to run server.main()")
    asyncio.run(server.main())
    logger.debug("Server main() completed")

if __name__ == "__main__":
    main()

# Expose important items at package level
__all__ = ["main", "server"]
