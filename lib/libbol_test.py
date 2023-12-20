"""
Unit tests for the `libbol` module.
"""
import os
import tempfile

import pytest

from . import libbol
from . import rarc


def _source_arc_filepaths() -> list[str]:
    if not os.getenv('COURSES_TEST_DATA_SET_DIR'):
        pytest.fail('COURSES_TEST_DATA_SET_DIR environment variable not set. A path to a directory '
                    'containing the stock `.arc` course files must be provided.')
    data_set_dir = os.environ['COURSES_TEST_DATA_SET_DIR']
    if not os.path.isdir(data_set_dir):
        pytest.fail(f'"{data_set_dir}" is not a valid directory.')

    filepaths = []
    for dirpath, dirnames, filenames in os.walk(data_set_dir):
        dirnames.sort()
        for filename in sorted(filenames):
            if filename.endswith('.arc'):
                filepath = os.path.join(dirpath, filename)
                filepaths.append(filepath)
    if not filepaths:
        pytest.fail(f'No `.arc` file could be sourced from "{data_set_dir}".')
    return filepaths


def _get_bol_file(arc_filepath: str) -> bytes:
    """
    Unpacks the RARC file given its filepath, and reads the BOL file, if present.
    """
    with open(arc_filepath, "rb") as f:
        archive = rarc.Archive.from_file(f)

    with tempfile.TemporaryDirectory() as tmp_dir:
        archive.extract_to(tmp_dir)

        for dirpath, _dirnames, filenames in os.walk(tmp_dir):
            for filename in filenames:
                if filename.endswith('.bol'):
                    filepath = os.path.join(dirpath, filename)
                    with open(filepath, 'rb') as f:
                        return f.read()

    return bytes()


@pytest.mark.parametrize("arc_filepath", _source_arc_filepaths())
def test_stock_data_set(arc_filepath):
    original_data = _get_bol_file(arc_filepath)
    assert original_data

    bol = libbol.BOL.from_bytes(original_data)
    baked_data = bol.to_bytes()

    original_length = len(original_data)
    baked_length = len(baked_data)
    assert original_length == baked_length
    assert original_data == baked_data
