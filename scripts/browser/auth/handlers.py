# scripts/browser/auth/handlers.py
import asyncio
import time
import sys
from typing import Optional
from ..core.script_executor import ScriptExecutor

class AuthHandler:
    """Base authentication handler"""
    
    async def wait_for_manual_login(self, tab, timeout_seconds: int = 300, 
                                   check_element: str = None, site_name: str = "") -> bool:
        """Base implementation for manual login waiting"""
        print("=" * 60, file=sys.stderr)
        print(f"MANUAL LOGIN REQUIRED{' for ' + site_name if site_name else ''}", file=sys.stderr)
        print(f"Timeout: {timeout_seconds} seconds", file=sys.stderr)
        if check_element:
            print(f"Looking for element: {check_element}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        initial_url = await ScriptExecutor.get_url(tab)
        print(f"Initial URL: {initial_url}", file=sys.stderr)
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                current_url = await ScriptExecutor.get_url(tab)
                
                # Check if URL changed from login page
                if current_url != initial_url:
                    login_indicators = ["login", "log-in", "auth", "signin", "sign-in"]
                    is_login_page = any(ind in current_url.lower() for ind in login_indicators)
                    
                    if not is_login_page:
                        print(f"Login detected - URL changed to: {current_url}", file=sys.stderr)
                        await asyncio.sleep(3)
                        return True
                
                # Check for specific element
                if check_element and await ScriptExecutor.element_exists(tab, check_element):
                    print(f"Login detected - found element: {check_element}", file=sys.stderr)
                    await asyncio.sleep(2)
                    return True
                
                # Check for common post-login indicators
                page_content = await ScriptExecutor.get_page_text(tab)
                indicators = ["logout", "sign out", "dashboard", "welcome", "ログアウト", "マイページ"]
                if any(indicator in page_content.lower() for indicator in indicators):
                    print(f"Login detected via page content", file=sys.stderr)
                    await asyncio.sleep(2)
                    return True
                    
            except Exception as e:
                print(f"Error during login check: {e}", file=sys.stderr)
            
            await asyncio.sleep(2)
        
        print("Login timeout reached", file=sys.stderr)
        return False


class ChatGPTAuthHandler(AuthHandler):
    """ChatGPT-specific authentication handling"""
    
    async def check_logged_in(self, tab) -> bool:
        """Check if already logged into ChatGPT"""
        login_check = await ScriptExecutor.execute(tab, """
            const profileBtn = document.querySelector('[data-testid="accounts-profile-button"]');
            if (profileBtn) return 'logged_in';
            
            const sidebar = document.querySelector('[data-testid="sidebar-item-library"]');
            if (sidebar) return 'logged_in';
            
            const inputField = document.querySelector('#prompt-textarea');
            if (inputField) return 'logged_in';
            
            const bodyText = document.body.innerText || '';
            if (bodyText.includes('Log out') || bodyText.includes('ログアウト')) {
                return 'logged_in';
            }
            
            return 'not_logged_in';
        """)
        
        return login_check == 'logged_in'
    
    async def wait_for_login(self, tab, timeout_seconds: int = 300) -> bool:
        """Wait for ChatGPT login to complete"""
        print("Checking ChatGPT login status...", file=sys.stderr)
        
        if await self.check_logged_in(tab):
            print("Already logged into ChatGPT!", file=sys.stderr)
            return True
        
        initial_url = await ScriptExecutor.get_url(tab)
        seen_okta = False
        seen_auth_page = False
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                current_url = await ScriptExecutor.get_url(tab)
                print(f"current: {current_url}", file=sys.stderr)
                
                # Handle Zscaler redirect
                if "https://chat.openai.com/?_sm_nck=1" == current_url:
                    await asyncio.sleep(2)
                    await ScriptExecutor.execute(tab, """
                        const form = document.querySelector('form[action*="zscaler.net"]');
                        if (form) form.submit();
                    """)
                    await asyncio.sleep(3)
                    continue
                
                # Track Okta auth
                if "uim.jp.nttdata.com" in current_url:
                    print("In Okta auth...", file=sys.stderr)
                    seen_okta = True
                    await asyncio.sleep(5)
                    continue
                
                # Check if already logged in
                if await self.check_logged_in(tab):
                    print("ChatGPT login successful!", file=sys.stderr)
                    await asyncio.sleep(2)
                    return True
                
                # Track OpenAI auth
                if "auth.openai.com" in current_url:
                    print("On OpenAI auth page...", file=sys.stderr)
                    seen_auth_page = True
                    await asyncio.sleep(2)
                    continue
                
                # Check if back on ChatGPT
                if "chatgpt.com" in current_url and "/auth" not in current_url:
                    if seen_okta or seen_auth_page:
                        print("ChatGPT login complete!", file=sys.stderr)
                        await asyncio.sleep(5)
                        return True
                
            except Exception as e:
                print(f"Error during login check: {e}", file=sys.stderr)
                await asyncio.sleep(3)
        
        return False


class ZscalerAuthHandler(AuthHandler):
    """Zscaler authentication handling"""
    
    async def wait_for_auth(self, tab, timeout_seconds: int = 300) -> bool:
        """Wait for Zscaler authentication to complete"""
        print("=" * 60, file=sys.stderr)
        print("ZSCALER AUTHENTICATION REQUIRED", file=sys.stderr)
        print(f"Timeout: {timeout_seconds} seconds", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                error_element = await tab.find(
                    class_name="error-code",
                    timeout=1,
                    raise_exc=False
                )
                
                if not error_element:
                    current_url = await ScriptExecutor.get_url(tab)
                    page_content = await ScriptExecutor.get_page_text(tab)
                    
                    if "zscaler" not in page_content.lower() and "error" not in page_content.lower():
                        print(f"Zscaler auth successful: {current_url}", file=sys.stderr)
                        return True
                
                await tab.refresh()
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Error during Zscaler auth check: {e}", file=sys.stderr)
                await asyncio.sleep(5)