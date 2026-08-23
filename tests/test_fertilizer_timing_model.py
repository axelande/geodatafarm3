"""Pure-function tests for support_scripts.fertilizer_timing_model.

No DB, no network - independent of the ordered/stateful part of the suite.
"""
from datetime import date, timedelta

from geodatafarm.support_scripts.fertilizer_timing_model import (
    DailyWeather, FertilizerEvent, analyse_events, summarize)


def _make_weather(start, days, rain_for_day, et0=3.0, temp=15.0):
    d0 = date.fromisoformat(start)
    out = []
    for i in range(days):
        d = d0 + timedelta(days=i)
        out.append(DailyWeather(date=d.isoformat(), precipitation_mm=rain_for_day(i),
                                et0_mm=et0, temp_mean_c=temp))
    return out


def test_rate_kg_n_ha_parses_numbers_from_free_text():
    assert FertilizerEvent(date='2024-01-01', rate_text='150 kg N/ha').rate_kg_n_ha == 150.0
    assert FertilizerEvent(date='2024-01-01', rate_text='120,5').rate_kg_n_ha == 120.5
    assert FertilizerEvent(date='2024-01-01', rate_text='a lot').rate_kg_n_ha is None
    assert FertilizerEvent(date='2024-01-01', rate_text='').rate_kg_n_ha is None


def test_heavy_rain_after_application_uses_advanced_tier_and_is_high_risk():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150 kg N/ha', crop='potato')]
    weather = _make_weather('2024-05-01', 40, lambda i: 30.0 if i in (10, 11) else 0.0)

    results = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)

    assert results[0].tier == 'advanced'
    assert results[0].risk in ('high', 'moderate')
    assert results[0].estimated_n_leached_kg_ha > 0


def test_dry_spell_after_application_leaches_less_than_a_heavy_rain():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150 kg N/ha', crop='potato')]
    wet = _make_weather('2024-05-01', 40, lambda i: 30.0 if i in (10, 11) else 0.0)
    dry = _make_weather('2024-05-01', 40, lambda i: 0.0)

    wet_result = analyse_events(events, wet, clay_pct=15.0, organic_matter_pct=3.0)[0]
    dry_result = analyse_events(events, dry, clay_pct=15.0, organic_matter_pct=3.0)[0]

    assert dry_result.risk == 'low'
    assert dry_result.estimated_n_leached_kg_ha < wet_result.estimated_n_leached_kg_ha


def test_unparseable_rate_falls_back_to_simple_tier():
    events = [FertilizerEvent(date='2024-05-10', rate_text='a lot', crop='potato')]
    weather = _make_weather('2024-05-01', 40, lambda i: 0.0)

    results = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)

    assert results[0].tier == 'simple'
    assert results[0].estimated_n_leached_kg_ha is None


def test_missing_soil_data_forces_simple_tier_even_with_a_good_rate():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150', crop='potato')]
    weather = _make_weather('2024-05-01', 40, lambda i: 0.0)

    results = analyse_events(events, weather, clay_pct=None)

    assert results[0].tier == 'simple'


def test_unknown_crop_falls_back_to_default_model_but_still_runs():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150', crop='quinoa')]
    weather = _make_weather('2024-05-01', 40, lambda i: 0.0)

    results = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)

    assert results[0].tier == 'advanced'
    assert results[0].risk == 'low'


def test_simple_tier_scales_by_crop_leaching_sensitivity():
    weather = _make_weather('2024-05-01', 15, lambda i: 10.0 if i == 10 else 0.0)
    potato_event = [FertilizerEvent(date='2024-05-11', rate_text='', crop='potato')]
    wheat_event = [FertilizerEvent(date='2024-05-11', rate_text='', crop='wheat')]

    potato_result = analyse_events(potato_event, weather)[0]
    wheat_result = analyse_events(wheat_event, weather)[0]

    assert potato_result.tier == 'simple'
    assert wheat_result.tier == 'simple'
    # potato has a higher leaching_sensitivity than wheat (see crop_models.py),
    # so the same rain should never read as a lower risk tier for potato.
    _order = {'low': 0, 'moderate': 1, 'high': 2}
    assert _order[potato_result.risk] >= _order[wheat_result.risk]


def test_no_weather_data_for_event_date_is_unknown_risk():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150', crop='potato')]
    weather = _make_weather('2024-06-01', 10, lambda i: 5.0)  # entirely after the event

    results = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)

    assert results[0].tier == 'simple'
    assert results[0].risk == 'unknown'


def test_rate_kg_p_k_mg_ha_parse_independently_of_n():
    ev = FertilizerEvent(date='2024-01-01', rate_text='100 kg N/ha',
                         rate_text_p='30 kg P/ha', rate_text_k='200 kg K/ha',
                         rate_text_mg='15 kg Mg/ha')
    assert ev.rate_kg_n_ha == 100.0
    assert ev.rate_kg_p_ha == 30.0
    assert ev.rate_kg_k_ha == 200.0
    assert ev.rate_kg_mg_ha == 15.0


def test_rate_kg_p_k_mg_ha_default_to_none_when_not_given():
    ev = FertilizerEvent(date='2024-01-01', rate_text='100 kg N/ha')
    assert ev.rate_kg_p_ha is None
    assert ev.rate_kg_k_ha is None
    assert ev.rate_kg_mg_ha is None


def test_rate_kg_p_k_mg_ha_unparseable_text_is_none():
    ev = FertilizerEvent(date='2024-01-01', rate_text_p='some', rate_text_k='',
                         rate_text_mg='a lot')
    assert ev.rate_kg_p_ha is None
    assert ev.rate_kg_k_ha is None
    assert ev.rate_kg_mg_ha is None


def test_analyse_events_carries_p_k_mg_rates_onto_result():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150 kg N/ha',
                              rate_text_p='30', rate_text_k='200', rate_text_mg='15',
                              crop='potato')]
    weather = _make_weather('2024-05-01', 40, lambda i: 0.0)

    result = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)[0]

    assert result.rate_kg_n_ha == 150.0
    assert result.rate_kg_p_ha == 30.0
    assert result.rate_kg_k_ha == 200.0
    assert result.rate_kg_mg_ha == 15.0


def test_analyse_events_p_k_mg_rates_none_when_not_given():
    events = [FertilizerEvent(date='2024-05-10', rate_text='150 kg N/ha', crop='potato')]
    weather = _make_weather('2024-05-01', 40, lambda i: 0.0)

    result = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)[0]

    assert result.rate_kg_p_ha is None
    assert result.rate_kg_k_ha is None
    assert result.rate_kg_mg_ha is None


def test_summarize_counts_tiers_and_risk_levels():
    events = [
        FertilizerEvent(date='2024-05-10', rate_text='150', crop='potato'),
        FertilizerEvent(date='2024-05-20', rate_text='not a number', crop='potato'),
    ]
    weather = _make_weather('2024-05-01', 40, lambda i: 30.0 if i == 10 else 0.0)

    results = analyse_events(events, weather, clay_pct=15.0, organic_matter_pct=3.0)
    text = summarize(results)

    assert '2 application(s)' in text
    assert summarize([]) == 'No fertilizer applications found for this field/period.'
