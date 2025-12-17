# release_service.py

import dataclasses
import hashlib
import requests
import abc
import os
import logging
import re
from typing import Optional, Callable
from paths import YMU_DLL_DIR, USER_AGENT


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ReleaseData:
    """Represents the standardized information for a single release."""

    version_tag: str
    download_url: str
    asset_name: str
    checksum: Optional[str] = None
    release_notes: Optional[str] = "No release notes available."


class SecurityException(Exception):
    """Raised when a security check fails (e.g., checksum mismatch)."""

    pass


class ReleaseProvider(abc.ABC):
    """Abstract base class for services that provide release information."""

    @abc.abstractmethod
    def get_latest_release(self) -> Optional[ReleaseData]:
        """
        Fetches the data of the latest release from the source.
        Returns a ReleaseData object or None if no release was found.
        """
        raise NotImplementedError


class GitHubAPIProvider(ReleaseProvider):
    """Implementation of the ReleaseProvider that uses the GitHub API."""

    def __init__(self, repository: str, asset_extension: str = ".dll"):
        """
        Initializes the provider for a specific GitHub repository.
        :param repository: The repository name in the format "User/Repo".
        :param asset_extension: The file extension of the main asset.
        """
        self.api_url = f"https://api.github.com/repos/{repository}/releases/latest"
        self.asset_extension = asset_extension
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": USER_AGENT,
        }

    def get_latest_release(self) -> Optional[ReleaseData]:
        """
        Fetches the latest release from the GitHub API and parses the data.
        """
        try:
            response = requests.get(self.api_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            version_tag = data.get("tag_name")
            release_notes = data.get("body", "No release notes available.")
            assets = data.get("assets", [])

            download_url = None
            asset_name = None

            for asset in assets:
                if asset.get("name", "").endswith(self.asset_extension):
                    download_url = asset.get("browser_download_url")
                    asset_name = asset.get("name")
                    break

            checksum = None
            if release_notes:
                # Searches for a 64-character hex string (SHA256)
                match = re.search(r"\b[a-fA-F0-9]{64}\b", release_notes)
                if match:
                    checksum = match.group(0)

            if not all([version_tag, download_url, asset_name]):
                logger.error(
                    "Essential release information could not be found (URL, asset name, etc.)."
                )
                return None

            return ReleaseData(
                version_tag=version_tag,
                download_url=download_url,  # type: ignore
                checksum=checksum,
                release_notes=release_notes,
                asset_name=asset_name,  # type: ignore
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"A network error occurred: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return None


def get_local_sha256(dll_path: str) -> str | None:
    """
    Calculates the SHA256 checksum of the locally available DLL.
    :param dll_path: The path to the local DLL file.
    """
    if os.path.exists(dll_path):
        sha256_hash = hashlib.sha256()
        with open(dll_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        checksum = sha256_hash.hexdigest()
        logger.debug(f"Calculated local checksum for {dll_path}: {checksum}")
        return checksum
    else:
        logger.warning(
            f"Local file not found at {dll_path}, cannot calculate checksum."
        )
        return None


def download_and_verify_release(
    release_data: ReleaseData,
    progress_signal: Optional[Callable[[int], None]] = None,
    **kwargs,
) -> bool:
    """
    Downloads a release file, verifies its integrity, and reports progress.
    """
    download_path = os.path.join(YMU_DLL_DIR, release_data.asset_name)
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            release_data.download_url, stream=True, timeout=30, headers=headers
        )
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded_size = 0

        os.makedirs(os.path.dirname(download_path), exist_ok=True)

        with open(download_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded_size += len(chunk)
                if total_size > 0 and progress_signal:
                    percentage = int((downloaded_size / total_size) * 100)
                    if progress_signal:
                        if hasattr(progress_signal, "emit"):
                            progress_signal.emit(percentage)
                        else:
                            progress_signal(percentage)

        logger.info(f"Download of '{release_data.asset_name}' complete.")

        if not release_data.checksum:
            logger.warning("No remote checksum provided. Skipping integrity check.")
            return True

        logger.info("Verifying file integrity...")
        calculated_checksum = get_local_sha256(download_path)

        logger.debug(f"  Expected checksum: {release_data.checksum}")
        logger.debug(f"  Calculated checksum: {calculated_checksum}")

        if (
            calculated_checksum
            and calculated_checksum.lower() == release_data.checksum.lower()
        ):
            logger.info("Integrity check successful!")
            return True
        else:
            raise SecurityException(
                "Checksums do not match! The file might be corrupted or tampered with."
            )

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading the file: {e}")
        return False
    except IOError as e:
        logger.error(f"Error writing the file: {e}")
        return False
    except SecurityException as e:
        logger.critical(f"SECURITY WARNING: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] [%(name)-18s] %(message)s",
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

        success = download_and_verify_release(latest_release)
        if success:
            dll_path = os.path.join(YMU_DLL_DIR, latest_release.asset_name)
            print(f"\n'{dll_path}' was successfully downloaded and verified.")
        else:
            print(f"\nDownload or verification FAILED. Check logs above.")
    else:
        print("Could not find a valid release.")
