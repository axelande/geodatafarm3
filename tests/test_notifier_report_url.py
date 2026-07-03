"""Tests for the pre-filled GitHub issue URL built for the 'Let us know' button.

These are pure-function tests: they do not touch the shared database fixture, so
they are independent of the ordered/stateful part of the suite.
"""
from urllib.parse import unquote

from geodatafarm.support_scripts.notifier.notifier import (
    _MAX_ISSUE_URL_LEN,
    _prefilled_github_issue_url,
    _report_body,
)
from geodatafarm.support_scripts.notifier.exceptions import GeoDataFarmError

_TRACKER = 'https://github.com/axelande/geodatafarm3/issues'


def test_prefilled_issue_url_contains_error_and_environment():
    err = GeoDataFarmError(user_message='Saving <b>failed</b>',
                           detail='Traceback ... boom at line 42')
    url = _prefilled_github_issue_url(_TRACKER, err)

    assert url.startswith(f'{_TRACKER}/new?')
    assert 'title=' in url and 'body=' in url

    decoded = unquote(url)
    # Inline HTML is stripped from both the title and the echoed error line.
    assert '<b>' not in decoded
    assert 'Saving failed' in decoded
    # The technical detail, the error id and the environment are all included.
    assert 'boom at line 42' in decoded
    assert err.error_id in decoded
    assert 'GeoDataFarm' in decoded
    assert 'QGIS' in decoded


def test_prefilled_issue_url_is_truncated_when_detail_is_huge():
    huge = 'x' * 40000 + 'REAL_ERROR_TAIL'
    err = GeoDataFarmError(user_message='Boom', detail=huge)

    url = _prefilled_github_issue_url(_TRACKER, err)

    assert len(url) <= _MAX_ISSUE_URL_LEN
    decoded = unquote(url)
    assert 'truncated' in decoded
    # The tail of the trace (where the real error line usually sits) survives.
    assert 'REAL_ERROR_TAIL' in decoded


def test_report_body_falls_back_to_cause_traceback():
    try:
        raise ValueError('kaboom')
    except ValueError as exc:
        err = GeoDataFarmError(user_message='Something failed')
        err.__cause__ = exc

    body = _report_body(err)

    assert 'ValueError' in body
    assert 'kaboom' in body
