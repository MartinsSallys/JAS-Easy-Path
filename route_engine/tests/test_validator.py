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
    raw["deliveries"][0]["demand"] = 26

    assert_invalid(raw, "vehicles")
