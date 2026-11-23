import math

import pytest
from route_engine.domain.models import (
    Delivery,
    Depot,
    Location,
    Problem,
    TimeWindow,
    Vehicle,
)
from route_engine.services.validator import ValidationError, validate_problem


def valid_input() -> dict:
    return {
        "operating_hours": {"start": "08:00", "end": "18:00"},
        "depot": {
            "id": 0,
            "location": {
                "address": "Av. São Sebastião, Parnaíba - PI",
                "latitude": -2.905,
                "longitude": -41.776,
            },
        },
        "vehicles": [{"id": 152, "capacity": 10}, {"id": 153, "capacity": 15}],
        "deliveries": [
            {
                "id": 1,
                "demand": 4,
                "location": {
                    "address": "Rua das Flores, 120, Parnaíba - PI",
                    "latitude": -2.910,
                    "longitude": -41.780,
                },
            }
        ],
    }


def assert_invalid(raw: object, expected_field: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_problem(raw)

    assert exc_info.value.errors[0]["field"] == expected_field


def get_location(raw: dict, section: str) -> dict:
    if section == "depot":
        return raw["depot"]["location"]
    return raw["deliveries"][0]["location"]


def test_validate_problem_builds_typed_domain_objects() -> None:
    problem = validate_problem(valid_input())

    assert isinstance(problem, Problem)
    assert problem.depot == Depot(
        id=0,
        location=Location(
            latitude=-2.905,
            longitude=-41.776,
            address="Av. São Sebastião, Parnaíba - PI",
        ),
    )
    assert problem.vehicles == (
        Vehicle(id=152, capacity=10),
        Vehicle(id=153, capacity=15),
    )
    assert problem.deliveries == (
        Delivery(
            id=1,
            demand=4,
            location=Location(
                latitude=-2.910,
                longitude=-41.780,
                address="Rua das Flores, 120, Parnaíba - PI",
            ),
            time_window=TimeWindow(start_minute=480, end_minute=1080),
        ),
    )
    assert problem.operating_hours == TimeWindow(start_minute=480, end_minute=1080)
    assert problem.total_demand == 4
    assert problem.total_capacity == 25


@pytest.mark.parametrize("raw", [None, [], "problem"])
def test_rejects_non_dictionary_problem(raw: object) -> None:
    assert_invalid(raw, "problem")


@pytest.mark.parametrize(
    ("section", "value", "expected_field"),
    [
        ("depot", None, "depot"),
        ("depot", [], "depot"),
        ("depot", {}, "depot"),
        ("vehicles", None, "vehicles"),
        ("vehicles", {}, "vehicles"),
        ("vehicles", [], "vehicles"),
        ("deliveries", None, "deliveries"),
        ("deliveries", {}, "deliveries"),
        ("deliveries", [], "deliveries"),
    ],
)
def test_rejects_missing_or_invalid_required_sections(
    section: str, value: object, expected_field: str
) -> None:
    raw = valid_input()
    raw[section] = value

    assert_invalid(raw, expected_field)


@pytest.mark.parametrize(
    ("section", "value", "expected_field"),
    [
        ("depot", None, "depot.id"),
        ("depot", True, "depot.id"),
        ("vehicles", None, "vehicles.id"),
        ("vehicles", 1.5, "vehicles.id"),
        ("deliveries", None, "deliveries.id"),
        ("deliveries", "1", "deliveries.id"),
    ],
)
def test_rejects_missing_or_non_integer_ids(
    section: str, value: object, expected_field: str
) -> None:
    raw = valid_input()
    if section == "depot":
        raw["depot"]["id"] = value
    else:
        raw[section][0]["id"] = value

    assert_invalid(raw, expected_field)


@pytest.mark.parametrize("capacity", [None, 0, -1, 1.5, True])
def test_rejects_invalid_vehicle_capacity(capacity: object) -> None:
    raw = valid_input()
    raw["vehicles"][0]["capacity"] = capacity

    assert_invalid(raw, "vehicles.capacity")


@pytest.mark.parametrize("demand", [None, 0, -1, 1.5, True])
def test_rejects_invalid_delivery_demand(demand: object) -> None:
    raw = valid_input()
    raw["deliveries"][0]["demand"] = demand

    assert_invalid(raw, "deliveries.demand")


@pytest.mark.parametrize(
    ("section", "value", "expected_field"),
    [
        ("vehicles", "not a vehicle", "vehicles"),
        ("deliveries", "not a delivery", "deliveries"),
    ],
)
def test_rejects_non_dictionary_entities(
    section: str, value: object, expected_field: str
) -> None:
    raw = valid_input()
    raw[section][0] = value

    assert_invalid(raw, expected_field)


@pytest.mark.parametrize("section", ["depot", "deliveries"])
@pytest.mark.parametrize(
    ("location", "expected_field"),
    [
        (None, "location"),
        ({}, "location"),
        ({"latitude": "south", "longitude": -41}, "location"),
        ({"latitude": 91, "longitude": -41}, "location"),
        ({"latitude": -2, "longitude": 181}, "location"),
        ({"latitude": -2, "longitude": -41, "address": 123}, "location.address"),
    ],
)
def test_validates_depot_and_delivery_locations(
    section: str, location: object, expected_field: str
) -> None:
    raw = valid_input()
    if section == "depot":
        raw["depot"]["location"] = location
    else:
        raw["deliveries"][0]["location"] = location

    assert_invalid(raw, f"{section}.{expected_field}")


@pytest.mark.parametrize("section", ["depot", "deliveries"])
@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(0, 0), (-90, -180), (90, 180)],
)
def test_accepts_zero_and_inclusive_coordinate_bounds(
    section: str, latitude: float, longitude: float
) -> None:
    raw = valid_input()
    location_data = get_location(raw, section)
    location_data["latitude"] = latitude
    location_data["longitude"] = longitude

    problem = validate_problem(raw)
    location = (
        problem.depot.location if section == "depot" else problem.deliveries[0].location
    )

    assert location.latitude == latitude
    assert location.longitude == longitude


@pytest.mark.parametrize("section", ["depot", "deliveries"])
@pytest.mark.parametrize(
    ("coordinate", "value"),
    [
        ("latitude", math.nextafter(-90.0, -math.inf)),
        ("latitude", math.nextafter(90.0, math.inf)),
        ("longitude", math.nextafter(-180.0, -math.inf)),
        ("longitude", math.nextafter(180.0, math.inf)),
    ],
)
def test_rejects_coordinates_immediately_outside_bounds(
    section: str, coordinate: str, value: float
) -> None:
    raw = valid_input()
    get_location(raw, section)[coordinate] = value

    assert_invalid(raw, f"{section}.location")


@pytest.mark.parametrize("section", ["depot", "deliveries"])
@pytest.mark.parametrize(
    ("coordinate", "value"),
    [
        ("latitude", math.nan),
        ("latitude", math.inf),
        ("latitude", -math.inf),
        ("longitude", math.nan),
        ("longitude", math.inf),
        ("longitude", -math.inf),
    ],
)
def test_rejects_non_finite_coordinates(
    section: str, coordinate: str, value: float
) -> None:
    raw = valid_input()
    get_location(raw, section)[coordinate] = value

    assert_invalid(raw, f"{section}.location")


@pytest.mark.parametrize(
    ("section", "path", "expected_field"),
    [
        ("depot", ("id",), "depot.id"),
        ("depot", ("location",), "depot.location"),
        ("depot", ("location", "latitude"), "depot.location"),
        ("depot", ("location", "longitude"), "depot.location"),
        ("vehicles", (0, "id"), "vehicles.id"),
        ("vehicles", (0, "capacity"), "vehicles.capacity"),
        ("deliveries", (0, "id"), "deliveries.id"),
        ("deliveries", (0, "demand"), "deliveries.demand"),
        ("deliveries", (0, "location"), "deliveries.location"),
        ("deliveries", (0, "location", "latitude"), "deliveries.location"),
        ("deliveries", (0, "location", "longitude"), "deliveries.location"),
    ],
)
def test_rejects_removed_required_keys(
    section: str, path: tuple[str | int, ...], expected_field: str
) -> None:
    raw = valid_input()
    target = raw[section]
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]

    assert_invalid(raw, expected_field)


def test_allows_location_without_address() -> None:
    raw = valid_input()
    raw["deliveries"][0]["location"] = {"latitude": -2.91, "longitude": -41.78}

    problem = validate_problem(raw)

    assert problem.deliveries[0].location == Location(
        latitude=-2.91,
        longitude=-41.78,
        address=None,
    )


def test_rejects_total_demand_above_total_capacity() -> None:
    raw = valid_input()
    raw["vehicles"] = [
        {"id": 152, "capacity": 8},
        {"id": 153, "capacity": 6},
    ]
    raw["deliveries"] = [
        {
            "id": 1,
            "demand": 8,
            "location": {"latitude": -2.910, "longitude": -41.780},
        },
        {
            "id": 2,
            "demand": 7,
            "location": {"latitude": -2.920, "longitude": -41.790},
        },
    ]

    assert_invalid(raw, "vehicles")


def test_rejects_delivery_demand_above_largest_vehicle_capacity() -> None:
    raw = valid_input()
    raw["vehicles"] = [
        {"id": 152, "capacity": 8},
        {"id": 153, "capacity": 6},
    ]
    raw["deliveries"][0]["demand"] = 9

    with pytest.raises(ValidationError) as exc_info:
        validate_problem(raw)

    assert exc_info.value.errors == [
        {
            "field": "deliveries.demand",
            "message": "Demanda da entrega excede a capacidade do maior veículo",
        }
    ]


def test_accepts_delivery_demand_equal_to_largest_vehicle_capacity() -> None:
    raw = valid_input()
    raw["vehicles"] = [
        {"id": 152, "capacity": 8},
        {"id": 153, "capacity": 6},
    ]
    raw["deliveries"][0]["demand"] = 8

    problem = validate_problem(raw)

    assert isinstance(problem, Problem)
    assert problem.deliveries[0].demand == 8
    assert problem.max_capacity == 8


def test_accepts_multiple_deliveries_within_individual_and_total_capacity() -> None:
    raw = valid_input()
    raw["vehicles"] = [
        {"id": 152, "capacity": 8},
        {"id": 153, "capacity": 6},
    ]
    raw["deliveries"] = [
        {
            "id": 1,
            "demand": 4,
            "location": {"latitude": -2.910, "longitude": -41.780},
        },
        {
            "id": 2,
            "demand": 5,
            "location": {"latitude": -2.920, "longitude": -41.790},
        },
        {
            "id": 3,
            "demand": 3,
            "location": {"latitude": -2.930, "longitude": -41.800},
        },
    ]

    problem = validate_problem(raw)

    assert isinstance(problem, Problem)
    assert [delivery.demand for delivery in problem.deliveries] == [4, 5, 3]
    assert problem.total_demand == 12
    assert problem.max_capacity == 8
    assert problem.total_capacity == 14


def test_accepts_total_demand_equal_to_total_capacity() -> None:
    raw = valid_input()
    raw["vehicles"] = [
        {"id": 152, "capacity": 10},
        {"id": 153, "capacity": 15},
    ]
    raw["deliveries"] = [
        {
            "id": 1,
            "demand": 10,
            "location": {"latitude": -2.910, "longitude": -41.780},
        },
        {
            "id": 2,
            "demand": 15,
            "location": {"latitude": -2.920, "longitude": -41.790},
        },
    ]

    problem = validate_problem(raw)

    assert problem.total_demand == 25
    assert problem.total_capacity == 25


def test_rejects_legacy_payload_without_operating_hours() -> None:
    raw = valid_input()
    raw.pop("operating_hours")

    assert_invalid(raw, "operating_hours")


@pytest.mark.parametrize(
    ("operating_hours", "expected_field"),
    [
        (None, "operating_hours"),
        ({}, "operating_hours.start"),
        ({"start": "08:00"}, "operating_hours.end"),
        ({"end": "18:00"}, "operating_hours.start"),
        ({"start": None, "end": "18:00"}, "operating_hours.start"),
        ({"start": "08:00", "end": None}, "operating_hours.end"),
    ],
)
def test_rejects_missing_null_or_partial_operating_hours(
    operating_hours: object,
    expected_field: str,
) -> None:
    raw = valid_input()
    raw["operating_hours"] = operating_hours

    assert_invalid(raw, expected_field)


@pytest.mark.parametrize(
    ("boundary", "value"),
    [
        ("start", 8),
        ("start", True),
        ("start", "8:00"),
        ("start", "08:0"),
        ("start", "25:00"),
        ("start", "12:60"),
        ("start", "24:00"),
        ("end", "24:01"),
        ("end", "18:60"),
    ],
)
def test_rejects_invalid_operating_hour_values(
    boundary: str,
    value: object,
) -> None:
    raw = valid_input()
    raw["operating_hours"][boundary] = value

    assert_invalid(raw, f"operating_hours.{boundary}")


@pytest.mark.parametrize("operating_hours", [[], "08:00-18:00", 1])
def test_rejects_non_object_operating_hours(operating_hours: object) -> None:
    raw = valid_input()
    raw["operating_hours"] = operating_hours

    assert_invalid(raw, "operating_hours")


@pytest.mark.parametrize(
    ("start", "end"),
    [("08:00", "08:00"), ("18:00", "08:00"), ("22:00", "02:00")],
)
def test_rejects_invalid_operating_hour_intervals(start: str, end: str) -> None:
    raw = valid_input()
    raw["operating_hours"] = {"start": start, "end": end}

    assert_invalid(raw, "operating_hours")


@pytest.mark.parametrize(
    ("time_window", "expected_field"),
    [
        ({}, "deliveries.time_window.start"),
        ({"start": "09:00"}, "deliveries.time_window.end"),
        ({"end": "12:00"}, "deliveries.time_window.start"),
        ({"start": None, "end": "12:00"}, "deliveries.time_window.start"),
        ({"start": "09:00", "end": None}, "deliveries.time_window.end"),
    ],
)
def test_rejects_partial_delivery_windows(
    time_window: object,
    expected_field: str,
) -> None:
    raw = valid_input()
    raw["deliveries"][0]["time_window"] = time_window

    assert_invalid(raw, expected_field)


@pytest.mark.parametrize("time_window", [[], "09:00-12:00", 9])
def test_rejects_non_object_delivery_windows(time_window: object) -> None:
    raw = valid_input()
    raw["deliveries"][0]["time_window"] = time_window

    assert_invalid(raw, "deliveries.time_window")


@pytest.mark.parametrize(
    ("boundary", "value"),
    [
        ("start", 9),
        ("start", "9:00"),
        ("start", "24:00"),
        ("end", "25:00"),
        ("end", "24:01"),
    ],
)
def test_rejects_invalid_delivery_window_values(boundary: str, value: object) -> None:
    raw = valid_input()
    raw["deliveries"][0]["time_window"] = {
        "start": "09:00",
        "end": "12:00",
    }
    raw["deliveries"][0]["time_window"][boundary] = value

    assert_invalid(raw, f"deliveries.time_window.{boundary}")


@pytest.mark.parametrize(
    ("start", "end"),
    [("09:00", "09:00"), ("12:00", "09:00"), ("22:00", "02:00")],
)
def test_rejects_invalid_delivery_window_intervals(start: str, end: str) -> None:
    raw = valid_input()
    raw["deliveries"][0]["time_window"] = {"start": start, "end": end}

    assert_invalid(raw, "deliveries.time_window")


@pytest.mark.parametrize("window_value", ["missing", None])
def test_delivery_without_window_inherits_operating_hours(window_value: object) -> None:
    raw = valid_input()
    if window_value is None:
        raw["deliveries"][0]["time_window"] = None

    problem = validate_problem(raw)

    assert problem.deliveries[0].time_window == TimeWindow(480, 1080)


@pytest.mark.parametrize(
    ("operating_hours", "requested_window", "expected_window"),
    [
        (("08:00", "18:00"), ("09:00", "12:00"), (540, 720)),
        (("08:00", "18:00"), ("06:00", "20:00"), (480, 1080)),
        (("08:00", "18:00"), ("06:00", "09:00"), (480, 540)),
        (("08:00", "18:00"), ("17:00", "20:00"), (1020, 1080)),
    ],
)
def test_stores_delivery_window_intersection(
    operating_hours: tuple[str, str],
    requested_window: tuple[str, str],
    expected_window: tuple[int, int],
) -> None:
    raw = valid_input()
    raw["operating_hours"] = {
        "start": operating_hours[0],
        "end": operating_hours[1],
    }
    raw["deliveries"][0]["time_window"] = {
        "start": requested_window[0],
        "end": requested_window[1],
    }

    problem = validate_problem(raw)

    assert problem.deliveries[0].time_window == TimeWindow(*expected_window)


def test_rejects_delivery_window_without_intersection() -> None:
    raw = valid_input()
    raw["deliveries"][0]["time_window"] = {
        "start": "06:00",
        "end": "07:00",
    }

    assert_invalid(raw, "deliveries.time_window")


@pytest.mark.parametrize(
    ("start", "expected_minutes"),
    [("17:52", 8), ("17:53", 7)],
)
def test_validates_minimum_effective_delivery_window(
    start: str,
    expected_minutes: int,
) -> None:
    raw = valid_input()
    raw["deliveries"][0]["time_window"] = {
        "start": start,
        "end": "18:00",
    }

    if expected_minutes == 8:
        problem = validate_problem(raw)
        assert problem.deliveries[0].time_window == TimeWindow(1072, 1080)
    else:
        assert_invalid(raw, "deliveries.time_window")


def test_accepts_24_00_as_end_and_converts_it_to_1440() -> None:
    raw = valid_input()
    raw["operating_hours"] = {"start": "23:50", "end": "24:00"}
    raw["deliveries"][0]["time_window"] = {
        "start": "23:52",
        "end": "24:00",
    }

    problem = validate_problem(raw)

    assert problem.operating_hours == TimeWindow(1430, 1440)
    assert problem.deliveries[0].time_window == TimeWindow(1432, 1440)


def test_inherited_operating_hours_must_fit_service_duration() -> None:
    raw = valid_input()
    raw["operating_hours"] = {"start": "08:00", "end": "08:07"}

    assert_invalid(raw, "deliveries.time_window")
