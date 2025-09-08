# scripts/browser/core/script_executor.py
from typing import Any

class ScriptExecutor:
    """Handles all JavaScript execution with proper response parsing"""

    @staticmethod
    async def execute(tab, script: str) -> str:
        """Execute JavaScript and handle pydoll's dict response format"""
        response = await tab.execute_script(script)
        return ScriptExecutor._extract_value(response)

    @staticmethod
    def _extract_value(response: Any) -> str:
        """Extract actual value from pydoll's nested response structure"""
        if isinstance(response, dict):
            result = response.get('result', {})
            if isinstance(result, dict):
                inner_result = result.get('result', {})
                if isinstance(inner_result, dict):
                    return str(inner_result.get('value', ''))
            return str(result)
        return str(response)

    @staticmethod
    async def get_url(tab) -> str:
        """Get current URL"""
        return await ScriptExecutor.execute(tab, 'return window.location.href')

    @staticmethod
    async def get_page_text(tab) -> str:
        """Get all visible text on page"""
        return await ScriptExecutor.execute(tab, 'return document.body.innerText')

    @staticmethod
    async def element_exists(tab, selector: str) -> bool:
        """Check if element exists"""
        result = await ScriptExecutor.execute(tab, f"""
            return document.querySelector('{selector}') !== null
        """)
        return result.lower() == 'true'