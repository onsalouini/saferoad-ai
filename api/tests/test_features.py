from ml.features import MODEL_WEATHER, ROAD_FEATURES, STATES, build_row, normalize_weather, season_of


def test_build_row_has_all_columns():
    row = build_row({"Start_Lat": 34.05, "Start_Lng": -118.24, "State": "CA", "Weather_Condition": "Rain", "Hour": 8})
    assert row["State_CA"] == 1 and sum(row[f"State_{s}"] for s in STATES[1:]) == 1
    assert row["Weather_Condition_Rain"] == 1 and sum(row[f"Weather_Condition_{w}"] for w in MODEL_WEATHER) == 1
    assert all(f in row for f in ROAD_FEATURES)
    assert row["IsRushHour"] == 1


def test_reference_categories_are_all_zero():
    row = build_row({"State": "AL", "Weather_Condition": "Clear", "Month": 10})
    assert sum(row[f"State_{s}"] for s in STATES[1:]) == 0
    assert sum(row[f"Weather_Condition_{w}"] for w in MODEL_WEATHER) == 0
    assert row["Season_Spring"] == row["Season_Summer"] == row["Season_Winter"] == 0  # automne = référence


def test_night_inferred_from_hour():
    assert build_row({"Hour": 23})["Sunrise_Sunset"] == 1
    assert build_row({"Hour": 13})["Sunrise_Sunset"] == 0
    assert build_row({"Hour": 23, "IsNight": False})["Sunrise_Sunset"] == 0


def test_weekend_and_seasons():
    assert build_row({"DayOfWeek": 6})["IsWeekend"] == 1
    assert season_of(1) == "Winter" and season_of(7) == "Summer"


def test_normalize_weather():
    assert normalize_weather("Thunderstorm") == "Other"
    assert normalize_weather("Light Rain Showers") == "Light Rain"
    assert normalize_weather("Mist") == "Fog"
    assert normalize_weather(None) == "Clear"
    assert normalize_weather("Partly Cloudy") == "Partly Cloudy"


def test_model_prediction_is_probability(model_ready):
    p = model_ready.probabilities([{"Start_Lat": 39.96, "Start_Lng": -83.0, "State": "OH", "Hour": 17}])[0]
    assert 0 <= p <= 1
    lvl = model_ready.level(p)
    assert lvl["status"] in ("good", "warning", "serious", "critical")
