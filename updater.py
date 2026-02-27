import sys
import os
import asyncio
import hashlib
from pathlib import Path
import aiohttp

GITHUB_REPO = "FrenchToblerone54/ghostpayments"
COMPONENT = "ghostpayments"

class Updater:
    def __init__(self, check_interval=300, check_on_startup=True, http_proxy="", https_proxy=""):
        self.check_interval = check_interval
        self.check_on_startup = check_on_startup
        self.http_proxy = http_proxy
        self.https_proxy = https_proxy
        self.current_version = self._get_current_version()
        self.binary_url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{COMPONENT}"
        self.check_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    def _get_current_version(self):
        script_path = Path(sys.argv[0])
        if script_path.name == COMPONENT:
            return "v0.1.1"
        return "dev"

    def _proxy_for(self, url):
        if url.startswith("https://") and self.https_proxy:
            return self.https_proxy
        if url.startswith("http://") and self.http_proxy:
            return self.http_proxy
        return None

    async def http_get(self, url, timeout=10):
        proxy = self._proxy_for(url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def http_download(self, url, output_path, timeout=300):
        proxy = self._proxy_for(url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        f.write(chunk)

    async def check_for_update(self):
        try:
            data = await self.http_get(self.check_url)
            latest = data.get("tag_name", "")
            if not latest.startswith("v"):
                latest = f"v{latest}"
            if self.current_version == "dev":
                return None
            if latest != self.current_version:
                return latest
        except Exception:
            pass
        return None

    def verify_checksum(self, binary_path, expected):
        h = hashlib.sha256()
        with open(binary_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        actual = h.hexdigest()
        expected_hash = expected.split()[0].strip()
        return actual == expected_hash

    async def download_update(self, new_version):
        tmp_dir = Path(f"/tmp/ghostpayments-update-{os.getpid()}")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        binary_path = tmp_dir / COMPONENT
        sha_path = tmp_dir / f"{COMPONENT}.sha256"
        print(f"Downloading {new_version}...")
        await self.http_download(self.binary_url, binary_path, 300)
        await self.http_download(f"{self.binary_url}.sha256", sha_path, 30)
        expected = sha_path.read_text().strip()
        if not self.verify_checksum(binary_path, expected):
            print("Checksum mismatch — aborting update")
            return
        current_bin = Path(sys.argv[0]).resolve()
        os.chmod(binary_path, 0o755)
        args = " ".join(sys.argv[1:])
        os.execv("/bin/bash", ["/bin/bash", "-c", f"sleep 0.5; mv '{binary_path}' '{current_bin}'; exec '{current_bin}' {args}"])

    async def manual_update(self):
        if not self.http_proxy:
            self.http_proxy = os.getenv("HTTP_PROXY", "")
        if not self.https_proxy:
            self.https_proxy = os.getenv("HTTPS_PROXY", "")
        print(f"Current version: {self.current_version}")
        print("Checking for updates...")
        new_version = await self.check_for_update()
        if not new_version:
            print("Already up to date.")
            return
        print(f"Update available: {new_version}")
        await self.download_update(new_version)
        print("Restarting service...")
        os.system("systemctl restart ghostpayments")

    async def update_loop(self, shutdown_event):
        if self.check_on_startup:
            new_version = await self.check_for_update()
            if new_version:
                await self.download_update(new_version)
                shutdown_event.set()
                return
        while not shutdown_event.is_set():
            try:
                await asyncio.sleep(self.check_interval)
                new_version = await self.check_for_update()
                if new_version:
                    await self.download_update(new_version)
                    shutdown_event.set()
                    return
            except asyncio.CancelledError:
                break
            except Exception:
                pass
