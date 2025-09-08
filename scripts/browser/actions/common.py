# scripts/browser/actions/common.py
import asyncio
import time
import sys
from pathlib import Path
from typing import Dict, Any
from .registry import ActionRegistry
from ..core.script_executor import ScriptExecutor

@ActionRegistry.register("input", aliases=["type", "fill"])
async def input_text(tab, **kwargs) -> Dict[str, Any]:
    """Input text into a field"""
    selector = kwargs.get("input_selector", kwargs.get("selector"))
    text = kwargs.get("input_text", kwargs.get("text", ""))
    clear_first = kwargs.get("clear_first", True)
    
    print(f"Looking for input field: {selector}", file=sys.stderr)
    
    input_field = None
    
    # Try class name ProseMirror
    if not input_field:
        input_field = await tab.find(
            class_name='ProseMirror',
            timeout=5,
            raise_exc=False
        )
    
    # Try ID prompt-textarea
    if not input_field:
        input_field = await tab.find(
            id='prompt-textarea',
            timeout=5,
            raise_exc=False
        )
    
    if not input_field:
        print("Input field not found", file=sys.stderr)
        return {"success": False, "error": "Input field not found"}
    
    print(f"Found element: {input_field}", file=sys.stderr)
    
    await input_field.click()
    await asyncio.sleep(0.5)
    
    if clear_first:
        await ScriptExecutor.execute(tab, """
            const editor = document.querySelector('div.ProseMirror') || 
                         document.getElementById('prompt-textarea');
            if (editor && editor.contentEditable === 'true') {
                editor.focus();
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(editor);
                selection.removeAllRanges();
                selection.addRange(range);
                document.execCommand('delete');
            }
        """)
        await asyncio.sleep(0.2)
    
    print(f"Typing text: {text}", file=sys.stderr)
    await input_field.type_text(text)
    await asyncio.sleep(1)
    
    await ScriptExecutor.execute(tab, """
        const editor = document.querySelector('div.ProseMirror') || 
                     document.getElementById('prompt-textarea');
        if (editor) {
            editor.dispatchEvent(new Event('input', { bubbles: true }));
            editor.dispatchEvent(new Event('change', { bubbles: true }));
        }
    """)
    
    print("Text input successful", file=sys.stderr)
    return {"success": True}


@ActionRegistry.register("click", aliases=["press"])
async def click_button(tab, **kwargs) -> Dict[str, Any]:
    """Click a button or element"""
    selector = kwargs.get("submit_button", kwargs.get("selector"))
    text = kwargs.get("submit_text", kwargs.get("text"))
    
    button = None
    
    if selector:
        for sel in selector.split(','):
            button = await tab.find(
                css_selector=sel.strip(),
                timeout=3,
                raise_exc=False
            )
            if button:
                break
    
    if not button and text:
        button = await tab.find(
            text=text,
            timeout=5,
            raise_exc=False
        )
    
    if not button:
        print("Button not found", file=sys.stderr)
        return {"success": False, "error": "Button not found"}
    
    await button.scroll_into_view()
    await button.wait_until(is_interactable=True, timeout=10)
    await button.click()
    await asyncio.sleep(1.5)
    return {"success": True}


@ActionRegistry.register("wait_response")
async def wait_for_response(tab, **kwargs) -> Dict[str, Any]:
    """Wait for response (especially for ChatGPT)"""
    timeout = kwargs.get("wait_timeout", 60)
    
    print(f"Waiting for response (timeout: {timeout}s)...", file=sys.stderr)
    start_time = time.time()
    seen_stop_button = False
    
    while (time.time() - start_time) < timeout:
        try:
            stop_button_check = await ScriptExecutor.execute(tab, """
                const stopBtn = document.querySelector('[data-testid="stop-button"]');
                if (stopBtn) return 'generating';
                else return 'complete';
            """)
            
            print(f"Button state: {stop_button_check}", file=sys.stderr)
            
            if stop_button_check == 'generating':
                if not seen_stop_button:
                    print("ChatGPT is generating response...", file=sys.stderr)
                    seen_stop_button = True
                await asyncio.sleep(1)
                continue
            
            elif stop_button_check == 'complete':
                if seen_stop_button:
                    print("Response complete!", file=sys.stderr)
                    await asyncio.sleep(2)
                    return {"success": True}
                else:
                    print("Response ready (no generation seen)", file=sys.stderr)
                    return {"success": True}
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
        
        await asyncio.sleep(1)
    
    print("Response wait timeout", file=sys.stderr)
    return {"success": False}


@ActionRegistry.register("download")
async def download_file(tab, **kwargs) -> Dict[str, Any]:
    """Download a file"""
    link_text = kwargs.get("link_text")
    link_selector = kwargs.get("link_selector")
    filename = kwargs.get("filename", f"download_{int(time.time())}.xlsx")
    output_dir = kwargs.get("output_dir", Path.cwd())
    
    download_element = None
    
    if link_selector:
        download_element = await tab.find(css_selector=link_selector, timeout=10, raise_exc=False)
    elif link_text:
        download_element = await tab.find(text=link_text, timeout=10, raise_exc=False)
    
    if not download_element:
        return {"success": False, "error": "Download element not found"}
    
    print("Clicking download...", file=sys.stderr)
    await download_element.click()
    
    download_path = output_dir / filename
    max_wait = 300
    start = time.time()
    
    while time.time() - start < max_wait:
        crdownloads = list(output_dir.glob("*.crdownload"))
        if crdownloads:
            await asyncio.sleep(1)
            continue
        
        excel_files = list(output_dir.glob("*.xlsx")) + list(output_dir.glob("*.xls"))
        if excel_files:
            latest = max(excel_files, key=lambda p: p.stat().st_mtime)
            if time.time() - latest.stat().st_mtime < 5:
                print(f"File saved: {latest}", file=sys.stderr)
                return {"success": True, "download_path": str(latest)}
        
        await asyncio.sleep(1)
    
    return {"success": False, "error": "Download timeout"}


@ActionRegistry.register("extract", aliases=["scrape"])
async def extract_text(tab, **kwargs) -> Dict[str, Any]:
    """Extract text from page"""
    selector = kwargs.get("extract_selector", kwargs.get("selector"))
    save_to = kwargs.get("save_as")
    output_dir = kwargs.get("output_dir", Path.cwd())
    
    print("Finding and clicking the last copy button...", file=sys.stderr)
    
    extracted_text = await ScriptExecutor.execute(tab, """
        const copyButtons = document.querySelectorAll('[data-testid="copy-turn-action-button"]');
        
        if (copyButtons.length > 0) {
            const lastCopyBtn = copyButtons[copyButtons.length - 1];
            lastCopyBtn.click();
            
            let parent = lastCopyBtn.closest('article');
            if (!parent) {
                parent = lastCopyBtn.closest('[data-message-author-role="assistant"]');
            }
            if (!parent) {
                parent = lastCopyBtn.parentElement;
                while (parent && !parent.querySelector('.markdown')) {
                    parent = parent.parentElement;
                }
            }
            
            if (parent) {
                const markdownDiv = parent.querySelector('.markdown');
                if (markdownDiv) {
                    return markdownDiv.innerText || markdownDiv.textContent || '';
                }
                return parent.innerText || parent.textContent || '';
            }
            
            return 'Copy button clicked but could not extract text';
        }
        
        return 'No copy button found';
    """)
    
    if not extracted_text or extracted_text in ['No copy button found', 'Copy button clicked but could not extract text']:
        print("Copy button method failed, trying direct extraction...", file=sys.stderr)
        
        extracted_text = await ScriptExecutor.execute(tab, """
            const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
            if (messages.length > 0) {
                const lastMsg = messages[messages.length - 1];
                const markdownDiv = lastMsg.querySelector('.markdown');
                if (markdownDiv) {
                    return markdownDiv.innerText || markdownDiv.textContent || '';
                }
                return lastMsg.innerText || lastMsg.textContent || '';
            }
            
            const articles = document.querySelectorAll('article');
            if (articles.length > 1) {
                const lastArticle = articles[articles.length - 1];
                const markdownDiv = lastArticle.querySelector('.markdown');
                if (markdownDiv) {
                    return markdownDiv.innerText || '';
                }
                return lastArticle.innerText || '';
            }
            
            return 'Could not extract response';
        """)
    
    if not isinstance(extracted_text, str):
        extracted_text = ""
    
    if extracted_text and extracted_text not in ['Could not extract response', 'Copy button clicked but could not extract text']:
        if save_to:
            save_path = output_dir / save_to
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            print(f"Text saved to: {save_path}", file=sys.stderr)
        
        print("\n--- EXTRACTED TEXT ---", file=sys.stderr)
        print(extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text, file=sys.stderr)
        print("--- END EXTRACTED TEXT ---\n", file=sys.stderr)
    else:
        print(f"Extraction failed: {extracted_text}", file=sys.stderr)
        extracted_text = ""
    
    return {
        "success": True,
        "extracted_text": extracted_text[:1000] if extracted_text else "",
        "text_length": len(extracted_text) if extracted_text else 0
    }