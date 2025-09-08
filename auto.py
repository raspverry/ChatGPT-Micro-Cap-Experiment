#!/usr/bin/env python3
"""
ChatGPT Micro-Cap Trading Automation
브라우저 자동화를 통한 완전 자동 트레이딩
"""

import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
import sys
sys.path.append('..')  # trading_script.py 접근용

from trading_script import (
    process_portfolio, 
    daily_results,
    load_latest_portfolio_state,
    log_manual_buy,
    log_manual_sell
)

class TradingAutomation:
    """ChatGPT를 통한 자동 트레이딩 시스템"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path.cwd() / "trading_output"
        self.output_dir.mkdir(exist_ok=True)
        
    def create_workflow(self, trading_prompt: str) -> list:
        """ChatGPT 자동화 워크플로우 생성"""
        return [
            {
                "name": "Navigate to ChatGPT",
                "type": "navigate",
                "url": "https://chatgpt.com",
                "wait_login": True,
                "login_timeout": 300
            },
            {
                "name": "Input Trading Prompt",
                "type": "input",
                "input_selector": "#prompt-textarea,.ProseMirror",
                "input_text": trading_prompt,
                "clear_first": True,
                "submit_button": '[data-testid="send-button"]',
                "submit_text": "Send",
                "wait_for_selector": '[data-testid="stop-button"]',
                "wait_timeout": 60
            },
            {
                "name": "Extract Response",
                "type": "extract",
                "extract_selector": '[data-message-author-role="assistant"]',
                "save_as": f"chatgpt_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            }
        ]
    
    async def run_browser_automation(self, workflow: list) -> dict:
        """브라우저 자동화 스크립트 실행"""
        workflow_json = json.dumps(workflow)
        
        cmd = [
            "python3", "scripts/browser_advanced_workflow.py",
            "--workflow", workflow_json,
            "--output-dir", str(self.output_dir),
            "--headless", "false"  # ChatGPT 로그인시 false 추천
        ]
        
        print("브라우저 자동화 시작...")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if stderr:
            print(f"자동화 로그: {stderr.decode()}", file=sys.stderr)
        
        try:
            result = json.loads(stdout.decode())
            return result
        except json.JSONDecodeError:
            return {"success": False, "error": "Failed to parse result"}
    
    def parse_chatgpt_response(self, response_file: Path) -> dict:
        """ChatGPT 응답 파싱"""
        if not response_file.exists():
            return {"error": "Response file not found"}
        
        with open(response_file, 'r', encoding='utf-8') as f:
            response_text = f.read()
        
        # 간단한 파싱 로직 (실제로는 더 정교하게)
        trades = []
        
        if "매수" in response_text or "buy" in response_text.lower():
            # 매수 신호 파싱
            lines = response_text.split('\n')
            for line in lines:
                if any(word in line.lower() for word in ['buy', '매수', 'purchase']):
                    # 티커, 수량, 가격 추출 (정규표현식 사용 권장)
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isupper() and len(part) <= 5:  # 티커로 추정
                            trades.append({
                                "action": "buy",
                                "ticker": part,
                                "shares": 10,  # 기본값
                                "price": 0,  # 시장가
                                "stop_loss": 0
                            })
                            break
        
        if "매도" in response_text or "sell" in response_text.lower():
            # 매도 신호 파싱
            lines = response_text.split('\n')
            for line in lines:
                if any(word in line.lower() for word in ['sell', '매도']):
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isupper() and len(part) <= 5:
                            trades.append({
                                "action": "sell",
                                "ticker": part,
                                "shares": 5,
                                "price": 0
                            })
                            break
        
        return {"trades": trades}
    
    def execute_trades(self, trades: list, portfolio_df, cash: float):
        """실제 거래 실행 (trading_script.py 함수 사용)"""
        for trade in trades:
            if trade["action"] == "buy":
                print(f"매수 실행: {trade['ticker']} x {trade['shares']}")
                cash, portfolio_df = log_manual_buy(
                    buy_price=trade.get("price", 0),
                    shares=trade["shares"],
                    ticker=trade["ticker"],
                    stoploss=trade.get("stop_loss", 0),
                    cash=cash,
                    chatgpt_portfolio=portfolio_df,
                    interactive=False  # 자동 실행
                )
                
            elif trade["action"] == "sell":
                print(f"매도 실행: {trade['ticker']} x {trade['shares']}")
                cash, portfolio_df = log_manual_sell(
                    sell_price=trade.get("price", 0),
                    shares_sold=trade["shares"],
                    ticker=trade["ticker"],
                    cash=cash,
                    chatgpt_portfolio=portfolio_df,
                    reason="AI recommendation",
                    interactive=False
                )
        
        return portfolio_df, cash
    
    async def run_daily_trading(self):
        """일일 트레이딩 자동 실행"""
        print("=" * 60)
        print(f"자동 트레이딩 시작: {datetime.now()}")
        print("=" * 60)
        
        # 1. 현재 포트폴리오 로드
        portfolio_df, cash = load_latest_portfolio_state(
            "Start Your Own/chatgpt_portfolio_update.csv"
        )
        
        # 2. 일일 결과 생성
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = StringIO()
        
        daily_results(portfolio_df, cash)
        trading_prompt = buffer.getvalue()
        
        sys.stdout = old_stdout
        
        print("트레이딩 프롬프트 생성 완료")
        
        # 3. ChatGPT 자동화 실행
        workflow = self.create_workflow(trading_prompt)
        result = await self.run_browser_automation(workflow)
        
        if not result.get("success"):
            print(f"자동화 실패: {result.get('error')}")
            return False
        
        print("ChatGPT 응답 받기 성공")
        
        # 4. 응답 파싱
        response_files = list(self.output_dir.glob("chatgpt_response_*.txt"))
        if not response_files:
            print("응답 파일을 찾을 수 없음")
            return False
        
        latest_response = max(response_files, key=lambda p: p.stat().st_mtime)
        parsed = self.parse_chatgpt_response(latest_response)
        
        if not parsed.get("trades"):
            print("거래 신호 없음 - 홀딩")
            return True
        
        # 5. 거래 실행
        print(f"거래 신호 발견: {len(parsed['trades'])}개")
        portfolio_df, cash = self.execute_trades(
            parsed["trades"], 
            portfolio_df, 
            cash
        )
        
        # 6. 결과 저장
        process_portfolio(portfolio_df, cash, interactive=False)
        
        print("=" * 60)
        print("자동 트레이딩 완료!")
        print(f"최종 현금: ${cash:.2f}")
        print("=" * 60)
        
        return True


# 스케줄러를 위한 메인 함수
async def main():
    """매일 실행될 메인 함수"""
    automation = TradingAutomation()
    
    # 일본/호주 시간대에 맞춰 실행
    # 아침 6-7시 (미국 장 마감 후)
    success = await automation.run_daily_trading()
    
    if success:
        print("오늘 트레이딩 완료")
        
        # Stake 앱 알림 (선택사항)
        # send_notification("트레이딩 신호를 Stake에서 실행하세요!")
    else:
        print("트레이딩 실패 - 수동 확인 필요")


# Cron 또는 스케줄러용 엔트리
if __name__ == "__main__":
    asyncio.run(main())