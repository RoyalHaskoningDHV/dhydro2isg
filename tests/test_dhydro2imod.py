"""Test the main dhydro2imod functionality."""

import pytest
from dhydro2isg.dhydro2isg_tmp import main


def test_main_function():
    """Test that main function runs without error."""
    # This should run without raising an exception
    main()


def test_main_function_output(capsys):
    """Test that main function produces expected output."""
    main()
    captured = capsys.readouterr()
    assert "D-HYDRO2iMOD converter" in captured.out
    assert "Version 0.0.1" in captured.out