import pytest

from core.meta_content_export import apply_content_export, read_content_export
from schemas.instagram import InstagramMedia


HEADER = (
    "Identificação do post,Identificação da conta,Descrição,Data,Alcance,Seguimentos\r\n"
)


def test_import_joins_posts_for_selected_account_and_preserves_raw_api_values():
    report = (
        HEADER
        + '18000000000000001,17912345678901234,"Linha um\nLinha dois, com vírgula",Total,708,6\r\n'
        + "18000000000000001,17912345678901239,Outro cliente,Total,100,12\r\n"
        + "18000000000000002,17912345678901234,Zero real,Total,0,\r\n"
    ).encode("utf-8-sig")
    reel = InstagramMedia(id="18000000000000001", reach=715, media_product_type="REELS")
    feed = InstagramMedia(id="18000000000000002", reach=60, follows=3)
    missing = InstagramMedia(id="18000000000000003", reach=45)

    snapshot = read_content_export(report, "17912345678901234")
    reel_copy, feed_copy, unmatched = apply_content_export([reel, feed, missing], snapshot)

    assert (reel_copy.business_suite_reach, reel_copy.business_suite_follows) == (708, 6)
    assert (reel_copy.reach, reel_copy.follows) == (715, None)
    assert reel.business_suite_reach is None
    assert (feed_copy.business_suite_reach, feed_copy.business_suite_follows) == (0, None)
    assert feed_copy.follows == 3
    assert unmatched is missing


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("1,3,Post,Total,12,0\n", "conta do Instagram selecionada"),
        ("1,2,Post,2026-11-09,12,0\n", "sem o detalhamento por dia"),
        ("1,2,Post,Total,12,0\n1,2,Post,Total,13,0\n", "totais diferentes"),
    ],
)
def test_import_rejects_a_different_account_or_ambiguous_totals(body, error):
    with pytest.raises(ValueError, match=error):
        read_content_export((HEADER + body).encode("utf-8"), "2")
