import datetime
from unittest.mock import Mock, patch

import pytest
import requests

import post_issue as uut


def make_resp_mock(*, status_code=200, json_ret=None, reason=None, url=None):
    resp = Mock(name="mock_response")
    resp.status_code = status_code
    resp.json.return_value = json_ret
    resp.reason = reason
    resp.url = url
    return resp


class TestGetToken:
    def test_gets_token(self):
        uut.host_info = {"host": "https://localhost/"}
        with patch.object(uut, "requests", name="mock_req") as mock_requests:
            mock_requests.post.side_effect = (
                lambda endpoint, json, **kwargs: make_resp_mock(
                    json_ret={
                        "token": f"{endpoint}-{json['username']}-{json['password']}"
                    }
                )
            )

            token = uut.get_token("user", "pass")

        assert token == "https://localhost/wp-json/jwt-auth/v1/token-user-pass"

    def test_explains_authentication_error(self):
        uut.host_info = {"host": "https://localhost/"}
        with patch.object(uut, "requests", name="mock_req") as mock_requests:
            mock_requests.HTTPError = requests.HTTPError
            mock_requests.post.side_effect = (
                lambda endpoint, json, **kwargs: make_resp_mock(
                    status_code=403,
                    reason="forbidden",
                    url=endpoint,
                    json_ret={"message": "Bad password"},
                )
            )

            with pytest.raises(
                requests.HTTPError,
                match="Failed to get JWT token. 403 error: Bad password for url: https://localhost/wp-json/jwt-auth/v1/token",
            ):
                uut.get_token("user", "pass")

        # Test passes if exception raised

    def test_raises_generic_error_on_non_200_status(self):
        uut.host_info = {"host": "https://localhost/"}
        with patch.object(uut, "requests", name="mock_req") as mock_requests:
            mock_requests.HTTPError = requests.HTTPError
            mock_requests.JSONDecodeError = requests.JSONDecodeError
            mock_requests.post.side_effect = (
                lambda endpoint, json, **kwargs: make_resp_mock(
                    status_code=404,
                    reason="just because",
                    url=endpoint,
                )
            )

            with pytest.raises(
                requests.HTTPError,
                match="Failed to get JWT token. 404 error: just because for url: https://localhost*",
            ):
                uut.get_token("user", "pass")

        # Test passes if exception raised


class TestIssueReleaseTime:
    def test_returns_the_first_monday_of_january_at_11_central_standard(self):
        d = datetime.date(year=2000, month=1, day=17)

        result = uut.issue_release_time(d)

        assert result.isoformat() == "2000-01-03T17:00:00"

    def test_returns_the_first_monday_of_june_at_11_central_daylight(self):
        d = datetime.date(year=2000, month=6, day=17)

        result = uut.issue_release_time(d)

        assert result.isoformat() == "2000-06-05T16:00:00"

    def test_returns_the_first_monday_of_the_next_month_from_december(self):
        with patch.object(uut, "datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.datetime(
                year=1999, month=12, day=30, hour=12, minute=13, second=14
            )

            result = uut.issue_release_time()

        assert result.isoformat() == "2000-01-03T17:00:00"


class TestWpRestUrl:
    def test_returns_url_with_default_namespace(self):
        uut.host_info = {"host": "https://testy.com"}

        result = uut.wp_rest_url("media")

        assert result == "https://testy.com/wp-json/wp/v2/media"

    def test_returns_url_with_passed_namespace(self):
        uut.host_info = {"host": "https://testy.com"}

        result = uut.wp_rest_url("media", "sg/v1/")

        assert result == "https://testy.com/wp-json/sg/v1/media"

    def test_works_with_namespaces_that_lack_an_ending_slash(self):
        uut.host_info = {"host": "https://testy.com"}

        result = uut.wp_rest_url("media", "sg/v1")

        assert result == "https://testy.com/wp-json/sg/v1/media"

    def test_works_even_when_slashes_abound(self):
        uut.host_info = {"host": "https://testy.com"}

        result = uut.wp_rest_url("/media", "sg/v1/")

        assert result == "https://testy.com/wp-json/sg/v1/media"
