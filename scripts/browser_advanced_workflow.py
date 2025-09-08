# scripts/browser_advanced_workflow.py
"""
Advanced browser workflow automation - Refactored version
Maintains backward compatibility with existing YAML files
"""
import argparse
import json
import sys
import asyncio
from pathlib import Path
from browser.workflow.processor import WorkflowProcessor

def parse_bool(x: str) -> bool:
    """Convert string to boolean."""
    return str(x).lower() in ("1", "true", "yes", "on")

async def process_advanced_workflow(args):
    """Process advanced workflow with multiple interaction types."""
    workflow = json.loads(args.workflow) if args.workflow else []
    output_dir = Path(args.output_dir).absolute()
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = WorkflowProcessor(
        output_dir=output_dir,
        headless=parse_bool(args.headless)
    )

    return await processor.execute(workflow)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True, help="JSON array of workflow steps")
    parser.add_argument("--output-dir", required=True, help="Directory for outputs")
    parser.add_argument("--headless", default="false")

    args = parser.parse_args()

    try:
        result = await process_advanced_workflow(args)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("success") else 1
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))