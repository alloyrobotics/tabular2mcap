#!/usr/bin/env python3
"""Tests for cache download retry logic."""

import urllib.error
from pathlib import Path
from unittest.mock import patch

from tabular2mcap.schemas.cache import download_file


class TestDownloadRetry:
    """Tests for download_file retry behavior."""

    def test_successful_download(self, tmp_path: Path):
        """Test successful download on first attempt."""
        dest = tmp_path / "test.zip"

        with patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock:
            mock.return_value = None
            result = download_file("http://example.com/file.zip", dest)

        assert result is True
        mock.assert_called_once()

    def test_retry_on_server_error(self, tmp_path: Path):
        """Test retry on HTTP 5xx errors."""
        dest = tmp_path / "test.zip"

        with (
            patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock,
            patch("tabular2mcap.schemas.cache.time.sleep") as mock_sleep,
        ):
            # Fail twice with 503, then succeed
            mock.side_effect = [
                urllib.error.HTTPError(
                    "http://example.com", 503, "Service Unavailable", {}, None
                ),
                urllib.error.HTTPError(
                    "http://example.com", 503, "Service Unavailable", {}, None
                ),
                None,  # Success
            ]
            result = download_file(
                "http://example.com/file.zip",
                dest,
                max_retries=3,
                initial_backoff=0.1,
            )

        assert result is True
        assert mock.call_count == 3
        assert mock_sleep.call_count == 2

    def test_no_retry_on_client_error(self, tmp_path: Path):
        """Test no retry on HTTP 4xx errors."""
        dest = tmp_path / "test.zip"

        with patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock:
            mock.side_effect = urllib.error.HTTPError(
                "http://example.com", 404, "Not Found", {}, None
            )
            result = download_file("http://example.com/file.zip", dest, max_retries=3)

        assert result is False
        mock.assert_called_once()  # No retries

    def test_retry_on_network_error(self, tmp_path: Path):
        """Test retry on network errors (URLError)."""
        dest = tmp_path / "test.zip"

        with (
            patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock,
            patch("tabular2mcap.schemas.cache.time.sleep") as mock_sleep,
        ):
            # Fail once with network error, then succeed
            mock.side_effect = [
                urllib.error.URLError("Connection refused"),
                None,  # Success
            ]
            result = download_file(
                "http://example.com/file.zip",
                dest,
                max_retries=3,
                initial_backoff=0.1,
            )

        assert result is True
        assert mock.call_count == 2
        assert mock_sleep.call_count == 1

    def test_max_retries_exceeded(self, tmp_path: Path):
        """Test failure after max retries exceeded."""
        dest = tmp_path / "test.zip"

        with (
            patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock,
            patch("tabular2mcap.schemas.cache.time.sleep"),
        ):
            # Always fail with 503
            mock.side_effect = urllib.error.HTTPError(
                "http://example.com", 503, "Service Unavailable", {}, None
            )
            result = download_file(
                "http://example.com/file.zip",
                dest,
                max_retries=2,
                initial_backoff=0.1,
            )

        assert result is False
        assert mock.call_count == 3  # Initial + 2 retries

    def test_no_retry_on_unexpected_error(self, tmp_path: Path):
        """Test no retry on unexpected exceptions."""
        dest = tmp_path / "test.zip"

        with patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock:
            mock.side_effect = RuntimeError("Unexpected error")
            result = download_file("http://example.com/file.zip", dest, max_retries=3)

        assert result is False
        mock.assert_called_once()  # No retries

    def test_zero_retries(self, tmp_path: Path):
        """Test with max_retries=0 (single attempt only)."""
        dest = tmp_path / "test.zip"

        with patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock:
            mock.side_effect = urllib.error.HTTPError(
                "http://example.com", 503, "Service Unavailable", {}, None
            )
            result = download_file("http://example.com/file.zip", dest, max_retries=0)

        assert result is False
        mock.assert_called_once()


class TestEnvVarParsing:
    """Tests for environment variable parsing with safeguards."""

    def test_negative_max_retries_clamped(self, tmp_path: Path):
        """Test that negative max_retries is clamped to 0 (one attempt, no retries)."""
        dest = tmp_path / "test.zip"

        with patch("tabular2mcap.schemas.cache.urllib.request.urlretrieve") as mock:
            mock.side_effect = urllib.error.HTTPError(
                "http://example.com", 503, "Service Unavailable", {}, None
            )
            result = download_file("http://example.com/file.zip", dest, max_retries=-1)

        assert result is False
        mock.assert_called_once()  # Clamped to 0: one attempt, no retries
