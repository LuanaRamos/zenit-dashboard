"""Read per-publication totals from a Meta Business Suite content export."""

import csv
import io
from dataclasses import dataclass

from schemas.instagram import InstagramMedia


@dataclass(frozen=True)
class BusinessSuiteMetrics:
    reach: int | None
    follows: int | None


_HEADERS = {
    "account": ("identificação da conta", "account id"),
    "post": ("identificação do post", "post id"),
    "reach": ("alcance", "reach"),
    "follows": ("seguimentos", "follows"),
    "date": ("data", "date"),
}


def _read_count(value: str) -> int | None:
    value = value.strip()
    if value.casefold() in {"", "-", "—", "n/d", "n/a"}:
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 18:
        raise ValueError("O CSV tem uma contagem inválida. Use o arquivo original da Meta.")
    return int(value)


def read_content_export(content: bytes, account_id: str) -> dict[str, BusinessSuiteMetrics]:
    """Identify rows by Instagram account and media IDs; never add daily reach."""
    if not content or len(content) > 10 * 1024 * 1024:
        raise ValueError("Escolha um CSV do Meta Business Suite de até 10 MB.")
    try:
        stream = io.StringIO(content.decode("utf-8-sig"), newline="")
        first_line = stream.readline()
        delimiter = csv.Sniffer().sniff(first_line, delimiters=",;").delimiter
        stream.seek(0)
        reader = csv.DictReader(stream, delimiter=delimiter, strict=True)
        headers = {header.strip().casefold(): header for header in reader.fieldnames or ()}
        columns = {
            key: next((headers[alias] for alias in aliases if alias in headers), None)
            for key, aliases in _HEADERS.items()
        }
        if any(columns[key] is None for key in ("account", "post", "reach", "follows")):
            raise ValueError(
                "Use o CSV de Posts e reels da Meta com ID da conta, ID do post, "
                "Alcance e Seguimentos."
            )

        result = {}
        for row in reader:
            if (row.get(columns["account"]) or "").strip() != account_id:
                continue
            if columns["date"] and (row.get(columns["date"]) or "").strip().casefold() not in {
                "total", "lifetime",
            }:
                raise ValueError("Exporte os totais por publicação, sem o detalhamento por dia.")
            post_id = (row.get(columns["post"]) or "").strip()
            if not post_id.isascii() or not post_id.isdecimal():
                raise ValueError("O CSV contém um ID de publicação inválido.")
            metrics = BusinessSuiteMetrics(
                _read_count(row.get(columns["reach"]) or ""),
                _read_count(row.get(columns["follows"]) or ""),
            )
            if post_id in result and result[post_id] != metrics:
                raise ValueError("O CSV tem totais diferentes para a mesma publicação.")
            result[post_id] = metrics
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("Não consegui ler o CSV. Use o arquivo original da Meta.") from error

    if not result:
        raise ValueError("O CSV não contém publicações da conta do Instagram selecionada.")
    return result


def apply_content_export(
    media: list[InstagramMedia], metrics: dict[str, BusinessSuiteMetrics],
) -> list[InstagramMedia]:
    """Keep imported values separate without mutating media shared in the API cache."""
    return [
        post.model_copy(update={
            "business_suite_reach": metrics[post.id].reach,
            "business_suite_follows": metrics[post.id].follows,
        })
        if post.id in metrics else post
        for post in media
    ]
