"""Tests for house_system."""

from __future__ import annotations

from realm.astro.house_system import (
    equal_house_cusps,
    house_for_longitude,
    sign_from_longitude,
)


class TestEqualHouseCusps:
    def test_ascendant_at_zero(self):
        cusps = equal_house_cusps(0.0)
        assert cusps[0] == 0.0
        assert cusps[3] == 90.0    # 4th cusp
        assert cusps[11] == 330.0  # 12th cusp

    def test_ascendant_at_45(self):
        cusps = equal_house_cusps(45.0)
        assert cusps[0] == 45.0
        assert cusps[6] == 225.0   # 7th (opposite to Asc)

    def test_wraps_around_360(self):
        cusps = equal_house_cusps(350.0)
        assert cusps[0] == 350.0
        assert cusps[1] == 20.0   # 2nd cusp wraps
        assert cusps[11] == 320.0


class TestHouseForLongitude:
    def test_ascendant_in_house_1(self):
        cusps = equal_house_cusps(0.0)
        assert house_for_longitude(15.0, cusps) == 1

    def test_opposite_point_in_house_7(self):
        cusps = equal_house_cusps(0.0)
        assert house_for_longitude(180.0, cusps) == 7

    def test_ic_in_house_4(self):
        cusps = equal_house_cusps(0.0)
        assert house_for_longitude(90.0, cusps) == 4

    def test_wraparound_house(self):
        cusps = equal_house_cusps(350.0)
        # 355° should be in house 1 (cusp 1 = 350°, cusp 2 = 20°)
        assert house_for_longitude(355.0, cusps) == 1
        # 10° should also be in house 1 (wraps past 360)
        assert house_for_longitude(10.0, cusps) == 1
        # 20° is exactly at cusp 2 — house 2
        assert house_for_longitude(20.0, cusps) == 2


class TestSignFromLongitude:
    def test_aries_start(self):
        sign, deg = sign_from_longitude(0.0)
        assert sign == "Aries"
        assert deg == 0.0

    def test_taurus_midpoint(self):
        sign, deg = sign_from_longitude(45.0)
        assert sign == "Taurus"
        assert deg == 15.0

    def test_pisces_end(self):
        sign, deg = sign_from_longitude(359.999)
        assert sign == "Pisces"
        assert 29.0 < deg < 30.0

    def test_wraps_at_360(self):
        sign, deg = sign_from_longitude(360.0)
        assert sign == "Aries"
        assert deg == 0.0

    def test_wraps_negative(self):
        sign, deg = sign_from_longitude(-30.0)
        assert sign == "Pisces"
