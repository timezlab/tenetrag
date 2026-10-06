"""Unit tests cannot open a network socket (FR-002)."""

import socket

import pytest
from pytest_socket import SocketBlockedError


# pytest-socket warns on every blocked attempt; here the attempt is the point.
@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket:UserWarning")
def test_opening_a_tcp_socket_is_blocked():
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
