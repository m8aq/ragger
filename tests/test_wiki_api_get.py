"""Retry behaviour for the wiki API helper.

A full ingestion run makes thousands of requests over a couple of hours and
`fetch_all.py` aborts the pipeline on any script failure, so a single transient
502 used to throw away the entire run.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from ragger import wiki


def _response(status: int) -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = status
    resp.raise_for_status = Mock()
    return resp


def test_returns_first_success_without_sleeping() -> None:
    with patch.object(wiki.requests, "get", return_value=_response(200)) as get, \
         patch.object(wiki.time, "sleep") as sleep:
        assert wiki.api_get({"action": "query"}).status_code == 200
        assert get.call_count == 1
        sleep.assert_not_called()


@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_retries_transient_status_then_succeeds(status: int) -> None:
    responses = [_response(status), _response(status), _response(200)]
    with patch.object(wiki.requests, "get", side_effect=responses) as get, \
         patch.object(wiki.time, "sleep") as sleep:
        assert wiki.api_get({"action": "query"}).status_code == 200
        assert get.call_count == 3
        assert sleep.call_count == 2


def test_backoff_is_exponential() -> None:
    responses = [_response(502), _response(502), _response(502), _response(200)]
    with patch.object(wiki.requests, "get", side_effect=responses), \
         patch.object(wiki.time, "sleep") as sleep:
        wiki.api_get({"action": "query"})
        assert [c.args[0] for c in sleep.call_args_list] == [1.0, 2.0, 4.0]


def test_retries_connection_errors() -> None:
    side_effect = [requests.ConnectionError("dropped"), _response(200)]
    with patch.object(wiki.requests, "get", side_effect=side_effect) as get, \
         patch.object(wiki.time, "sleep"):
        assert wiki.api_get({"action": "query"}).status_code == 200
        assert get.call_count == 2


def test_gives_up_after_max_attempts() -> None:
    with patch.object(wiki.requests, "get", return_value=_response(502)) as get, \
         patch.object(wiki.time, "sleep"):
        with pytest.raises(requests.RequestException):
            wiki.api_get({"action": "query"})
        assert get.call_count == wiki.API_MAX_ATTEMPTS


def test_does_not_retry_client_errors() -> None:
    """A 404 fails identically next time — retrying just wastes the wiki's time."""
    resp = _response(404)
    resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    with patch.object(wiki.requests, "get", return_value=resp) as get, \
         patch.object(wiki.time, "sleep") as sleep:
        with pytest.raises(requests.HTTPError):
            wiki.api_get({"action": "query"})
        assert get.call_count == 1
        sleep.assert_not_called()
