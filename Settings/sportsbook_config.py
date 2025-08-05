from Settings.dfs_providers import DFS_PROVIDERS, DFSProvider


# This module provides configuration for DFS & Sportsbooks
class SportsbookConfig:
    @classmethod
    def get_dfs_provider(cls, name: str) -> DFSProvider:
        try:
            return next(provider for provider in DFS_PROVIDERS if provider.name == name)
        except StopIteration:
            raise ValueError(f"DFS provider '{name}' not found.")

