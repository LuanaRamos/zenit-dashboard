"""
Exceções customizadas para tratamento de erros das APIs da Meta.
Seguindo as diretrizes do Python Expert de não usar 'except Exception' genérico.
"""

class MetaAPIError(Exception):
    """Exceção base para erros genéricos da Meta API."""
    pass

class InstagramAPIError(MetaAPIError):
    """Exceção específica para erros na Graph API do Instagram (Tokens, Permissões, Rate Limits)."""
    pass

class MetaAdsAPIError(MetaAPIError):
    """Exceção específica para erros na API de Anúncios do Meta (Ads Manager)."""
    pass