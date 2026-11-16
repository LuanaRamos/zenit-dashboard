"""Ícones vetoriais no estilo Lucide para os componentes HTML do Streamlit.

Sem emojis, imagens externas ou scripts. Tamanhos e traços uniformes.
"""
from __future__ import annotations

from html import escape


# Geometrias Lucide com stroke='currentColor' (24x24).
_PATHS = {
    "wallet": '<path d="M20 7V5a2 2 0 0 0-2-2H5a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h15a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2H5a3 3 0 0 1 0-6"/><path d="M22 12h-6a2 2 0 0 0 0 4h6"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "message": '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 16 4-4 4 3 5-8"/>',
    "bar-chart": '<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="5" rx=".5"/><rect x="12" y="8" width="3" height="9" rx=".5"/><rect x="17" y="5" width="3" height="12" rx=".5"/>',
    "eye": '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "pointer": '<path d="m5 3 14 9-7 1-3 7z"/><path d="m12 13 4 7"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/>',
    "sparkles": '<path d="m12 3 1.9 6.1L20 11l-6.1 1.9L12 19l-1.9-6.1L4 11l6.1-1.9L12 3Z"/><path d="m19 17 .5 1.5L21 19l-1.5.5L19 21l-.5-1.5L17 19l1.5-.5L19 17Z"/>',
    "arrow-up-right": '<path d="M7 17 17 7M7 7h10v10"/>',
    "instagram": '<rect width="20" height="20" x="2" y="2" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "alert": '<path d="m10.29 3.86-8.82 15.42A2 2 0 0 0 3.2 22h17.6a2 2 0 0 0 1.73-2.72L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4M12 17h.01"/>',
}
_LABEL_ICONS = {
    "investimento": "wallet", "gasto": "wallet",
    "lead": "users", "seguidores": "users", "contas engajadas": "users",
    "conversa": "message", "mensagen": "message",
    "custo": "target", "cpl": "target", "cpa": "target",
    "visualiza": "eye", "alcance": "eye", "impress": "eye",
    "clique": "pointer", "toque": "pointer",
    "campanha": "chart", "crescimento": "chart",
    "intera": "activity", "curtida": "activity",
    "salvamento": "file", "compartilha": "link",
}


def icon_for_label(label: str) -> str:
    lower = str(label).casefold()
    for token, name in _LABEL_ICONS.items():
        if token in lower:
            return name
    return "chart"


def lucide_icon(name: str, size: int = 18) -> str:
    """SVG decorativo inline, com dados fixos e sem depender de CDN."""
    name = str(name)
    path = _PATHS.get(name, _PATHS["chart"])
    icon_size = max(12, min(int(size), 48))
    return (
        f'<svg data-lucide="{escape(name, quote=True)}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'width="{icon_size}" height="{icon_size}" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        'aria-hidden="true" focusable="false">'
        f'{path}</svg>'
    )
