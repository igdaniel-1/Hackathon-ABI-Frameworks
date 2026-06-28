import uvicorn


if __name__ == "__main__":
    uvicorn.run("abi_pipeline.api:app", host="0.0.0.0", port=8000, reload=True)
