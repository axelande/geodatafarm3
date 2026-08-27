"""The column-name matching that picks a file's coordinate columns.

This used to be a substring test - ``part.lower() in "latitude lat y"`` - which
is true for every substring of that string, the empty string included. A column
name with a leading space splits into an empty first part, so files like
tests/test_data/planting_file.csv handed both coordinate columns to whichever
oddly spaced column came last. Every row then failed check_row_failed()'s
float() on it and the import stored an empty table while reporting success.
"""
from ..import_data.handle_text_data import LATITUDE_NAMES, LONGITUDE_NAMES


def parts(heading: str) -> list[str]:
    """How prepare_last_choices() breaks a column name up."""
    return heading.lower().split(' ')


def test_the_usual_coordinate_headings_are_recognised():
    for heading in ('latitude (wgs84)', 'Latitude', 'LAT', 'Y'):
        assert any(part in LATITUDE_NAMES for part in parts(heading)), heading
    for heading in ('longitude (wgs84)', 'Longitude', 'LON', 'X'):
        assert any(part in LONGITUDE_NAMES for part in parts(heading)), heading


def test_a_leading_space_does_not_make_a_column_a_coordinate():
    """The empty part these split into used to match both names at once."""
    for heading in (' Ferti-Flow application', ' Cut potatoes',
                    ' Potato square measurement', ' Granules application'):
        assert not any(part in LATITUDE_NAMES for part in parts(heading)), heading
        assert not any(part in LONGITUDE_NAMES for part in parts(heading)), heading


def test_an_unrelated_column_is_not_mistaken_for_a_coordinate():
    for heading in ('Vattenhalt', 'set granules %', 'Potato variety', 'comment',
                    'altitude (m)', 'speed (km/h)', 'a', 'l', 'at'):
        assert not any(part in LATITUDE_NAMES for part in parts(heading)), heading
        assert not any(part in LONGITUDE_NAMES for part in parts(heading)), heading


def test_latitude_and_longitude_never_claim_the_same_name():
    assert not set(LATITUDE_NAMES) & set(LONGITUDE_NAMES)
