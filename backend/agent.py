import os
import re
from typing import Dict, Any
from dotenv import load_dotenv
from tools import cek_sertifikat_bpjph, analisis_titik_kritis

load_dotenv()

class KawalHalalAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.use_real_api = bool(self.api_key and self.api_key.strip())
        self.model_name = "gemini-3.8-flash"
        
        if self.use_real_api:
            try:
                from google import genai
                from google.genai import types
                self.client = genai.Client(api_key=self.api_key)
                self.types = types
            except Exception as e:
                print(f"[Agent Init Error] {e}")
                self.client = None
                self.use_real_api = False
        else:
            self.client = None

    def proses_pertanyaan(self, prompt: str) -> Dict[str, Any]:
        # 1. LIVE GEMINI MODE (Menggunakan Chat Session + AFC sesuai rekomendasi SDK)
        if self.use_real_api and self.client:
            try:
                chat = self.client.chats.create(
                    model=self.model_name,
                    config=self.types.GenerateContentConfig(
                        system_instruction=(
                            "Kamu adalah asisten AI resmi KawalHalal. "
                            "Gunakan tool cek_sertifikat_bpjph untuk memverifikasi nomor sertifikat, "
                            "dan tool analisis_titik_kritis untuk memeriksa kehalalan bahan atau kode E-number. "
                            "Jawablah dengan sopan, berbasis fakta fiqih dan regulasi halal Indonesia."
                        ),
                        tools=[cek_sertifikat_bpjph, analisis_titik_kritis],
                        temperature=0.2,
                    )
                )
                
                res = chat.send_message(prompt)
                
                return {
                    "mode": "live",
                    "intent": "ai_agent_reasoning",
                    "jawaban": res.text,
                    "data": None
                }
            except Exception as e:
                print(f"[Gemini Execution Error]: {e}")
                hasil_mock = self._mock_fallback(prompt)
                hasil_mock["catatan"] = f"Gemini gagal ({type(e).__name__}); memakai fallback mock."
                return hasil_mock

        # 2. MOCK FALLBACK MODE
        return self._mock_fallback(prompt)

    def _mock_fallback(self, prompt: str) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        
        # Pola cek nomor sertifikat (misal ID3111...)
        pola_id = re.search(r'\b(id\d{10,15})\b', prompt_lower)
        if pola_id or "sertifikat" in prompt_lower:
            nomor = pola_id.group(1).upper() if pola_id else "ID3111000012345"
            hasil = cek_sertifikat_bpjph(nomor)
            return {
                "mode": "mock",
                "intent": "cek_sertifikat",
                "jawaban": hasil.get("pesan", f"Data sertifikat {nomor} ditemukan."),
                "data": hasil.get("data")
            }
        
        # Pola analisis bahan
        if any(k in prompt_lower for k in ["e471", "e120", "gelatin", "alkohol", "bahan", "kritis"]):
            hasil = analisis_titik_kritis(["e471", "gelatin"])
            return {
                "mode": "mock",
                "intent": "analisis_bahan",
                "jawaban": "Terdapat titik kritis/syubhat pada bahan yang dicek.",
                "data": hasil
            }

        return {
            "mode": "mock",
            "intent": "tidak_dikenali",
            "jawaban": "Kirim nomor sertifikat halal (mis. ID3111000012345) atau daftar bahan untuk diperiksa.",
            "data": None
        }