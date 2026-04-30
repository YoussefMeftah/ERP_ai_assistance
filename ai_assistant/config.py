"""
Configuration management for the ERP AI Assistant.

Centralizes environment variables, defaults, and configuration logic.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

# For Colab environment - load secrets via google.colab.userdata
try:
    from google.colab import userdata
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

# Load environment variables from .env file (local development only)
if not IN_COLAB:
    try:
        from dotenv import load_dotenv
        
        # Load .env from project root
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        # python-dotenv not installed, continue with os.getenv
        pass


class Config:
    """Central configuration for the ERP Assistant system."""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    AI_ASSISTANT_ROOT = Path(__file__).resolve().parent
    DATA_DIR = AI_ASSISTANT_ROOT / "data"
    CACHE_DIR = DATA_DIR / "cache"
    
    def __init__(self):
        """Initialize directories."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # ========== OLLAMA Configuration ==========
    @staticmethod
    def ollama_url() -> str:
        """Ollama API URL."""
        return os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    
    @staticmethod
    def ollama_timeout_seconds() -> int:
        """General Ollama timeout."""
        return int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
    
    @staticmethod
    def ollama_router_timeout_seconds() -> int:
        """Timeout for endpoint routing LLM."""
        return int(
            os.getenv(
                "OLLAMA_ROUTER_TIMEOUT_SECONDS",
                os.getenv("OLLAMA_TIMEOUT_SECONDS", "300")
            )
        )
    
    @staticmethod
    def ollama_model_router() -> str:
        """LLM model for endpoint routing (DeepSeek)."""
        return os.getenv("OLLAMA_MODEL_ROUTER", "deepseek-coder:6.7b")
    
    @staticmethod
    def ollama_model_answer() -> str:
        """LLM model for answer generation (Llama)."""
        return os.getenv("OLLAMA_MODEL_ANSWER", "llama3.2:latest")
    
    @staticmethod
    def use_ollama() -> bool:
        """Whether to enable Ollama integration."""
        return os.getenv("USE_OLLAMA", "1").strip().lower() in {"1", "true", "yes"}
    
    # ========== ERP API Configuration ==========
    @staticmethod
    def erp_api_base_urls() -> List[str]:
        """Get ERP API base URLs for calling WebApi."""
        explicit = os.getenv("ERP_API_BASE_URL", "https://localhost:44393").strip().rstrip("/")
        if explicit:
            return [explicit]
        
        # Auto-discovery from WebApi project
        webapi_project_dir = os.getenv("ERP_WEBAPI_PROJECT_DIR", "").strip()
        if not webapi_project_dir:
            return []
        
        launch_settings = Path(webapi_project_dir) / "Properties" / "launchSettings.json"
        if not launch_settings.exists():
            return []
        
        try:
            payload = json.loads(launch_settings.read_text(encoding="utf-8-sig"))
            profiles = payload.get("profiles", {})
            
            candidate_profiles: List[Dict[str, Any]] = []
            if isinstance(profiles, dict):
                if isinstance(profiles.get("WebApi"), dict):
                    candidate_profiles.append(profiles["WebApi"])
                candidate_profiles.extend(
                    p for p in profiles.values()
                    if isinstance(p, dict) and p not in candidate_profiles
                )
            
            urls: List[str] = []
            for profile in candidate_profiles:
                app_urls = profile.get("applicationUrl", "")
                if app_urls:
                    for raw_url in str(app_urls).split(";"):
                        cleaned = raw_url.strip().rstrip("/")
                        if cleaned and cleaned not in urls:
                            urls.append(cleaned)
            return urls
        except (json.JSONDecodeError, OSError):
            return []
    
    @staticmethod
    def erp_api_bearer_token() -> Optional[str]:
        """JWT bearer token for ERP API authentication."""
        token = os.getenv("ERP_API_BEARER_TOKEN", "").strip()
        return token if token else None
    
    # ========== Endpoint Configuration ==========
    @staticmethod
    def endpoint_source() -> str:
        """Source of endpoints: 'swagger' or 'file'."""
        return os.getenv("ERP_ENDPOINT_SOURCE", "swagger").strip().lower()
    
    @staticmethod
    def endpoints_json_path() -> Optional[Path]:
        """Path to endpoints.json configuration file."""
        configured = os.getenv("ERP_ENDPOINTS_JSON", "").strip()
        if configured:
            return Path(configured)
        
        default = Config.AI_ASSISTANT_ROOT / "data" / "endpoints.sample.json"
        if default.exists():
            return default
        return None
    
    @staticmethod
    def endpoint_overrides_path() -> Optional[Path]:
        """Path to endpoint_overrides.json for ID->URL mapping."""
        configured = os.getenv("ERP_ENDPOINT_OVERRIDES_JSON", "").strip()
        if configured:
            return Path(configured)
        
        default = Config.AI_ASSISTANT_ROOT / "data" / "endpoint_overrides.json"
        if default.exists():
            return default
        return None
    
    @staticmethod
    def swagger_json_path() -> Optional[Path]:
        """Path to swagger_live.json fallback file."""
        configured = os.getenv("ERP_SWAGGER_JSON", "").strip()
        if configured:
            return Path(configured)
        
        default = Config.AI_ASSISTANT_ROOT / "swagger_live.json"
        if default.exists():
            return default
        return None
    
    @staticmethod
    def load_swagger_endpoints() -> bool:
        """Whether to enrich endpoints from live Swagger."""
        return os.getenv("ERP_LOAD_SWAGGER_ENDPOINTS", "1").strip() in {"1", "true"}
    
    @staticmethod
    def router_candidate_limit() -> int:
        """Max number of endpoint candidates to pass to router LLM."""
        return int(os.getenv("ERP_ROUTER_CANDIDATE_LIMIT", "12"))
    
    # ========== MongoDB Configuration (for staging large results) ==========
    @staticmethod
    def mongodb_uri() -> Optional[str]:
        """MongoDB connection URI for staging results."""
        return os.getenv("MONGODB_URI", "").strip() or None
    
    @staticmethod
    def mongodb_db_name() -> str:
        """MongoDB database name for staging."""
        return os.getenv("MONGODB_DB_NAME", "erp_assistant_staging")
    
    @staticmethod
    def mongodb_staging_threshold() -> int:
        """Threshold: if API result > N records, save to MongoDB."""
        return int(os.getenv("MONGODB_STAGING_THRESHOLD", "50"))
    
    # ========== LangSmith Configuration ==========
    @staticmethod
    def langsmith_api_key() -> Optional[str]:
        """LangSmith API key for evaluation and tracing.
        
        In Colab: Gets from Google Colab Secrets (set via Secrets panel)
        Locally: Gets from .env file
        """
        if IN_COLAB:
            try:
                return userdata.get('LANGSMITH_API_KEY')
            except Exception:
                return None
        else:
            # Local development: use .env file
            api_key = os.getenv("LANGSMITH_API_KEY", "").strip()
            return api_key if api_key else None
    
    @staticmethod
    def langsmith_project_name() -> str:
        """LangSmith project name for evaluations."""
        return os.getenv("LANGSMITH_PROJECT_NAME", "endpoint_selection_evaluation_v2")
    
    @staticmethod
    def langsmith_dataset_name() -> str:
        """LangSmith dataset name for evaluations."""
        return os.getenv("LANGSMITH_DATASET_NAME", "endpoint_selection_test_cases")
    
    @staticmethod
    def langsmith_endpoint() -> str:
        """LangSmith API endpoint URL."""
        return os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    
    # ========== HTTP Server Configuration ==========
    @staticmethod
    def http_host() -> str:
        """HTTP server host."""
        return os.getenv("ERP_ASSISTANT_HOST", "127.0.0.1")
    
    @staticmethod
    def http_port() -> int:
        """HTTP server port."""
        return int(os.getenv("ERP_ASSISTANT_PORT", "8000"))
    
    # ========== Logging & Debug ==========
    @staticmethod
    def debug_mode() -> bool:
        """Enable debug logging."""
        return os.getenv("DEBUG", "0").strip() in {"1", "true", "yes"}
    
    @staticmethod
    def log_level() -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR)."""
        return os.getenv("LOG_LEVEL", "INFO").upper()


# Global config instance
config = Config()
