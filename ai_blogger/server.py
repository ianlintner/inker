#!/usr/bin/env python3
"""AI Blogger API Server.

This module provides the server entry point for the Phase 2 API.

Usage:
    python -m ai_blogger.server [--host HOST] [--port PORT] [--reload]

    or:

    uvicorn ai_blogger.api:create_app --factory --host 0.0.0.0 --port 8000
"""

import argparse
import logging
import sys


def main():
    """Main entry point for the API server."""
    parser = argparse.ArgumentParser(
        description="AI Blogger API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with default settings
    python -m ai_blogger.server

    # Run on custom host/port
    python -m ai_blogger.server --host 0.0.0.0 --port 8080

    # Run with auto-reload for development
    python -m ai_blogger.server --reload
""",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Install it with: pip install uvicorn")
        sys.exit(1)

    print("=" * 60)
    print("AI BLOGGER API SERVER")
    print("=" * 60)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print(f"Workers: {args.workers}")
    print(f"Log Level: {args.log_level}")
    print()
    print(f"OpenAPI docs: http://{args.host}:{args.port}/docs")
    print(f"Redoc docs: http://{args.host}:{args.port}/redoc")
    print("=" * 60)

    uvicorn.run(
        "ai_blogger.api.app:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
        factory=True,
    )


if __name__ == "__main__":
    main()
