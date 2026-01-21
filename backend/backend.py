#Faut installer les dependances en faisant : pip install fastapi uvicorn
#Et ensuite pour lancer le back faut faire ca : OPENAQ_API_KEY=***REMOVED*** uvicorn backend:app --reload

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from eco_city import eco_city
import os

app = FastAPI(title="Eco City Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if not os.getenv("OPENAQ_API_KEY"):
    raise RuntimeError("OPENAQ_API_KEY is missing")

@app.get("/eco")
def get_eco(city: str):
    try:
        return eco_city(city)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
