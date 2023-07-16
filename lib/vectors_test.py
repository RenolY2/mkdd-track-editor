import sys

import pytest

from vectors import Vector3


def test_vector3_initializer():
    vector = Vector3(1, 2, 3)
    assert vector.x == 1
    assert vector.y == 2
    assert vector.z == 3


def test_vector3_comparison():
    vector = Vector3(1, 2, 3)

    assert vector == Vector3(1, 2, 3)
    assert vector == Vector3(1.0, 2.0, 3.0)

    assert vector != Vector3(4, 5, 6)
    assert vector != 42
    assert vector != 'foobar'

    assert hash(vector) == hash(Vector3(1, 2, 3))
    assert hash(vector) != hash(Vector3(4, 5, 6))

    assert str(vector) == '(1.0, 2.0, 3.0)'
    assert repr(vector) == '(1.0, 2.0, 3.0)'

    assert vector in [vector]
    assert vector in (vector, )
    assert vector in set((vector,))
    assert vector in {vector: True}

    assert vector in [Vector3(1, 2, 3)]
    assert vector in (Vector3(1, 2, 3), )
    assert vector in set((Vector3(1, 2, 3),))
    assert vector in {Vector3(1, 2, 3): True}


def test_vector3_set_components():
    vector = Vector3(0, 0, 0)
    vector.x = 1
    vector.y = 2
    vector.z = 3
    assert vector.x == 1
    assert vector.y == 2
    assert vector.z == 3


def test_vector3_copy():
    vector = Vector3(1, 2, 3)
    copy = vector.copy()
    assert copy is not vector
    assert copy == vector
    assert copy.x == 1
    assert copy.y == 2
    assert copy.z == 3


def test_vector3_arithmetic():
    vector = Vector3(1, 2, 3)

    assert vector * 2 == Vector3(2, 4, 6)
    assert vector / 2 == Vector3(0.5, 1.0, 1.5)
    assert vector + Vector3(7, 8, 9) == Vector3(8, 10, 12)
    assert vector - Vector3(7, 8, 9) == Vector3(-6, -6, -6)

    vector *= 2
    assert vector == Vector3(2, 4, 6)
    vector /= 4
    assert vector == Vector3(0.5, 1.0, 1.5)
    vector += Vector3(2, 3, 4)
    assert vector == Vector3(2.5, 4.0, 5.5)
    vector -= Vector3(2, 3, 4)
    assert vector == Vector3(0.5, 1.0, 1.5)


def test_vector3_linear_algebra():
    assert Vector3(1, 2, 3).norm() == pytest.approx(3.741657, 0.000001)

    vector = Vector3(1, 2, 3)
    vector.normalize()
    assert vector.x == pytest.approx(0.267261, 0.000001)
    assert vector.y == pytest.approx(0.534522, 0.000001)
    assert vector.z == pytest.approx(0.801783, 0.000001)

    assert Vector3(1, 2, 3).normalized() == vector

    vector = Vector3(1, 2, 3).cross(Vector3(4, -5, 6))
    assert vector.x == 27.0
    assert vector.y == 6.0
    assert vector.z == -13.0

    assert Vector3(1, 2, 3).dot(Vector3(4, 5, 6)) == 32.0

    assert Vector3(1, 2, 3).cos_angle(Vector3(4, 5, 6)) == pytest.approx(0.974632, 0.000001)

    assert Vector3(0, 0, 0).is_zero()
    assert not Vector3(1, 2, 3).is_zero()

    assert Vector3(1, 2, 3).distance(Vector3(4, 5, 6)) == pytest.approx(5.196152, 0.000001)
    assert Vector3(1, 2, 3).distance2(Vector3(4, 5, 6)) == 27.0


if __name__ == '__main__':
    sys.exit(pytest.main(sys.argv))
