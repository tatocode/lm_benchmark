def main() -> None:
    import os

    import uvicorn

    host = os.environ.get("LMB_HOST", "127.0.0.1")
    port = int(os.environ.get("LMB_PORT", "8000"))
    uvicorn.run("llm_benchmark.server:app", host=host, port=port)
