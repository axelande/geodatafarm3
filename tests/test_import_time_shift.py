from datetime import datetime, timedelta

import pytest

from ..support_scripts.time_shift import (TimeShiftMatcher,
                                          match_source_indexes,
                                          shift_import_attributes)


def test_positive_delay_moves_later_measurements_to_earlier_positions():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start + timedelta(seconds=index) for index in range(4)]
    rows = [[timestamp.isoformat(), f'lat-{index}', f'lon-{index}', f'yield-{index}']
            for index, timestamp in enumerate(timestamps)]

    shifted, sources = shift_import_attributes(
        rows, timestamps, date_index=0, longitude_index=2, latitude_index=1,
        delay_seconds=1, strategy='nearest', tolerance_seconds=0)

    assert sources == [1, 2, 3, None]
    assert shifted[0][:3] == rows[0][:3]
    assert shifted[0][3] == 'yield-1'
    assert shifted[3][3] == ''


def test_irregular_times_use_nearest_measurement_with_tolerance():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start, start + timedelta(seconds=1.8),
                  start + timedelta(seconds=4.2)]
    rows = [[timestamp.isoformat(), f'lat-{index}', f'lon-{index}', f'yield-{index}']
            for index, timestamp in enumerate(timestamps)]

    shifted, sources = shift_import_attributes(
        rows, timestamps, date_index=0, longitude_index=2, latitude_index=1,
        delay_seconds=2, strategy='nearest', tolerance_seconds=0.5)

    assert sources == [1, 2, None]
    assert shifted[0][3] == 'yield-1'
    assert shifted[1][3] == 'yield-2'
    assert shifted[2][3] == ''


def test_blank_strategy_keeps_rows_but_clears_shifted_values():
    timestamp = datetime(2024, 9, 1, 10, 0, 0)
    rows = [[timestamp.isoformat(), 'lat', 'lon', 'yield']]

    shifted, sources = shift_import_attributes(
        rows, [timestamp], date_index=0, longitude_index=2, latitude_index=1,
        delay_seconds=10, strategy='blank', tolerance_seconds=1)

    assert sources == [None]
    assert shifted == [[rows[0][0], 'lat', 'lon', '']]


def test_rows_with_missing_timestamps_are_retained_as_unmatched():
    timestamp = datetime(2024, 9, 1, 10, 0, 0)
    rows = [[timestamp.isoformat(), 'lat-0', 'lon-0', 'yield-0'],
            ['', 'lat-1', 'lon-1', 'yield-1']]

    shifted, sources = shift_import_attributes(
        rows, [timestamp, None], date_index=0, longitude_index=2,
        latitude_index=1, delay_seconds=0, strategy='nearest',
        tolerance_seconds=1)

    assert len(shifted) == 2
    assert sources == [0, None]
    assert shifted[1] == ['', 'lat-1', 'lon-1', '']


def test_previous_strategy_never_matches_a_later_measurement():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start + timedelta(seconds=index) for index in range(4)]

    sources = match_source_indexes(timestamps, delay_seconds=0.5,
                                   strategy='previous', tolerance_seconds=1)

    assert sources == [0, 1, 2, 3]


def test_next_strategy_never_matches_an_earlier_measurement():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start + timedelta(seconds=index) for index in range(4)]

    sources = match_source_indexes(timestamps, delay_seconds=0.5,
                                   strategy='next', tolerance_seconds=1)

    assert sources == [1, 2, 3, None]


def test_unsorted_rows_are_matched_on_time_not_on_file_order():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start + timedelta(seconds=5), start, start + timedelta(seconds=5)]

    sources = match_source_indexes(timestamps, delay_seconds=5,
                                   strategy='nearest', tolerance_seconds=1)

    assert sources == [None, 0, None]


def test_rows_sharing_one_second_keep_their_place_within_that_second():
    """A 5 Hz logger written out with a seconds-resolution date format."""
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start + timedelta(seconds=index // 5) for index in range(15)]

    assert match_source_indexes(timestamps, 0, 'nearest', 1) == list(range(15))
    assert match_source_indexes(timestamps, 1, 'nearest', 1)[:10] == list(range(5, 15))
    assert match_source_indexes(timestamps, 1, 'next', 1)[:10] == list(range(5, 15))


def test_a_shorter_block_clamps_to_its_last_row():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start, start, start,
                  start + timedelta(seconds=1), start + timedelta(seconds=1)]

    sources = match_source_indexes(timestamps, 1, 'nearest', 1)

    assert sources == [3, 4, 4, 3, 4]


def test_matcher_is_reusable_across_delays():
    start = datetime(2024, 9, 1, 10, 0, 0)
    timestamps = [start + timedelta(seconds=index) for index in range(4)]
    matcher = TimeShiftMatcher(timestamps)

    assert matcher.source_indexes(1, 'nearest', 0) == [1, 2, 3, None]
    assert matcher.source_indexes(-1, 'nearest', 0) == [None, 0, 1, 2]
    assert matcher.source_indexes(2, 'blank', 0) == [None] * 4


def test_unknown_strategy_and_negative_tolerance_are_rejected():
    timestamps = [datetime(2024, 9, 1, 10, 0, 0)]

    with pytest.raises(ValueError):
        match_source_indexes(timestamps, 0, 'sideways', 1)
    with pytest.raises(ValueError):
        match_source_indexes(timestamps, 0, 'nearest', -1)
