import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

import asyncio
from sqlalchemy import select
from app.core.database import async_session_maker, init_db
from app.models.stock import StockMaster, StockPriceHistory
from app.workers.stock_ingestion import calculate_institutional_ratings, get_sector_averages, parse_briefing_sections

async def backfill():
    print("Initializing database tables and running column migrations...")
    await init_db()
    
    print("Starting Hardened Ratings Engine v2 backfill...")
    async with async_session_maker() as session:
        # Fetch all stocks
        res = await session.execute(select(StockMaster))
        stocks = res.scalars().all()
        print(f"Found {len(stocks)} stocks to backfill.")
        
        valid_stocks = []
        
        for stock in stocks:
            if stock.sector == "Unknown" or stock.sector == "Invalid":
                print(f"Skipping skeleton stock: {stock.symbol}")
                continue
                
            # Fetch price history closes
            prices_res = await session.execute(
                select(StockPriceHistory.close)
                .where(StockPriceHistory.symbol == stock.symbol)
                .order_by(StockPriceHistory.date.asc())
            )
            prices_list = [row[0] for row in prices_res.all()]
            if not prices_list:
                prices_list = [100.0] * 50
                
            # Sector averages
            sector_avgs = await get_sector_averages(stock.sector, session)
            
            # Map attributes
            stock_meta = {
                "symbol": stock.symbol,
                "company_name": stock.company_name,
                "roe": stock.roe,
                "debt_equity": stock.debt_equity,
                "pe_ratio": stock.pe_ratio,
                "pb_ratio": stock.pb_ratio,
                "target_beta": stock.beta or 1.0,
                "cagr_1y": stock.cagr_1y,
                "cagr_3y": stock.cagr_3y,
                "cagr_5y": stock.cagr_5y
            }
            
            # Compute ratings
            ratings = calculate_institutional_ratings(stock_meta, prices_list, sector_avgs)
            
            # Update database columns
            stock.alpha_score = ratings["final_score"]
            stock.fundamental_score = ratings["fundamental_score"]
            stock.quality_score = ratings["quality_score"]
            stock.valuation_score = ratings["valuation_score"]
            stock.technical_score = ratings["technical_score"]
            stock.risk_score = ratings["risk_score"]
            stock.sector_relative_score = ratings["sector_relative_score"]
            stock.event_score = ratings["event_score"]
            stock.confidence_score = ratings["confidence_score"]
            stock.investor_verdict = ratings["investor_verdict"]
            stock.trader_verdict = ratings["trader_verdict"]
            stock.trend_structure = ratings["trend_structure"]
            
            # Parse AI briefing if present
            if stock.ai_summary and stock.ai_summary != "Generating Equity Intelligence Briefing in the background...":
                bull, bear, rationale = parse_briefing_sections(stock.ai_summary)
                stock.bull_case = bull
                stock.bear_case = bear
                stock.verdict_rationale = rationale
                
            valid_stocks.append(stock)
            print(f"- Processed {stock.symbol}: Score={stock.alpha_score}, Inv={stock.investor_verdict}, Tra={stock.trader_verdict}, Trend={stock.trend_structure}")
            
        await session.commit()
        print("\nDatabase commit successful!")
        
        # Calculate new distributions
        scores = [s.alpha_score for s in valid_stocks]
        avg_score = sum(scores) / len(scores) if scores else 0
        highest = max(scores) if scores else 0
        lowest = min(scores) if scores else 0
        
        strong_buy = 0
        buy = 0
        hold = 0
        reduce_v = 0
        avoid = 0
        
        for s in valid_stocks:
            verdict = s.investor_verdict
            if verdict == "STRONG BUY": strong_buy += 1
            elif verdict == "BUY": buy += 1
            elif verdict == "HOLD": hold += 1
            elif verdict == "REDUCE": reduce_v += 1
            else: avoid += 1
            
        total = len(valid_stocks)
        print("\n=========================================================")
        print("NEW RATINGS v2 DISTRIBUTION ANALYSIS")
        print("=========================================================")
        print(f"Total valid stocks: {total}")
        print(f"Average final score: {avg_score:.2f}")
        print(f"Highest score: {highest:.2f}")
        print(f"Lowest score: {lowest:.2f}")
        print(f"Distribution:")
        print(f"- STRONG BUY: {strong_buy} ({strong_buy/total*100:.1f}%) [Target: 5-10%]")
        print(f"- BUY:        {buy} ({buy/total*100:.1f}%) [Target: 15-20%]")
        print(f"- HOLD:       {hold} ({hold/total*100:.1f}%) [Target: 40-50%]")
        print(f"- REDUCE:     {reduce_v} ({reduce_v/total*100:.1f}%) [Target: 15-20%]")
        print(f"- AVOID:      {avoid} ({avoid/total*100:.1f}%) [Target: 10-15%]")

if __name__ == "__main__":
    asyncio.run(backfill())
