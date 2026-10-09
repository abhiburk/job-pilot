from fastapi import FastAPI

app = FastAPI(
    title="JobPilot",
    description="Agentic AI job search and application assistant",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}