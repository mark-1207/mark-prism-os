"""棱镜 4 维 12 选题测试"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_generate_dimension_titles_returns_list():
    """generate_dimension_titles 应返回 List[Dict]"""
    from prism_engine import generate_dimension_titles

    with patch("prism_engine._call_llm_raw") as mock_llm:
        # 标题至少 18 字才能通过长度校验
        mock_llm.return_value = (
            '{"candidates": [{"title": "AI时代下自媒体如何帮普通人摆脱失业困境", "rationale": "理由1"}]}'
        )
        result = generate_dimension_titles("测试命题", "reversal")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "title" in result[0]
        assert "dimension" in result[0]


def test_generate_all_titles_produces_12():
    """generate_all_titles 应返回 12 个选题（4 维 × 3）"""
    from prism_engine import generate_all_titles

    with patch("prism_engine._call_llm_raw") as mock_llm:
        mock_llm.side_effect = lambda *a, **kw: (
            '{"candidates": [' +
            ",".join([
                '{"title": "AI时代自媒体帮普通人摆脱失业困境第' + str(j) + '篇完整解析文章", "rationale": "理由"}'
                for j in range(3)
            ]) +
            ']}'
        )
        result = generate_all_titles("AI时代下自媒体是普通人摆脱失业的唯一解药")
        assert len(result) == 12, f"期望 12 选题，实际 {len(result)}"


def test_generate_all_titles_groups_by_dimension():
    """generate_all_titles 应按 4 维分组"""
    from prism_engine import generate_all_titles

    with patch("prism_engine._call_llm_raw") as mock_llm:
        call_count = [0]
        dim_names = ["reversal", "benefit_anchor", "micro_scene", "contrarian"]

        def fake_llm(*args, **kwargs):
            dim_idx = call_count[0]
            call_count[0] += 1
            dim_name = dim_names[dim_idx % 4]
            titles = ",".join([
                '{"title": "AI自媒体帮助普通人摆脱失业困境' + dim_name + '第' + str(j) + '篇全解析", "rationale": "理由", "dimension": "' + dim_name + '"}'
                for j in range(3)
            ])
            return f'{{"candidates": [{titles}]}}'

        mock_llm.side_effect = fake_llm
        result = generate_all_titles("测试命题")

        dims = {}
        for c in result:
            d = c.get("dimension", "?")
            dims.setdefault(d, []).append(c["title"])

        assert len(dims) == 4, f"期望 4 维分组，实际 {len(dims)}: {list(dims.keys())}"
        for dim, titles in dims.items():
            assert len(titles) == 3, f"维度 {dim} 应有 3 选题，实际 {len(titles)}"


def test_dimensions_count_4():
    """PRD 4 维"""
    from prism_engine import DIMENSIONS
    assert len(DIMENSIONS) == 4


def test_dimension_keys():
    """PRD 4 维 key 正确"""
    from prism_engine import DIMENSIONS
    assert set(DIMENSIONS.keys()) == {"reversal", "benefit_anchor", "micro_scene", "contrarian"}


def test_dimension_to_archetype_mapping():
    """DIMENSION_TO_ARCHETYPE 覆盖 4 维"""
    from prism_engine import DIMENSION_TO_ARCHETYPE
    assert "reversal" in DIMENSION_TO_ARCHETYPE
    assert "benefit_anchor" in DIMENSION_TO_ARCHETYPE
    assert "micro_scene" in DIMENSION_TO_ARCHETYPE
    assert "contrarian" in DIMENSION_TO_ARCHETYPE
