#Faut installer les dependances en faisant : pip install fastapi uvicorn
#Et ensuite pour lancer le back faut faire ca : OPENAQ_API_KEY=***REMOVED*** uvicorn backend:app --reload

from fastapi import FastAPI, HTTPException
from eco_city import eco_city
import os

app = FastAPI(title="Eco City Backend")

if not os.getenv("OPENAQ_API_KEY"):
    raise RuntimeError("OPENAQ_API_KEY is missing")

@app.get("/eco")
def get_eco(city: str):
    try:
        return eco_city(city)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
