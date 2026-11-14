from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from novelty_engine import fetch_novel_analogs
from llm_brain import generate_mission_brief

app = FastAPI(
    title="Project Terra-Incognita API",
    description=(
        "Backend API for systematic discovery of unexplored planetary"
        " analogs."
    ),
    version="1.0.0",
)

# Enable CORS for Streamlit frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
