from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("OSIRIS_HOST", "0.0.0.0"),
        port=int(os.getenv("OSIRIS_PORT", "8787")),
        reload=False,
    )
	
