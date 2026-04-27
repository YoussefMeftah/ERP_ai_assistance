"""
Main entry point for the ERP AI Assistant.

Builds the LangGraph and provides HTTP server interface.
"""

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from state import AssistantState
from config import config
from nodes import (
    classify_question,
    retrieve_candidate_endpoints,
    select_endpoint_and_params,
    call_webapi,
    llama_nosql_query_generator,
    execute_mongodb_query,
    format_mongodb_results,
)


def build_graph():
    """Build and compile the LangGraph assistant workflow with MongoDB + Llama NoSQL.
    
    New Graph structure (MongoDB + NoSQL queries):
        START
          ↓
        classify_question (intent, domain)
          ↓
        retrieve_candidate_endpoints (score endpoints)
          ↓
        select_endpoint_and_params (DeepSeek or score-based)
          ↓
        call_webapi (execute API calls + save to MongoDB)
          ↓
        llama_nosql_query_generator (Llama generates MongoDB aggregation pipeline)
          ↓
        execute_mongodb_query (Execute NoSQL query, return results only)
          ↓
        END
    
    Returns:
        Compiled LangGraph application
    """
    graph = StateGraph(AssistantState)
    
    # Add nodes
    graph.add_node("classify_question", classify_question)
    graph.add_node("retrieve_candidate_endpoints", retrieve_candidate_endpoints)
    graph.add_node("select_endpoint_and_params", select_endpoint_and_params)
    graph.add_node("call_webapi", call_webapi)
    graph.add_node("llama_nosql_query_generator", llama_nosql_query_generator)
    graph.add_node("execute_mongodb_query", execute_mongodb_query)
    graph.add_node("format_mongodb_results", format_mongodb_results)
    
    # Add edges (linear flow with MongoDB + NoSQL)
    graph.add_edge(START, "classify_question")
    graph.add_edge("classify_question", "retrieve_candidate_endpoints")
    graph.add_edge("retrieve_candidate_endpoints", "select_endpoint_and_params")
    graph.add_edge("select_endpoint_and_params", "call_webapi")
    graph.add_edge("call_webapi", "llama_nosql_query_generator")
    graph.add_edge("llama_nosql_query_generator", "execute_mongodb_query")
    graph.add_edge("execute_mongodb_query", "format_mongodb_results")
    graph.add_edge("format_mongodb_results", END)
    
    return graph.compile()


def run_once(question: str) -> AssistantState:
    """Run the assistant once on a single question.
    
    Args:
        question: User's question
    
    Returns:
        Final state with answer and metadata
    """
    app = build_graph()
    result = app.invoke({"question": question, "errors": []})
    return result


class AssistantHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the assistant API."""
    
    server_version = "ERPAssistant/1.0"
    
    def _send_json(
        self,
        payload: Dict[str, Any],
        status: int = HTTPStatus.OK
    ) -> None:
        """Send JSON response.
        
        Args:
            payload: Response dict
            status: HTTP status code
        """
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health":
            self._send_json({"status": "ok", "service": "erp-assistant"})
            return
        
        if self.path == "/":
            self._send_json({
                "service": "ERP AI Assistant",
                "version": "1.0",
                "endpoints": {
                    "POST /assistant/query": "Ask a question",
                    "GET /health": "Health check"
                }
            })
            return
        
        self._send_json(
            {"error": "Not found"},
            status=HTTPStatus.NOT_FOUND
        )
    
    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path != "/assistant/query":
            self._send_json(
                {"error": "Not found"},
                status=HTTPStatus.NOT_FOUND
            )
            return
        
        # Read request body
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        
        try:
            # Try to decode with different encodings
            decoded_body = None
            for encoding in ["utf-8-sig", "utf-8", "utf-16", "cp1252"]:
                try:
                    decoded_body = raw_body.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if decoded_body is None:
                # Last resort: decode with errors='replace'
                decoded_body = raw_body.decode("utf-8", errors="replace")
            
            payload = json.loads(decoded_body)
        except json.JSONDecodeError:
            self._send_json(
                {"error": "Invalid JSON body"},
                status=HTTPStatus.BAD_REQUEST
            )
            return
        
        # Validate question
        question = str(payload.get("question", "")).strip()
        if not question:
            self._send_json(
                {"error": "Question is required"},
                status=HTTPStatus.BAD_REQUEST
            )
            return
        
        # Run assistant
        try:
            result = run_once(question)
            self._send_json(result)
        except Exception as exc:
            self._send_json(
                {
                    "error": "Assistant execution failed",
                    "details": str(exc),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
    
    def do_OPTIONS(self) -> None:
        """Handle CORS OPTIONS requests."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging."""
        return


def serve_http(host: str, port: int) -> None:
    """Start HTTP server.
    
    Args:
        host: Bind address
        port: Bind port
    """
    server = ThreadingHTTPServer((host, port), AssistantHTTPHandler)
    print(f"[INFO] Assistant HTTP server running on http://{host}:{port}")
    print(f"[INFO] POST query to: http://{host}:{port}/assistant/query")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
        server.shutdown()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ERP AI Assistant - LangGraph-based question answering"
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run as HTTP server"
    )
    parser.add_argument(
        "--host",
        default=config.http_host(),
        help="HTTP server host"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.http_port(),
        help="HTTP server port"
    )
    parser.add_argument(
        "--question",
        default="Quels sont mes clients de Paris ?",
        help="Question to ask (CLI mode)"
    )
    
    args = parser.parse_args()
    
    if args.serve:
        serve_http(args.host, args.port)
    else:
        # CLI mode
        print("[INFO] Running in CLI mode...")
        result = run_once(args.question)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
