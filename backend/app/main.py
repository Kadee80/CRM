from fastapi import FastAPI

from app.api.routes import health, notion_sync, prospects, scrape


app = FastAPI(title="CRM Scrape Notion API", version="0.1.0")

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(prospects.router, prefix="/prospects", tags=["prospects"])
app.include_router(scrape.router, prefix="/scrape", tags=["scrape"])
app.include_router(notion_sync.router, prefix="/notion", tags=["notion"])

