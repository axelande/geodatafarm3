import pytest

from ..database_scripts.fertility_index import (
    classify_index,
    combine_sources,
    default_class_boundaries,
    percentile_ranks,
)


def test_percentile_ranks_preserve_order_and_handle_ties():
    assert percentile_ranks([10, 20, 30]) == [0.0, 50.0, 100.0]
    assert percentile_ranks([1, 1, 3]) == [25.0, 25.0, 100.0]


def test_combine_sources_renormalizes_missing_values():
    result = combine_sources({'yield': [10, 20], 'soil': [1, None]})
    assert result[0] == pytest.approx(0.0)
    assert result[1] == pytest.approx(100.0)


def test_default_five_classes_and_custom_boundaries():
    assert default_class_boundaries() == [20.0, 40.0, 60.0, 80.0]
    assert classify_index([0, 20, 55, 100]) == [1, 2, 3, 5]
    assert classify_index([10, 30, 90], [25, 75]) == [1, 2, 3]


def test_class_boundaries_must_be_ordered():
    with pytest.raises(ValueError):
        classify_index([10], [60, 40])