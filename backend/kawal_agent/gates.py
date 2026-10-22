"""Gerbang konfirmasi manusia (human gate), ditegakkan oleh kode, bukan oleh prompt.

Alur: agen memanggil minta_konfirmasi (tool) -> tulis pertanyaan ke pengguna -> giliran berakhir.
Di awal giliran berikutnya, callback membaca balasan ASLI pengguna dan memindahkan aksi ke
'disetujui' hanya bila balasannya jelas setuju. Model tidak bisa menyetujui untuk pengguna.
"""
import re
from typing import Any, Optional

_AFIRMATIF = re.compile(
    r"^\s*(ya|iya|iyaa|iyap|y|yes|yup|ok|oke|okey|okay|sip|setuju|boleh|lanjut|lanjutkan|gas|silakan|silahkan|"
    r"benar|betul|sesuai|masukkan|masukin|kirim)\b",
    re.IGNORECASE,
)
_NEGATIF_AWAL = re.compile(r"^\s*(tidak|nggak|ngga|gak|ga|enggak|engga|jangan|batal|stop|no|nope)\b", re.IGNORECASE)
_RAGU = re.compile(r"\b(tapi|tetapi|namun|ganti|ubah|revisi|salah|belum|tunggu|nanti|bukan|kecuali|dulu)\b", re.IGNORECASE)

AKSI_DIKENAL = {
    "masukkan_bahan_bermasalah",
    "kirim_pengajuan",
    "pernyataan_kebijakan_halal",
    "pernyataan_pengertian_halal_haram",
    "pernyataan_praktik_sjph",
    "pernyataan_bebas_babi",
}


def teks_pengguna(content: Any) -> str:
    """Ambil teks dari types.Content pesan pengguna."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = getattr(content, "parts", None) or []
    return " ".join(getattr(p, "text", "") or "" for p in parts).strip()


def baca_jawaban(teks: str) -> Optional[str]:
    """Kembalikan 'ya', 'tidak', atau None bila ambigu. Sengaja konservatif: ragu dianggap belum setuju."""
    t = (teks or "").strip()
    if not t:
        return None
    if _NEGATIF_AWAL.search(t):
        return "tidak"
    if _AFIRMATIF.search(t) and not _RAGU.search(t) and len(t.split()) <= 8:
        return "ya"
    return None


def proses_giliran_baru(callback_context) -> None:
    """before_agent_callback: terapkan balasan pengguna terhadap konfirmasi yang tertunda."""
    state = callback_context.state
    menunggu = state.get("menunggu")
    if not menunggu:
        return None
    jawab = baca_jawaban(teks_pengguna(callback_context.user_content))
    if jawab == "ya":
        state["disetujui"] = sorted(set(state.get("disetujui", [])) | {menunggu["id"]})
        state["fp_disetujui"] = {**(state.get("fp_disetujui") or {}), menunggu["id"]: menunggu.get("fp", "")}
        state["keputusan_terakhir"] = {"aksi": menunggu["id"], "keputusan": "disetujui"}
        state["menunggu"] = None
    elif jawab == "tidak":
        state["keputusan_terakhir"] = {"aksi": menunggu["id"], "keputusan": "ditolak"}
        state["menunggu"] = None
    return None


def sudah_disetujui(state, aksi_id: str, fp: Optional[str] = None) -> bool:
    """Persetujuan berlaku bila ada, dan (bila fp diberikan) data saat disetujui sama dengan data sekarang."""
    if aksi_id not in (state.get("disetujui") or []):
        return False
    return fp is None or (state.get("fp_disetujui") or {}).get(aksi_id) == fp


def minta(state, aksi_id: str, ringkasan: str, invocation_id: str, fp: str = "") -> dict:
    if aksi_id not in AKSI_DIKENAL:
        return {"status": "galat", "pesan": f"aksi_id harus salah satu dari: {', '.join(sorted(AKSI_DIKENAL))}."}
    state["menunggu"] = {"id": aksi_id, "ringkasan": ringkasan, "invocation": invocation_id, "fp": fp}
    return {
        "status": "menunggu_pengguna",
        "instruksi": (
            "Tulis ringkasan ini ke pengguna dengan bahasa sederhana, tanyakan apakah mau dilanjutkan "
            "(balas YA atau TIDAK), lalu AKHIRI giliran ini. Jangan memanggil tool tulis lain sebelum pengguna menjawab."
        ),
        "ringkasan": ringkasan,
    }


def cabut(state, aksi_id: str) -> None:
    """Pakai-sekali: hapus persetujuan setelah dipakai supaya tidak berlaku untuk hal lain."""
    state["disetujui"] = [a for a in (state.get("disetujui") or []) if a != aksi_id]
    state["fp_disetujui"] = {k: v for k, v in (state.get("fp_disetujui") or {}).items() if k != aksi_id}
