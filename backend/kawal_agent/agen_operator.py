"""Agen Operator KawalHalal (ADK): menjalankan rencana pengisian formulir web SIHALAL lewat browser.

Agen ini terisolasi dari sesi Kala dan TIDAK menyentuh atau mengimpor sihalal_mock.
Seluruh pembacaan dan pengisian dilakukan melalui antarmuka layar (_Layar) dan rencana
deterministik di operator_ui.
"""
from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import contextvars
import json
import logging
import os
import queue
import uuid
from typing import Any, Callable, Optional

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from . import operator_ui
from .agent import kirim_ke_loop_agen

logger = logging.getLogger("kawalhalal.agen_operator")

APP_NAME = "kawalhalal_operator"
MODEL_RINGAN = os.getenv("GEMINI_MODEL_RINGAN") or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
BATAS_ULANG_TUGAS = 2  # maksimal 1 kali ulang bila gagal (total 2 percobaan per langkah)

INSTRUKSI_OPERATOR_AGEN = """\
Kamu adalah agen operator browser KawalHalal yang bertugas mengisi formulir web SIHALAL sesuai rencana kerja.

ATURAN WAJIB:
1. Panggil lihat_rencana terlebih dahulu untuk mengambil daftar langkah tugas formulir yang harus dikerjakan.
2. Selesaikan seluruh tugas secara berurutan sesuai nomor di rencana dengan memanggil kerjakan_tugas(nomor) satu per satu dari nomor pertama hingga terakhir.
3. Bila suatu langkah gagal (status "gagal"), kamu boleh memeriksa halaman dengan lihat_layar(tab) dan mengulangi kerjakan_tugas(nomor) untuk langkah tersebut MAKSIMAL SATU KALI. Bila masih gagal setelah diulang satu kali, lanjutkan ke langkah berikutnya.
4. DILARANG mengarang data, mengubah isi tugas, atau melakukan aksi di luar rencana dari lihat_rencana.
5. Setelah semua langkah dalam rencana selesai dicoba, sampaikan ringkasan singkat hasil pengerjaan.
"""


class _KonteksOperator:
    """Konteks eksekusi per sesi operator agar tool terhubung ke state dan layar tanpa variabel global bersama."""

    def __init__(
        self,
        state: dict,
        layar: Any = None,
        eksekutor: Optional[Callable[[Callable[[], Any]], Any]] = None,
    ):
        self.state = state
        self.layar = layar
        self.eksekutor = eksekutor
        self.rencana_terakhir: Optional[list[dict]] = None
        self.selesai_nomor: set[int] = set()
        self.selesai_tugas: list[dict] = []
        self.gagal_nomor: dict[int, dict] = {}
        self.percobaan_per_nomor: dict[int, int] = {}
        self.riwayat_tugas: list[dict] = []

    def panggil_layar(self, fn: Callable[[], Any]) -> Any:
        if self.eksekutor is not None:
            return self.eksekutor(fn)
        return fn()

    def ambil_live(self) -> Any:
        if self.layar is not None and hasattr(self.layar, "baca") and callable(self.layar.baca):
            return self.panggil_layar(self.layar.baca)
        return True


_konteks_aktif: contextvars.ContextVar[Optional[_KonteksOperator]] = contextvars.ContextVar(
    "konteks_operator_aktif", default=None
)
_model_override: Any = None


def _ambil_konteks() -> _KonteksOperator:
    ctx = _konteks_aktif.get()
    if ctx is None:
        raise RuntimeError("Konteks agen operator belum diinisialisasi.")
    return ctx


def pasang_konteks(
    state: dict,
    layar: Any = None,
    eksekutor: Optional[Callable[[Callable[[], Any]], Any]] = None,
) -> _KonteksOperator:
    """Pasang konteks operator untuk pengujian langsung tool tanpa Runner."""
    ctx = _KonteksOperator(state=state, layar=layar, eksekutor=eksekutor)
    _konteks_aktif.set(ctx)
    return ctx


# ------------------------------------------------------------------
# Tool Pembungkus Agen Operator (tanpa akses sihalal_mock)
# ------------------------------------------------------------------
def lihat_rencana() -> dict:
    """Ambil daftar langkah tugas pengisian formulir SIHALAL yang perlu dikerjakan.

    Returns:
        dict berisi status, total tugas, dan daftar tugas bernomor urut (mulai dari 1).
    """
    ctx = _ambil_konteks()
    live = ctx.ambil_live()
    mentah = operator_ui.rencana(ctx.state, live=live)
    masih = [t for t in mentah if t not in ctx.selesai_tugas]
    ctx.rencana_terakhir = list(masih)
    ctx.selesai_nomor.clear()
    ctx.gagal_nomor.clear()
    ctx.percobaan_per_nomor.clear()
    tugas = [{"nomor": i, **t} for i, t in enumerate(masih, start=1)]
    return {
        "status": "ok",
        "total": len(tugas),
        "tugas": tugas,
    }


def kerjakan_tugas(nomor: int) -> dict:
    """Jalankan langkah tugas formulir ke-n sesuai daftar dari lihat_rencana menggunakan browser.

    Args:
        nomor: Nomor urut langkah tugas (mulai dari 1) sebagaimana tercantum pada lihat_rencana.

    Returns:
        dict berisi status ('ok' atau 'gagal'), nomor, aksi, detail tugas, dan pesan/galat bila ada.
    """
    ctx = _ambil_konteks()
    try:
        idx = int(nomor)
    except (TypeError, ValueError):
        return {"status": "galat", "nomor": nomor, "pesan": "Nomor tugas harus berupa angka bulat."}

    if ctx.rencana_terakhir is None:
        live = ctx.ambil_live()
        ctx.rencana_terakhir = [t for t in operator_ui.rencana(ctx.state, live=live) if t not in ctx.selesai_tugas]

    if idx < 1 or idx > len(ctx.rencana_terakhir):
        return {
            "status": "galat",
            "nomor": idx,
            "pesan": f"Nomor tugas {idx} di luar jangkauan rencana (1..{len(ctx.rencana_terakhir)}).",
        }

    tugas = ctx.rencana_terakhir[idx - 1]

    # Jaga idempotensi: jangan jalankan ulang langkah yang sudah berhasil di sesi ini atau sudah ada di layar
    if idx in ctx.selesai_nomor or tugas in ctx.selesai_tugas:
        return {
            "status": "ok",
            "nomor": idx,
            "aksi": tugas["aksi"],
            "tugas": tugas,
            "lewati": True,
            "pesan": "Tugas sudah selesai dikerjakan sebelumnya (idempoten).",
        }

    live_sekarang = ctx.ambil_live()
    if isinstance(live_sekarang, dict):
        masih_perlu = operator_ui.rencana(ctx.state, live=live_sekarang)
        if tugas not in masih_perlu:
            ctx.selesai_nomor.add(idx)
            ctx.selesai_tugas.append(tugas)
            ctx.gagal_nomor.pop(idx, None)
            return {
                "status": "ok",
                "nomor": idx,
                "aksi": tugas["aksi"],
                "tugas": tugas,
                "lewati": True,
                "pesan": "Isian untuk tugas ini sudah ada di layar SIHALAL (idempoten).",
            }

    percobaan = ctx.percobaan_per_nomor.get(idx, 0)
    if percobaan >= BATAS_ULANG_TUGAS:
        return {
            "status": "gagal",
            "nomor": idx,
            "aksi": tugas["aksi"],
            "tugas": tugas,
            "batas_ulang": True,
            "pesan": "Batas pengulangan tercapai (maksimal 1 kali ulang). Lanjutkan ke tugas berikutnya.",
        }

    ctx.percobaan_per_nomor[idx] = percobaan + 1

    def _lakukan():
        if ctx.layar is None or not hasattr(ctx.layar, "lakukan"):
            raise RuntimeError("Runner browser (_Layar) tidak tersedia.")
        try:
            ctx.layar.lakukan(tugas)
            return None
        except Exception as e:
            ringkas = str(e).splitlines()[0][:120] if str(e) else type(e).__name__
            if hasattr(ctx.layar, "catat") and callable(ctx.layar.catat):
                ctx.layar.catat(f"Gagal pada {tugas['aksi']}: {ringkas}")
            if hasattr(ctx.layar, "tab"):
                ctx.layar.tab = None
            if getattr(ctx.layar, "pg", None) is not None:
                try:
                    ctx.layar.pg.keyboard.press("Escape")
                except Exception:
                    pass
            return ringkas

    galat = ctx.panggil_layar(_lakukan)
    if galat is None:
        ctx.selesai_nomor.add(idx)
        ctx.selesai_tugas.append(tugas)
        ctx.gagal_nomor.pop(idx, None)
        ctx.riwayat_tugas.append({"nomor": idx, "aksi": tugas["aksi"], "status": "ok", "percobaan": percobaan + 1})
        return {
            "status": "ok",
            "nomor": idx,
            "aksi": tugas["aksi"],
            "tugas": tugas,
            "percobaan": percobaan + 1,
        }

    ctx.gagal_nomor[idx] = tugas
    ctx.riwayat_tugas.append(
        {"nomor": idx, "aksi": tugas["aksi"], "status": "gagal", "galat": galat, "percobaan": percobaan + 1}
    )
    return {
        "status": "gagal",
        "nomor": idx,
        "aksi": tugas["aksi"],
        "tugas": tugas,
        "galat": galat,
        "percobaan": percobaan + 1,
    }


def lihat_layar(tab: str) -> dict:
    """Baca teks atau status elemen pada halaman tab aktif di browser SIHALAL.

    Args:
        tab: Nama tab halaman yang ingin dilihat (mis. 'bahan', 'produk', 'komitmen', 'proses', 'data').

    Returns:
        dict berisi status, nama tab, dan cuplikan teks isi layar.
    """
    ctx = _ambil_konteks()
    nama_tab = (tab or "").strip().lower() or getattr(ctx.layar, "tab", None) or "bahan"

    def _baca_teks() -> str:
        if ctx.layar is None:
            return ""
        if hasattr(ctx.layar, "lihat") and callable(ctx.layar.lihat):
            return str(ctx.layar.lihat(nama_tab))
        if getattr(ctx.layar, "pg", None) is not None:
            if nama_tab and hasattr(ctx.layar, "buka"):
                ctx.layar.buka(nama_tab)
            return str(ctx.layar.pg.locator("body").inner_text()[:4000])
        if hasattr(ctx.layar, "baca") and callable(ctx.layar.baca):
            data = ctx.layar.baca()
            if isinstance(data, dict):
                bagian = data.get(nama_tab, data)
                return json.dumps(bagian, ensure_ascii=False)[:4000]
        return ""

    teks_layar = ctx.panggil_layar(_baca_teks)
    return {
        "status": "ok",
        "tab": nama_tab,
        "teks": teks_layar,
    }


SEMUA_TOOL_OPERATOR = [lihat_rencana, kerjakan_tugas, lihat_layar]


def model_operator():
    """Ambil model untuk agen operator: override tes -> GEMINI_MODEL_RINGAN -> GEMINI_MODEL."""
    if _model_override is not None:
        return _model_override
    return os.getenv("GEMINI_MODEL_RINGAN") or os.getenv("GEMINI_MODEL") or MODEL_RINGAN


def bangun_agen(model=None) -> LlmAgent:
    """Bangun LlmAgent bernama 'operator' dengan model ringan dan tool pembungkus."""
    return LlmAgent(
        name="operator",
        model=model if model is not None else model_operator(),
        description="Agen operator browser yang mengisi formulir web SIHALAL sesuai rencana kerja.",
        instruction=INSTRUKSI_OPERATOR_AGEN,
        tools=SEMUA_TOOL_OPERATOR,
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )


operator = bangun_agen()
root_agent = operator


def ganti_model(model) -> None:
    """Untuk pengujian: pasang model pengganti (mis. LLMTerskrip) pada agen operator."""
    global _model_override, operator, root_agent
    _model_override = model
    operator = bangun_agen(model)
    root_agent = operator


async def jalankan(
    state: dict,
    layar: Any,
    pid: str = "default",
    eksekutor: Optional[Callable[[Callable[[], Any]], Any]] = None,
    model: Any = None,
) -> dict:
    """Jalankan agen operator pada Runner dan InMemorySessionService terisolasi untuk satu pekerjaan."""
    konteks = _KonteksOperator(state=state, layar=layar, eksekutor=eksekutor)
    token = _konteks_aktif.set(konteks)
    try:
        agen = bangun_agen(model=model)
        sessions = InMemorySessionService()
        runner = Runner(agent=agen, app_name=APP_NAME, session_service=sessions)
        user_id = f"operator-{pid}"
        session_id = f"sesi-op-{pid}-{uuid.uuid4().hex[:8]}"
        await sessions.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id, state={})
        pesan = types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=(
                        f"Kerjakan pengisian formulir SIHALAL untuk pengajuan {pid}. "
                        "Panggil lihat_rencana lalu jalankan kerjakan_tugas secara berurutan sampai tuntas."
                    )
                )
            ],
        )
        alat: list[str] = []
        balasan: list[str] = []
        async for e in runner.run_async(user_id=user_id, session_id=session_id, new_message=pesan):
            if e.content and e.content.parts:
                for p in e.content.parts:
                    if getattr(p, "function_call", None):
                        alat.append(p.function_call.name)
            if e.is_final_response() and e.content and e.content.parts:
                balasan.append("".join(p.text or "" for p in e.content.parts if getattr(p, "text", None)))

        if konteks.rencana_terakhir is not None:
            belum_selesai = [
                t for i, t in enumerate(konteks.rencana_terakhir, start=1) if i not in konteks.selesai_nomor
            ]
        else:
            live_akhir = konteks.ambil_live()
            belum_selesai = [
                t for t in operator_ui.rencana(state, live=live_akhir) if t not in konteks.selesai_tugas
            ]

        return {
            "balasan": "\n".join(b for b in balasan if b).strip(),
            "alat": alat,
            "dikerjakan": list(konteks.selesai_tugas),
            "gagal": belum_selesai,
            "riwayat_tugas": list(konteks.riwayat_tugas),
        }
    finally:
        _konteks_aktif.reset(token)


def jalankan_sinkron(
    state: dict,
    layar: Any,
    pid: str = "default",
    batas: float = 60.0,
    model: Any = None,
) -> dict:
    """Jadwalkan Runner agen operator ke loop agen (kirim_ke_loop_agen) sambil mengeksekusi aksi _Layar di thread pemanggil."""
    antrean_layar: queue.Queue = queue.Queue()

    def eksekusi_di_pemanggil(fn: Callable[[], Any]) -> Any:
        hasil_q: queue.Queue = queue.Queue(maxsize=1)
        antrean_layar.put((fn, hasil_q))
        ok, nilai = hasil_q.get()
        if not ok:
            raise nilai
        return nilai

    fut = kirim_ke_loop_agen(jalankan(state, layar, pid=pid, eksekutor=eksekusi_di_pemanggil, model=model))
    fut.add_done_callback(lambda _: antrean_layar.put(None))

    while True:
        try:
            item = antrean_layar.get(timeout=batas)
        except queue.Empty as err:
            fut.cancel()
            raise TimeoutError(f"Agen operator melebihi batas waktu {batas} detik.") from err
        if item is None:
            break
        fn, hasil_q = item
        try:
            hasil_q.put((True, fn()))
        except Exception as e:
            hasil_q.put((False, e))

    return fut.result()
