# scripts/browser/sites/chatgpt.py
import asyncio
from ..core.script_executor import ScriptExecutor
import sys

class ChatGPTSiteHandler:
    """Handler for ChatGPT-specific behaviors"""

    @staticmethod
    async def handle_zscaler_redirect(tab, url: str) -> bool:
        """Handle the Zscaler redirect with _sm_nck parameter"""
        if url == "https://chat.openai.com/?_sm_nck=1":
            print("Handling Zscaler redirect for ChatGPT...", file=sys.stderr)
            await asyncio.sleep(2)

            form_submitted = await ScriptExecutor.execute(tab, """
                const form = document.querySelector('form[action*="zscaler.net"]');
                if (form) {
                    form.submit();
                    return 'submitted';
                }
                return 'no_form';
            """)

            if form_submitted == 'submitted':
                print("Zscaler form auto-submitted", file=sys.stderr)
                await asyncio.sleep(3)
                return True

        return False