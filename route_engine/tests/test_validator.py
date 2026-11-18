import math

import pytest

from route_engine.domain.models import Delivery, Depot, Location, Problem, Vehicle
from route_engine.services.validator import ValidationError, validate_problem


def valid_input() -> dict:
    return {
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
        ),
    )
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
