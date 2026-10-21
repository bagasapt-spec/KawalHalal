"""FastAPI app KawalHalal."""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import KawalHalalAgent
from tools import cek_sertifikat_bpjph

app = FastAPI(title="KawalHalal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = KawalHalalAgent()


class ChatRequest(BaseModel):
    message: str


class VerifyRequest(BaseModel):
    nomor_sertifikat: str


@app.get("/")
def health():
    return {"status": "ok", "service": "KawalHalal", "mode": agent.mode}


@app.post("/api/chat")
def chat(req: ChatRequest):
    return agent.proses_pertanyaan(req.message)


@app.post("/api/verify")
def verify(req: VerifyRequest):
    return cek_sertifikat_bpjph(req.nomor_sertifikat)
