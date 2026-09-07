"""Secret storage with filesystem permission isolation."""

from .manager import SecretsError, SecretStore, get_secret_store

__all__ = ["SecretStore", "SecretsError", "get_secret_store"]
