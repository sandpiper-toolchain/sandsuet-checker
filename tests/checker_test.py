import netCDF4 as nc  # noqa: N813
import numpy as np
import pytest

from sandsuet_checker.checker import SandsuetChecker


@pytest.fixture
def valid_dataset() -> nc.Dataset:
    """Create a minimal sandsuet-compliant NetCDF4 dataset."""
    ds = nc.Dataset("in-memory", mode="w", memory=1024)

    ds.sandsuet_version = "1.0.0"

    ds.createDimension("y", 4)
    ds.createDimension("x", 4)

    y = ds.createVariable("y", "f8", ("y",), fill_value=-9999.0)
    y.units = "m"
    y[:] = np.arange(4) * 10.0

    x = ds.createVariable("x", "f8", ("x",), fill_value=-9999.0)
    x.units = "m"
    x[:] = np.arange(4) * 10.0

    eta = ds.createVariable("eta", "f4", ("y", "x"), fill_value=-9999.0)
    eta.units = "m"
    eta.long_name = "water_surface__elevation"
    eta[:] = np.zeros((4, 4))

    return ds


def test_valid(valid_dataset):
    checker = SandsuetChecker(valid_dataset)
    results = checker.run_all()
    assert all(result[1] in ("PASS", "SKIP") for result in results)


def test_from_path(tmpdir, valid_dataset):
    with tmpdir.as_cwd(), open("foo.nc", "wb") as stream:
        stream.write(valid_dataset.close())

    checker = SandsuetChecker.from_path(tmpdir.join("foo.nc"))
    results = checker.run_all()
    assert all(result[1] in ("PASS", "SKIP") for result in results)


@pytest.mark.parametrize("version", ("v1.0.0", "", "1.0", "foobar", None))
def test_bad_version(valid_dataset, version):
    if version is None:
        del valid_dataset.sandsuet_version
    else:
        valid_dataset.sandsuet_version = version

    checker = SandsuetChecker(valid_dataset)
    results = checker.run_all()

    messages = [result[2] for result in results if result[1] == "FAIL"]
    assert len(messages) == 1
    assert messages[0].startswith(
        "Global attribute 'sandsuet_version' is missing"
        if version is None
        else f"sandsuet_version {version!r}"
    )
