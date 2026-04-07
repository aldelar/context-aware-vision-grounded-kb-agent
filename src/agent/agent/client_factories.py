"""Environment-aware SDK factories for the agent service."""

from __future__ import annotations

from typing import Protocol

from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
from azure.ai.inference import EmbeddingsClient
from azure.core.credentials import AzureKeyCredential
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient
from openai import OpenAI

from agent.config import Config, get_config

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class EmbeddingBackend(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class _AzureEmbeddingBackend:
    def __init__(self, cfg: Config) -> None:
        endpoint = f"{cfg.ai_services_endpoint.rstrip('/')}/openai/deployments/{cfg.embedding_deployment_name}"
        self._client = EmbeddingsClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
            credential_scopes=[_COGNITIVE_SCOPE],
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embed(input=texts)
        return [item.embedding for item in response.data]


class _OllamaEmbeddingBackend:
    def __init__(self, cfg: Config) -> None:
        self._client = OpenAI(base_url=cfg.ollama_endpoint, api_key=cfg.ollama_api_key)
        self._model = cfg.embedding_deployment_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]


def create_blob_service_client(account_url: str | None = None) -> BlobServiceClient:
    cfg = get_config()
    if cfg.is_dev and cfg.azurite_connection_string:
        return BlobServiceClient.from_connection_string(cfg.azurite_connection_string)
    return BlobServiceClient(
        account_url=(account_url or cfg.serving_blob_endpoint).rstrip("/"),
        credential=DefaultAzureCredential(),
    )


def create_async_cosmos_client(endpoint: str | None = None) -> AsyncCosmosClient:
    cfg = get_config()
    if cfg.is_dev:
        return AsyncCosmosClient(
            url=endpoint or cfg.cosmos_endpoint,
            credential=cfg.cosmos_key,
            connection_verify=cfg.cosmos_verify_cert,
            enable_endpoint_discovery=False,
        )
    return AsyncCosmosClient(
        url=endpoint or cfg.cosmos_endpoint,
        credential=DefaultAzureCredential(),
    )


def create_search_client() -> SearchClient:
    cfg = get_config()
    if cfg.is_dev:
        return SearchClient(
            endpoint=cfg.search_endpoint,
            index_name=cfg.search_index_name,
            credential=AzureKeyCredential(cfg.search_api_key),
            connection_verify=cfg.search_verify_cert,
        )
    return SearchClient(
        endpoint=cfg.search_endpoint,
        index_name=cfg.search_index_name,
        credential=DefaultAzureCredential(),
    )


def create_query_embedding_backend() -> EmbeddingBackend:
    cfg = get_config()
    if cfg.is_dev:
        return _OllamaEmbeddingBackend(cfg)
    return _AzureEmbeddingBackend(cfg)


def create_chat_client() -> OpenAIChatClient | OpenAIChatCompletionClient:
    cfg = get_config()
    if cfg.is_dev:
        return OpenAIChatClient(
            model=cfg.agent_model_deployment_name,
            api_key=cfg.ollama_api_key,
            base_url=cfg.ollama_endpoint,
        )

    return OpenAIChatCompletionClient(
        credential=DefaultAzureCredential(),
        azure_endpoint=cfg.ai_services_endpoint,
        model=cfg.agent_model_deployment_name,
        api_version="2025-03-01-preview",
    )