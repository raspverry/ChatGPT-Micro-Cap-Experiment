# scripts/browser/workflow/processor.py
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List
from ..core.browser_session import BrowserSession
from ..core.script_executor import ScriptExecutor
from ..auth.handlers import ChatGPTAuthHandler, ZscalerAuthHandler, AuthHandler
from ..actions.registry import ActionRegistry
from ..actions import common  # Triggers action registration

class WorkflowProcessor:
    """Main workflow processing engine"""
    
    def __init__(self, output_dir: Path, headless: bool = False):
        self.output_dir = output_dir
        self.headless = headless
        self.auth_handlers = {
            'chatgpt': ChatGPTAuthHandler(),
            'zscaler': ZscalerAuthHandler(),
            'default': AuthHandler()
        }
    
    async def execute(self, workflow: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a workflow"""
        result = {
            "success": False,
            "steps": []
        }
        
        profile_dir = Path.home() / ".browser_profiles" / "default"
        
        async with BrowserSession(
            headless=self.headless,
            profile_dir=profile_dir,
            output_dir=self.output_dir
        ) as tab:
            
            print("Browser started", file=sys.stderr)
            
            for idx, step in enumerate(workflow):
                print(f"\n=== Step {idx + 1}: {step.get('name', 'Unnamed')} ===", file=sys.stderr)
                
                step_result = await self.execute_step(tab, idx, step)
                result["steps"].append(step_result)
                
                if not step_result.get("success", False):
                    break
                
                if idx < len(workflow) - 1:
                    await asyncio.sleep(2)
            
            result["success"] = all(s.get("success", False) for s in result["steps"])
        
        print("=== Workflow complete ===", file=sys.stderr)
        return result
    
    async def execute_step(self, tab, idx: int, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step"""
        step_result = {
            "name": step.get("name", f"Step {idx}"),
            "type": step.get("type", "navigate"),
            "success": False
        }
        
        try:
            # Handle navigation
            if step.get("url"):
                print(f"Navigating to: {step['url']}", file=sys.stderr)
                await tab.go_to(step["url"])
                await asyncio.sleep(3)
                
                current_url = await ScriptExecutor.get_url(tab)
                
                # Handle Zscaler redirect for ChatGPT
                if "chat.openai.com/?_sm_nck=1" in current_url:
                    from ..sites.chatgpt import ChatGPTSiteHandler
                    await ChatGPTSiteHandler.handle_zscaler_redirect(tab, current_url)
                
                # Check for Zscaler error
                zscaler_error = await tab.find(
                    class_name="error-code",
                    timeout=1,
                    raise_exc=False
                )
                
                if zscaler_error:
                    if not await self.auth_handlers['zscaler'].wait_for_auth(tab, 300):
                        step_result["error"] = "Zscaler auth failed"
                        return step_result
            
            # Handle login if needed
            if step.get("wait_login"):
                auth_handler = self._get_auth_handler(step.get("url", ""))
                
                if isinstance(auth_handler, ChatGPTAuthHandler):
                    login_success = await auth_handler.wait_for_login(
                        tab,
                        step.get("login_timeout", 300)
                    )
                else:
                    login_success = await auth_handler.wait_for_manual_login(
                        tab,
                        step.get("login_timeout", 300),
                        step.get("login_check"),
                        step.get("name", "")
                    )
                
                if not login_success:
                    step_result["error"] = "Login timeout"
                    return step_result
            
            # Navigate to target
            if step.get("target_url"):
                print(f"Navigating to target: {step['target_url']}", file=sys.stderr)
                await tab.go_to(step["target_url"])
                await asyncio.sleep(3)
            
            # Execute action
            action_type = step.get("type", "navigate")
            
            if action_type == "navigate":
                step_result["success"] = True
            
            elif action_type == "input":
                action_params = {k: v for k, v in step.items() 
                               if k not in ['name', 'type']}
                
                result = await ActionRegistry.execute("input", tab, **action_params)
                
                if result.get("success") and step.get("submit_button"):
                    result = await ActionRegistry.execute("click", tab, **action_params)
                
                if result.get("success") and step.get("wait_for_selector"):
                    result = await ActionRegistry.execute("wait_response", tab, **action_params)
                
                step_result["success"] = result.get("success", False)
                if not result.get("success"):
                    step_result["error"] = result.get("error")
            
            elif action_type in ["download", "extract"]:
                action_params = {k: v for k, v in step.items() 
                               if k not in ['name', 'type']}
                action_params['output_dir'] = self.output_dir
                
                result = await ActionRegistry.execute(
                    action_type, 
                    tab,
                    **action_params
                )
                step_result.update(result)
            
            else:
                try:
                    action_params = {k: v for k, v in step.items() 
                                   if k not in ['name', 'type']}
                    action_params['output_dir'] = self.output_dir
                    
                    result = await ActionRegistry.execute(
                        action_type,
                        tab,
                        **action_params
                    )
                    step_result.update(result)
                except ValueError:
                    step_result["success"] = True
            
        except Exception as e:
            step_result["error"] = str(e)
            print(f"Error in step: {e}", file=sys.stderr)
        
        return step_result
    
    def _get_auth_handler(self, url: str):
        """Get appropriate auth handler for URL"""
        if "chatgpt" in url or "openai" in url:
            return self.auth_handlers['chatgpt']
        elif "zscaler" in url:
            return self.auth_handlers['zscaler']
        return self.auth_handlers['default']