# scripts/browser/core/browser_session.py
import asyncio
import sys
from pathlib import Path
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

class BrowserSession:
    """Manages browser lifecycle and Chrome options"""

    def init(self, headless: bool = False, profile_dir: Path = None, output_dir: Path = None):
        self.headless = headless
        self.profile_dir = profile_dir or Path.home() / ".browser_profile"
        self.output_dir = output_dir or Path.cwd() / "downloads"
        self.browser = None
        self.tab = None

    def _build_options(self) -> ChromiumOptions:
        """Build Chrome options with all necessary flags"""
        options = ChromiumOptions()

        # Profile directory for session persistence
        self.profile_dir.mkdir(exist_ok=True, parents=True)
        options.add_argument(f'--user-data-dir={self.profile_dir}')

        if self.headless:
            options.add_argument('--headless=new')
        else:
            options.add_argument('--start-maximized')

        # Standard stability options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')

        return options

    async def aenter(self):
        """Async context manager entry"""
        self.browser = Chrome(options=self._build_options())
        self.tab = await self.browser.start()
        await self._setup_downloads()
        return self.tab

    async def aexit(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup"""
        print("Closing browser...", file=sys.stderr)

        if self.tab:
            try:
                await self.tab.close()
            except:
                pass

        if self.browser:
            try:
                if hasattr(self.browser, 'close'):
                    await self.browser.close()
                elif hasattr(self.browser, 'quit'):
                    await self.browser.quit()
                elif hasattr(self.browser, 'aexit'):
                    await self.browser.aexit(None, None, None)
            except Exception as e:
                print(f"Error closing browser: {e}", file=sys.stderr)

        await asyncio.sleep(2)
        print("Browser cleanup complete", file=sys.stderr)

    async def _setup_downloads(self):
        """Configure Chrome download behavior"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if hasattr(self.tab, '_connection_handler'):
            try:
                await self.tab._connection_handler.execute_command({
                    "method": "Browser.setDownloadBehavior",
                    "params": {
                        "behavior": "allow",
                        "downloadPath": str(self.output_dir),
                        "eventsEnabled": True
                    }
                })
                print(f"Download directory set to: {self.output_dir}", file=sys.stderr)
            except Exception as e:
                print(f"Could not set download behavior: {e}", file=sys.stderr)