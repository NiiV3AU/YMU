# release_service.py

import abc
import dataclasses
import hashlib
import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

import requests

from core.paths import USER_AGENT, YMU_CACHE_FILE_PATH, YMU_DLL_DIR

logger = logging.getLogger(__name__)


@runtime_checkable
class SupportsEmit(Protocol):
    """A Qt Signal (has .emit) or any object exposing an emit(int) method."""

    def emit(self, value: int, /) -> None: ...


# Progress can be reported either by a plain callback or a Qt Signal.
ProgressReporter = Callable[[int], None] | SupportsEmit


@dataclasses.dataclass
class ReleaseData:
    """Represents the standardized information for a single release."""

    version_tag: str
    download_url: str
    asset_name: str
    checksum: str | None = None
    release_notes: str | None = "No release notes available."


class SecurityException(Exception):
    """Raised when a security check fails (e.g., checksum mismatch)."""


class RateLimitException(Exception):
    """Raised when the GitHub API rate limit is exceeded."""

    def __init__(self, message: str, reset_timestamp: int | None = None):
        super().__init__(message)
        self.reset_timestamp = reset_timestamp
        if reset_timestamp:
            self.wait_minutes = max(1, int((reset_timestamp - time.time()) / 60))
        else:
            self.wait_minutes = None


class FileLockedException(PermissionError):
    """Raised when the target DLL is locked by another process (e.g. GTA V)."""


_cache_lock = threading.Lock()
_in_memory_cache: dict | None = None
CACHE_TTL_SECONDS = 300.0  # 5 minutes


def _read_cache() -> dict:
    global _in_memory_cache
    if _in_memory_cache is not None:
        return _in_memory_cache.copy()

    if not os.path.exists(YMU_CACHE_FILE_PATH):
        _in_memory_cache = {}
        return {}
    try:
        with open(YMU_CACHE_FILE_PATH, encoding="utf-8") as f:
            data = json.load(f)
            _in_memory_cache = data if isinstance(data, dict) else {}
            return _in_memory_cache.copy()
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read API cache: {e}")
        _in_memory_cache = {}
        return {}


def _write_cache(cache_data: dict) -> None:
    global _in_memory_cache
    _in_memory_cache = cache_data.copy()
    tmp_path = YMU_CACHE_FILE_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(YMU_CACHE_FILE_PATH), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        os.replace(tmp_path, YMU_CACHE_FILE_PATH)
    except OSError as e:
        logger.warning(f"Failed to write API cache: {e}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def clear_memory_cache() -> None:
    """Clears the in-memory release API cache."""
    global _in_memory_cache
    with _cache_lock:
        _in_memory_cache = None


def get_cached_release(
    repo: str, max_age: float = CACHE_TTL_SECONDS
) -> tuple[ReleaseData | None, str | None, bool]:
    """
    Returns (ReleaseData or None, etag or None, is_fresh: bool).
    """
    with _cache_lock:
        cache = _read_cache()
        entry = cache.get(repo)
        if not isinstance(entry, dict):
            return (None, None, False)

        etag = entry.get("etag")
        timestamp = entry.get("timestamp", 0)
        if not isinstance(timestamp, (int, float)):
            timestamp = 0
        rel_dict = entry.get("release_data")
        if not isinstance(rel_dict, dict):
            return (None, etag, False)

        try:
            rel_data = ReleaseData(
                version_tag=rel_dict["version_tag"],
                download_url=rel_dict["download_url"],
                asset_name=rel_dict["asset_name"],
                checksum=rel_dict.get("checksum"),
                release_notes=rel_dict.get("release_notes"),
            )
        except (KeyError, TypeError):
            return (None, etag, False)

        is_fresh = (time.time() - timestamp) < max_age
        return (rel_data, etag, is_fresh)


def save_cached_release(
    repo: str, release_data: ReleaseData, etag: str | None = None
) -> None:
    with _cache_lock:
        cache = _read_cache()
        entry = cache.get(repo, {})
        if not isinstance(entry, dict):
            entry = {}

        if etag:
            entry["etag"] = etag
        entry["timestamp"] = time.time()
        entry["release_data"] = {
            "version_tag": release_data.version_tag,
            "download_url": release_data.download_url,
            "asset_name": release_data.asset_name,
            "checksum": release_data.checksum,
            "release_notes": release_data.release_notes,
        }
        cache[repo] = entry
        _write_cache(cache)


def touch_cached_release(repo: str) -> None:
    with _cache_lock:
        cache = _read_cache()
        entry = cache.get(repo)
        if isinstance(entry, dict):
            entry["timestamp"] = time.time()
            cache[repo] = entry
            _write_cache(cache)


class ReleaseProvider(abc.ABC):
    """Abstract base class for services that provide release information."""

    @abc.abstractmethod
    def get_latest_release(self) -> ReleaseData | None:
        """
        Fetches the data of the latest release from the source.
        Returns a ReleaseData object or None if no release was found.
        """
        raise NotImplementedError


def extract_checksum_from_release(text: str | None) -> str | None:
    """Extracts a SHA256 checksum from release notes text.

    Requires explicit keywords (e.g. SHA-256, checksum, hash) or
    a standard sha256sum format line (<hash> [*]<filename>).
    Arbitrary standalone 64-hex strings (such as Git commit hashes)
    are intentionally ignored to prevent false checksum mismatch errors.
    """
    if not text:
        return None

    # 1. Look for explicit keyword indicators: sha-256, sha256, checksum, hash
    match = re.search(r"(?i)(?:sha[-_]?256|checksum|hash)[\s:=]+([a-f0-9]{64})", text)
    if match:
        return match.group(1).lower()

    # 2. Look for standard sha256sum line: <hash>  <filename> or <hash> *<filename>
    sum_match = re.search(
        r"(?m)^([a-f0-9]{64})\s+[*]?\S+\.(?:dll|exe|zip|bin)\b", text, re.IGNORECASE
    )
    if sum_match:
        return sum_match.group(1).lower()

    # 3. Look for reverse format: <filename>[:= ]+<hash>
    rev_match = re.search(
        r"(?i)\b\S+\.(?:dll|exe|zip|bin)[\s:=]+([a-f0-9]{64})\b", text
    )
    if rev_match:
        return rev_match.group(1).lower()

    return None


class GitHubAPIProvider(ReleaseProvider):
    """Implementation of the ReleaseProvider that uses the GitHub API with persistent ETag caching."""

    def __init__(self, repository: str, asset_extension: str = ".dll"):
        """
        Initializes the provider for a specific GitHub repository.
        :param repository: The repository name in the format "User/Repo".
        :param asset_extension: The file extension of the main asset (or "" for any).
        """
        self.repository = repository
        self.api_url = f"https://api.github.com/repos/{repository}/releases/latest"
        self.asset_extension = asset_extension
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": USER_AGENT,
        }

    def get_latest_release(self, force_refresh: bool = False) -> ReleaseData | None:
        """Fetches the latest release from the GitHub API and parses the data.
        Uses persistent disk caching and ETag conditional requests to avoid rate limits.

        :param force_refresh: If True, bypasses disk caching and ETag validation.
        :return: A ReleaseData object or None if no release exists.
        :raises RateLimitException: If GitHub API returns HTTP 403 with rate limit exceeded.
        :raises requests.RequestException: If network communication fails.
        """
        cached_data, cached_etag, is_fresh = get_cached_release(self.repository)

        if is_fresh and not force_refresh and cached_data is not None:
            logger.debug(f"Using fresh disk-cached release for {self.repository}.")
            return cached_data

        req_headers = self.headers.copy()
        if cached_etag and cached_data is not None and not force_refresh:
            req_headers["If-None-Match"] = cached_etag

        try:
            response = requests.get(self.api_url, headers=req_headers, timeout=10)

            # 304 Not Modified: Cache is still valid! Doesn't count toward rate limits.
            if response.status_code == 304 and cached_data is not None:
                logger.info(
                    f"Release data for {self.repository} not modified (304). Cache touched."
                )
                touch_cached_release(self.repository)
                return cached_data

            # 403 Forbidden / Rate limit check
            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_raw = response.headers.get("X-RateLimit-Reset")
                reset_time = (
                    int(reset_raw) if reset_raw and reset_raw.isdigit() else None
                )

                if remaining == "0" or "rate limit" in response.text.lower():
                    if cached_data is not None:
                        logger.warning(
                            f"GitHub API rate limit hit for {self.repository}. Falling back to cached release."
                        )
                        return cached_data
                    else:
                        wait_min = (
                            max(1, int((reset_time - time.time()) / 60))
                            if reset_time
                            else None
                        )
                        wait_msg = f" Resets in {wait_min} min." if wait_min else ""
                        raise RateLimitException(
                            f"GitHub API rate limit exceeded.{wait_msg}",
                            reset_timestamp=reset_time,
                        )

            response.raise_for_status()
            data = response.json()

            version_tag = data.get("tag_name")
            release_notes = data.get("body", "No release notes available.")
            assets = data.get("assets", [])

            download_url = None
            asset_name = None

            if self.asset_extension:
                for asset in assets:
                    if (
                        asset.get("name", "")
                        .lower()
                        .endswith(self.asset_extension.lower())
                    ):
                        download_url = asset.get("browser_download_url")
                        asset_name = asset.get("name")
                        break
            else:
                download_url = data.get("html_url", "")
                asset_name = version_tag or "release"

            checksum = extract_checksum_from_release(release_notes)

            if checksum is None:
                logger.warning(
                    f"No SHA256 checksum found in the release notes for "
                    f"'{version_tag}' ({self.api_url}). Integrity cannot be "
                    f"verified and up-to-date state cannot be confirmed."
                )

            if version_tag is None or (
                self.asset_extension and (download_url is None or asset_name is None)
            ):
                logger.error(
                    "Essential release information could not be found (URL, asset name, etc.)."
                )
                return None

            release_obj = ReleaseData(
                version_tag=version_tag,
                download_url=download_url or "",
                checksum=checksum,
                release_notes=release_notes,
                asset_name=asset_name or "",
            )

            etag = response.headers.get("ETag")
            save_cached_release(self.repository, release_obj, etag)
            return release_obj

        except RateLimitException:
            raise
        except requests.exceptions.RequestException as e:
            if cached_data is not None:
                logger.warning(
                    f"Network error fetching release for {self.repository}: {e}. Using cached data."
                )
                return cached_data
            logger.error(f"A network error occurred: {e}")
            return None
        except Exception:
            logger.exception(
                "An unexpected error occurred while fetching release data."
            )
            return None


def get_local_sha256(dll_path: str) -> str | None:
    """
    Calculates the SHA256 checksum of the locally available DLL.
    :param dll_path: The path to the local DLL file.
    """
    if os.path.isfile(dll_path):
        try:
            sha256_hash = hashlib.sha256()
            with open(dll_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            checksum = sha256_hash.hexdigest()
            logger.debug(f"Calculated local checksum for {dll_path}: {checksum}")
            return checksum
        except OSError as e:
            logger.warning(f"Could not read local DLL at {dll_path}: {e}")
            return None
    else:
        logger.warning(
            f"Local file not found at {dll_path}, cannot calculate checksum."
        )
        return None


def download_and_verify_release(
    release_data: ReleaseData,
    progress_signal: ProgressReporter | None = None,
) -> tuple[bool, bool]:
    """Downloads a release file to a temporary file, verifies its integrity,
    and moves it atomically to the final destination.

    :return: A tuple of (success, is_verified).
             - (True, True): downloaded and SHA256 verified
             - (True, False): downloaded successfully, but unverified (no remote checksum)
             - (False, False): download or verification failed
    :raises FileLockedException: If the destination file is locked by a running process.
    """
    raw_name = release_data.asset_name
    if (
        not raw_name
        or "/" in raw_name
        or "\\" in raw_name
        or not re.match(r"^[A-Za-z0-9._-]+$", raw_name)
        or raw_name in (".", "..")
    ):
        logger.error(
            f"Unsafe or invalid asset name rejected: {release_data.asset_name!r}"
        )
        return (False, False)

    safe_name = raw_name

    download_path = os.path.join(YMU_DLL_DIR, safe_name)
    tmp_path = download_path + ".tmp"
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            release_data.download_url, stream=True, timeout=30, headers=headers
        )
        try:
            response.raise_for_status()

            try:
                cl_header = (
                    response.headers.get("Content-Length")
                    or response.headers.get("content-length")
                    or 0
                )
                total_size = int(cl_header)
            except (ValueError, TypeError):
                total_size = 0
            downloaded_size = 0
            last_percentage = -1
            start_time = time.monotonic()

            os.makedirs(os.path.dirname(download_path), exist_ok=True)

            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if time.monotonic() - start_time > 120:
                        raise requests.exceptions.ReadTimeout(
                            "Download exceeded 120s deadline"
                        )
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    if total_size > 0 and progress_signal is not None:
                        percentage = min(100, max(0, int((downloaded_size / total_size) * 100)))
                        if percentage != last_percentage:
                            last_percentage = percentage
                            if isinstance(progress_signal, SupportsEmit):
                                progress_signal.emit(percentage)
                            else:
                                progress_signal(percentage)

            if total_size > 0 and downloaded_size < int(total_size * 0.999):
                calculated_hash = get_local_sha256(tmp_path) if release_data.checksum else None
                if not (release_data.checksum and calculated_hash and calculated_hash.lower() == release_data.checksum.lower()):
                    logger.error(
                        f"Download incomplete for '{safe_name}': received {downloaded_size} of {total_size} bytes."
                    )
                    return (False, False)
        finally:
            response.close()

        logger.info(f"Download of '{safe_name}' complete.")

        is_verified = False
        if release_data.checksum:
            logger.info("Verifying file integrity...")
            calculated_checksum = get_local_sha256(tmp_path)

            logger.debug(f"  Expected checksum: {release_data.checksum}")
            logger.debug(f"  Calculated checksum: {calculated_checksum}")

            if (
                calculated_checksum
                and calculated_checksum.lower() == release_data.checksum.lower()
            ):
                logger.info("Integrity check successful!")
                is_verified = True
            else:
                raise SecurityException(
                    "Checksums do not match! The file might be corrupted or tampered with."
                )
        else:
            logger.warning("No remote checksum provided. Skipping integrity check.")

        try:
            os.replace(tmp_path, download_path)
        except PermissionError as e:
            winerror = getattr(e, "winerror", None)
            if winerror in (5, 32):
                logger.error(
                    f"Target file '{download_path}' is locked by another process (winerror={winerror}): {e}"
                )
                raise FileLockedException(
                    f"Target file '{download_path}' is locked by another process (GTA V)."
                ) from e
            logger.error(
                f"Permission denied replacing '{download_path}' (winerror={winerror}): {e}"
            )
            raise
        return (True, is_verified)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading the file: {e}")
        return (False, False)
    except FileLockedException:
        raise
    except OSError as e:
        logger.error(f"Error writing the file: {e}")
        return (False, False)
    except SecurityException as e:
        logger.critical(f"SECURITY WARNING: {e}")
        return (False, False)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] [%(name)-28s] %(message)s",
    )

    print("Searching for the latest YimMenu release...")
    provider = GitHubAPIProvider(repository="Mr-X-GTA/YimMenu")
    latest_release = provider.get_latest_release()

    if latest_release:
        print("-" * 30)
        print(f"Latest release found: {latest_release.version_tag}")
        print(f"Asset: {latest_release.asset_name}")
        print(f"Checksum: {latest_release.checksum}")
        print("-" * 30)

        success, verified = download_and_verify_release(latest_release)
        if success:
            dll_path = os.path.join(YMU_DLL_DIR, latest_release.asset_name)
            ver_text = "and verified" if verified else "(unverified)"
            print(f"\n'{dll_path}' was successfully downloaded {ver_text}.")
        else:
            print("\nDownload or verification FAILED. Check logs above.")
    else:
        print("Could not find a valid release.")
