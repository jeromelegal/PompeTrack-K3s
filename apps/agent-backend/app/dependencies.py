from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.agentic import AgenticService
from app.services.ollama import OllamaService
from app.services.rag import RAGService
from app.services.scraper import ScraperService
from app.services.state_store import StateStore
from app.services.websearch import WebSearchService
from app.services.workspace import WorkspaceService


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ensure_directories()
        self.ollama = OllamaService(settings)
        self.websearch = WebSearchService(settings)
        self.scraper = ScraperService(settings)
        self.workspace = WorkspaceService(settings)
        self.rag = RAGService(settings)
        self.state_store = StateStore(settings)
        self.agentic = AgenticService(
            settings=settings,
            ollama=self.ollama,
            websearch=self.websearch,
            scraper=self.scraper,
            workspace=self.workspace,
            rag=self.rag,
            state_store=self.state_store,
        )

    def ensure_directories(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_services() -> ServiceContainer:
    return ServiceContainer(get_settings())
