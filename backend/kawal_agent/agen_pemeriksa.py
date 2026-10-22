"""Agen Pemeriksa KawalHalal (ADK): memverifikasi kesesuaian antara niat Kala (state)
dan data yang benar-benar terisi di layar SIHALAL setelah operator selesai bekerja.

Bila pemeriksa menemukan selisih (missing, mismatch, unmapped), pekerja operator_ui
mengulang operator maksimal 1 kali (strict limit) lalu mencatat hasilnya di riwayat(pid)
dan menyalurkannya ke Kala lewat periksa_pengajuan.
"""
from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import contextvars
import copy
import logging
import os
import queue
import re
import uuid
from typing import Any, Callable, Optional

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from . import operator_ui, sinkron as sk
from .agent import kirim_ke_loop_agen

logger = logging.getLogger("kawalhalal.agen_pemeriksa")

APP_NAME = "kawalhalal_pemeriksa"
MODEL_RINGAN = os.getenv("GEMINI_MODEL_RINGAN") or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

INSTRUKSI_PEMERIKSA = """\
Kamu adalah agen pemeriksa KawalHalal yang bertugas memverifikasi kesesuaian antara niat Kala (data percakapan pengguna) dan data yang terisi pada formulir web SIHALAL.

ATURAN WAJIB:
1. Panggil niat_kala() untuk membaca daftar bahan, produk, pembelian, dan komitmen yang seharusnya masuk ke SIHALAL.
2. Panggil baca_tab(tab) (misalnya tab 'bahan', 'produk', atau 'komitmen') untuk membaca data yang benar-benar tercatat di layar SIHALAL.
3. Bandingkan secara teliti daftar bahan, produk, dan pemetaan antara niat Kala dan data di SIHALAL.
4. Kembalikan daftar selisih secara konkret dengan kategori (missing, mismatch, atau unmapped) bila ada item yang belum masuk, tidak cocok, atau belum terpetakan.
5. Jika seluruh bahan, produk, dan pemetaan sudah sesuai tanpa selisih, laporkan secara tegas bahwa semua data sudah cocok dan lengkap. Jangan mengarang data di luar hasil tool.
"""

_POLA_NEGASI_SELISIH = re.compile(
    r"(tidak\s+ada\s+selisih|tanpa\s+selisih|0\s+selisih|selisih\s*[:=]\s*0|"
    r"semua\b[^\n.;]*\b(cocok|lengkap|sesuai)|"
    r"seluruh\b[^\n.;]*\b(cocok|lengkap|sesuai)|"
    r"sudah\s+(cocok|lengkap|sesuai))",
    re.IGNORECASE,
)
_POLA_ADA_SELISIH = re.compile(
    r"\b(missing|mismatch|unmapped|belum\s+masuk|belum\s+terisi|tidak\s+cocok|belum\s+dipetakan|belum\s+terpasang)\b",
    re.IGNORECASE,
)


def bandingkan(state: dict, live: dict) -> list[str]:
    """Bandingkan niat Kala (state) terhadap data pengajuan SIHALAL (live) dan kembalikan daftar selisih konkret."""
    if not isinstance(live, dict):
        live = operator_ui._live_kosong()
    dok = (state or {}).get("dok") or {}
    selisih: list[str] = []

    bahan_obj = live.get("bahan") or {}
    daftar_bahan_live = list(bahan_obj.get("daftarBahan") or [])
    bahan_live = {sk._norm(b.get("nama", "")): b for b in daftar_bahan_live if isinstance(b, dict)}
    nama_bahan_live = {b.get("id"): b.get("nama", "") for b in daftar_bahan_live if isinstance(b, dict)}

    diinginkan = operator_ui._bahan_diinginkan(state or {})
    for d in diinginkan:
        kunci = sk._norm(d["nama"])
        ada = bahan_live.get(kunci)
        if not ada:
            selisih.append(f"missing: Bahan '{d['nama']}' belum masuk di SIHALAL.")
        else:
            jenis_ada = (ada.get("jenis") or "bahan").strip().lower()
            prod_ada = (ada.get("produsen") or "").strip()
            sert_ada = (ada.get("noSertifikat") or "").strip()
            if (jenis_ada, prod_ada, sert_ada) != (d["jenis"], d["produsen"].strip(), d["noSertifikat"].strip()):
                selisih.append(f"mismatch: Data bahan '{d['nama']}' di SIHALAL tidak cocok dengan niat Kala.")

    daftar_produk_live = list(live.get("produk") or [])
    produk_live = {sk._norm(p.get("nama", "")): p for p in daftar_produk_live if isinstance(p, dict)}
    bahan_produk = [d for d in diinginkan if d["jenis"] in ("bahan", "kemasan")]

    for r in dok.get("produk", []):
        nama_p = r.get("nama", "")
        kunci_p = sk._norm(nama_p)
        ada_p = produk_live.get(kunci_p)
        if not ada_p:
            selisih.append(f"missing: Produk '{nama_p}' belum masuk di SIHALAL.")
        else:
            merek_ada = (ada_p.get("merek") or "").strip()
            merek_niat = (r.get("merek") or "").strip()
            if merek_niat and merek_ada != merek_niat:
                selisih.append(
                    f"mismatch: Merek produk '{nama_p}' di SIHALAL ('{merek_ada}') tidak cocok dengan niat Kala ('{merek_niat}')."
                )
            terpasang = {sk._norm(nama_bahan_live.get(i, "")) for i in (ada_p.get("bahanIds") or [])}
            kurang_bahan = [d["nama"] for d in bahan_produk if sk._norm(d["nama"]) not in terpasang]
            if kurang_bahan:
                selisih.append(
                    f"unmapped: Bahan belum terpasang pada produk '{nama_p}': {', '.join(kurang_bahan)}."
                )

    pabrik_ids = list((live.get("data") or {}).get("pabrikIds") or [])
    pemetaan_live = list(live.get("pemetaan") or [])
    if pabrik_ids:
        for r in dok.get("produk", []):
            nama_p = r.get("nama", "")
            ada_p = produk_live.get(sk._norm(nama_p))
            if not ada_p or not any(
                m.get("produkId") == ada_p.get("id") and m.get("pabrikId") in pabrik_ids for m in pemetaan_live
            ):
                selisih.append(f"unmapped: Produk '{nama_p}' belum dipetakan ke fasilitas pabrik di SIHALAL.")

    # Periksa langkah formulir lain dari rencana operator (pembelian, pemeriksaan, komitmen, anggota)
    for t in operator_ui.rencana(state or {}, live):
        aksi = t.get("aksi")
        if aksi == "pembelian":
            selisih.append(f"missing: Catatan pembelian bahan '{t.get('bahan')}' belum sesuai di SIHALAL.")
        elif aksi == "pemeriksaan":
            selisih.append(f"missing: Catatan pemeriksaan bahan '{t.get('bahan')}' belum sesuai di SIHALAL.")
        elif aksi == "setuju_komitmen":
            selisih.append(f"missing: Pernyataan komitmen '{t.get('id')}' belum disetujui di SIHALAL.")
        elif aksi == "anggota_tambah":
            selisih.append(f"missing: Anggota tim halal '{t.get('nama')}' belum masuk di SIHALAL.")
        elif aksi == "setuju_bebas_babi":
            selisih.append("missing: Pernyataan bebas babi belum disetujui di SIHALAL.")

    return selisih


class _KonteksPemeriksa:
    """Konteks eksekusi per sesi pemeriksa agar tool terhubung ke state dan sumber data live."""

    def __init__(
        self,
        state: dict,
        layar: Any = None,
        live: Optional[dict] = None,
        eksekutor: Optional[Callable[[Callable[[], Any]], Any]] = None,
    ):
        self.state = state or {}
        self.layar = layar
        self.live = live
        self.eksekutor = eksekutor

    def panggil_layar(self, fn: Callable[[], Any]) -> Any:
        if self.eksekutor is not None:
            return self.eksekutor(fn)
        return fn()

    def ambil_live(self) -> dict:
        if self.layar is not None and hasattr(self.layar, "baca") and callable(self.layar.baca):
            data = self.panggil_layar(self.layar.baca)
            if isinstance(data, dict):
                return data
        if isinstance(self.live, dict):
            return copy.deepcopy(self.live)
        pid = self.state.get("pengajuan_id")
        if pid:
            try:
                import httpx

                r = httpx.get(f"{operator_ui._base_url()}/api/sihalal/pengajuan/{pid}", timeout=5.0)
                if r.status_code == 200 and isinstance(r.json(), dict):
                    return r.json()
            except Exception:
                pass
            try:
                import sihalal_mock as sm

                with sm._kunci:
                    return copy.deepcopy(sm._cari(pid))
            except Exception:
                pass
        return operator_ui._live_kosong()


_konteks_aktif: contextvars.ContextVar[Optional[_KonteksPemeriksa]] = contextvars.ContextVar(
    "konteks_pemeriksa_aktif", default=None
)
_model_override: Any = None


def _ambil_konteks() -> _KonteksPemeriksa:
    ctx = _konteks_aktif.get()
    if ctx is None:
        raise RuntimeError("Konteks agen pemeriksa belum diinisialisasi.")
    return ctx


def pasang_konteks(
    state: dict,
    layar: Any = None,
    live: Optional[dict] = None,
    eksekutor: Optional[Callable[[Callable[[], Any]], Any]] = None,
) -> _KonteksPemeriksa:
    """Pasang konteks pemeriksa untuk pengujian langsung tool tanpa Runner."""
    ctx = _KonteksPemeriksa(state=state, layar=layar, live=live, eksekutor=eksekutor)
    _konteks_aktif.set(ctx)
    return ctx


# ------------------------------------------------------------------
# Tool Agen Pemeriksa
# ------------------------------------------------------------------
def baca_tab(tab: str) -> dict:
    """Baca isi tab formulir dari pengajuan SIHALAL sebagaimana tampil di halaman web.

    Args:
        tab: Nama tab formulir yang ingin diperiksa ('bahan', 'produk', 'pemetaan', 'komitmen', 'proses', 'data', 'pemantauan', atau 'semua').

    Returns:
        dict berisi status, nama tab, isi data tab, ringkasan bahan/produk/pemetaan, serta selisih yang terdeteksi.
    """
    ctx = _ambil_konteks()
    nama_tab = (tab or "").strip().lower() or "bahan"
    live = ctx.ambil_live()

    bahan_obj = live.get("bahan") or {}
    daftar_bahan = list(bahan_obj.get("daftarBahan") or [])
    produk_list = list(live.get("produk") or [])
    pemetaan_list = list(live.get("pemetaan") or [])
    komitmen_obj = live.get("komitmen") or {}
    data_obj = live.get("data") or {}

    if nama_tab == "bahan":
        isi = {
            "daftarBahan": daftar_bahan,
            "catatanPembelian": list(bahan_obj.get("catatanPembelian") or []),
            "pemeriksaan": list(bahan_obj.get("pemeriksaan") or []),
            "produk": produk_list,
        }
    elif nama_tab in ("produk", "pemetaan"):
        isi = {
            "produk": produk_list,
            "pemetaan": pemetaan_list,
            "pabrikIds": list(data_obj.get("pabrikIds") or []),
        }
    elif nama_tab == "komitmen":
        isi = komitmen_obj
    elif nama_tab in live:
        isi = live[nama_tab]
    else:
        isi = {
            "bahan": bahan_obj,
            "produk": produk_list,
            "pemetaan": pemetaan_list,
            "komitmen": komitmen_obj,
        }

    selisih = bandingkan(ctx.state, live)
    return {
        "status": "ok",
        "tab": nama_tab,
        "isi": isi,
        "daftar_bahan": [b.get("nama") for b in daftar_bahan if isinstance(b, dict)],
        "daftar_produk": [p.get("nama") for p in produk_list if isinstance(p, dict)],
        "jumlah_pemetaan": len(pemetaan_list),
        "selisih_terdeteksi": selisih,
    }


def niat_kala() -> dict:
    """Baca state dan dokumen yang diserahkan Kala ke operator untuk pengajuan aktif.

    Returns:
        dict berisi pengajuan_id, kategori, daftar bahan yang diinginkan, produk, pembelian, persetujuan, dan anggota tim.
    """
    ctx = _ambil_konteks()
    st = ctx.state or {}
    dok = st.get("dok") or {}
    bahan_diinginkan = operator_ui._bahan_diinginkan(st)
    return {
        "status": "ok",
        "pengajuan_id": st.get("pengajuan_id"),
        "kategori": st.get("kategori"),
        "bahan": bahan_diinginkan,
        "produk": list(dok.get("produk") or []),
        "pembelian": list(dok.get("pembelian") or []),
        "persetujuan": list((st.get("persetujuan") or {}).keys()),
        "anggota": list(st.get("anggota") or []),
    }


SEMUA_TOOL_PEMERIKSA = [baca_tab, niat_kala]


def model_override_aktif() -> bool:
    return _model_override is not None


def model_siap_dipanggil(model=None) -> bool:
    target = model if model is not None else _model_override
    skrip = getattr(target, "skrip", None)
    log = getattr(target, "log", None)
    if isinstance(skrip, list) and isinstance(log, list):
        return len(log) < len(skrip)
    return True


def model_pemeriksa():
    """Ambil model untuk agen pemeriksa: override tes -> GEMINI_MODEL_RINGAN -> GEMINI_MODEL."""
    if _model_override is not None:
        return _model_override
    return os.getenv("GEMINI_MODEL_RINGAN") or os.getenv("GEMINI_MODEL") or MODEL_RINGAN


def bangun_agen(model=None) -> LlmAgent:
    """Bangun LlmAgent bernama 'pemeriksa' dengan model ringan dan tool pemeriksa."""
    return LlmAgent(
        name="pemeriksa",
        model=model if model is not None else model_pemeriksa(),
        description="Agen pemeriksa yang memverifikasi kesesuaian data SIHALAL terhadap niat Kala.",
        instruction=INSTRUKSI_PEMERIKSA,
        tools=SEMUA_TOOL_PEMERIKSA,
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )


pemeriksa = bangun_agen()
root_agent = pemeriksa


def ganti_model(model) -> None:
    """Untuk pengujian: pasang model pengganti (mis. LLMTerskrip) pada agen pemeriksa."""
    global _model_override, pemeriksa, root_agent
    _model_override = model
    pemeriksa = bangun_agen(model)
    root_agent = pemeriksa


def periksa_deterministik(state: dict, live: Optional[dict] = None) -> dict:
    """Pemeriksaan deterministik langsung tanpa memanggil LLM (dipakai sebagai fallback atau saat mode agen nonaktif)."""
    ctx = _KonteksPemeriksa(state=state, live=live)
    data_live = ctx.ambil_live()
    selisih = bandingkan(state, data_live)
    cocok = len(selisih) == 0
    laporan = (
        "Semua data bahan, produk, dan pemetaan di SIHALAL sudah cocok dan lengkap sesuai niat Kala."
        if cocok
        else "Pemeriksa menemukan selisih antara niat Kala dan SIHALAL: " + "; ".join(selisih)
    )
    return {
        "cocok": cocok,
        "selisih": selisih,
        "laporan": laporan,
        "balasan": laporan,
        "alat": [],
    }


def _ekstrak_selisih_teks(teks: str) -> list[str]:
    bersih = (teks or "").strip()
    if not bersih or _POLA_NEGASI_SELISIH.search(bersih):
        return []
    if _POLA_ADA_SELISIH.search(bersih):
        baris = [b.strip("-•* \t") for b in bersih.splitlines() if b.strip()]
        kandidat = [b for b in baris if _POLA_ADA_SELISIH.search(b)]
        return kandidat or [bersih]
    return []


async def jalankan(
    state: dict,
    layar: Any = None,
    live: Optional[dict] = None,
    pid: str = "default",
    eksekutor: Optional[Callable[[Callable[[], Any]], Any]] = None,
    model: Any = None,
) -> dict:
    """Jalankan agen pemeriksa pada Runner dan sesi terisolasi untuk memverifikasi satu pengajuan."""
    konteks = _KonteksPemeriksa(state=state, layar=layar, live=live, eksekutor=eksekutor)
    token = _konteks_aktif.set(konteks)
    try:
        agen = bangun_agen(model=model)
        sessions = InMemorySessionService()
        runner = Runner(agent=agen, app_name=APP_NAME, session_service=sessions)
        user_id = f"pemeriksa-{pid}"
        session_id = f"sesi-pm-{pid}-{uuid.uuid4().hex[:8]}"
        await sessions.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id, state={})
        pesan = types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=(
                        f"Periksa kesesuaian pengajuan {pid} antara niat Kala dan data di SIHALAL. "
                        "Panggil niat_kala dan baca_tab, lalu laporkan daftar selisih atau nyatakan cocok."
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

        teks_akhir = "\n".join(b for b in balasan if b).strip()
        live_akhir = konteks.ambil_live()
        selisih_aktual = bandingkan(state, live_akhir)
        selisih_llm = _ekstrak_selisih_teks(teks_akhir)

        selisih = list(selisih_aktual)
        if not selisih and selisih_llm:
            selisih.extend(selisih_llm)

        cocok = len(selisih) == 0
        if teks_akhir:
            laporan = teks_akhir
            if not cocok and _POLA_NEGASI_SELISIH.search(teks_akhir):
                laporan = "Pemeriksa menemukan selisih antara niat Kala dan SIHALAL: " + "; ".join(selisih)
        else:
            laporan = (
                "Semua data bahan, produk, dan pemetaan di SIHALAL sudah cocok dan lengkap sesuai niat Kala."
                if cocok
                else "Pemeriksa menemukan selisih antara niat Kala dan SIHALAL: " + "; ".join(selisih)
            )

        return {
            "cocok": cocok,
            "selisih": selisih,
            "selisih_llm": selisih_llm,
            "laporan": laporan,
            "balasan": laporan,
            "alat": alat,
        }
    finally:
        _konteks_aktif.reset(token)


def jalankan_sinkron(
    state: dict,
    layar: Any = None,
    live: Optional[dict] = None,
    pid: str = "default",
    batas: float = 60.0,
    model: Any = None,
) -> dict:
    """Jadwalkan Runner agen pemeriksa ke loop agen (kirim_ke_loop_agen) sambil mengeksekusi aksi _Layar di thread pemanggil."""
    antrean_layar: queue.Queue = queue.Queue()

    def eksekusi_di_pemanggil(fn: Callable[[], Any]) -> Any:
        hasil_q: queue.Queue = queue.Queue(maxsize=1)
        antrean_layar.put((fn, hasil_q))
        ok, nilai = hasil_q.get()
        if not ok:
            raise nilai
        return nilai

    fut = kirim_ke_loop_agen(
        jalankan(state, layar=layar, live=live, pid=pid, eksekutor=eksekusi_di_pemanggil, model=model)
    )
    fut.add_done_callback(lambda _: antrean_layar.put(None))

    while True:
        try:
            item = antrean_layar.get(timeout=batas)
        except queue.Empty as err:
            fut.cancel()
            raise TimeoutError(f"Agen pemeriksa melebihi batas waktu {batas} detik.") from err
        if item is None:
            break
        fn, hasil_q = item
        try:
            hasil_q.put((True, fn()))
        except Exception as e:
            hasil_q.put((False, e))

    return fut.result()


def periksa_untuk_kala(
    state: dict,
    pengajuan_live: Optional[dict] = None,
    hasil_tercatat: Optional[dict] = None,
    riwayat_op: Optional[list[str]] = None,
) -> dict:
    """Susun laporan pemeriksa untuk disertakan pada periksa_pengajuan di tools.py."""
    pid = (state or {}).get("pengajuan_id") or "default"
    riwayat_list = list(riwayat_op or [])

    if hasil_tercatat is not None:
        hasil = copy.deepcopy(hasil_tercatat)
        if isinstance(pengajuan_live, dict) and not hasil.get("dari_layar"):
            selisih_kini = bandingkan(state, pengajuan_live)
            if not selisih_kini and hasil.get("cocok"):
                pass
            elif selisih_kini:
                gabung = list(hasil.get("selisih") or [])
                for s in selisih_kini:
                    if s not in gabung:
                        gabung.append(s)
                hasil["selisih"] = gabung
                hasil["cocok"] = False
                if _POLA_NEGASI_SELISIH.search(hasil.get("laporan") or ""):
                    hasil["laporan"] = "Pemeriksa menemukan selisih antara niat Kala dan SIHALAL: " + "; ".join(gabung)
    elif model_override_aktif() and model_siap_dipanggil():
        try:
            try:
                asyncio.get_running_loop()
                # Bila dipanggil dari dalam event loop yang sedang berjalan, jalankan di thread terpisah
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    hasil = pool.submit(
                        lambda: asyncio.run(jalankan(state, live=pengajuan_live, pid=pid))
                    ).result(timeout=30)
            except RuntimeError:
                hasil = asyncio.run(jalankan(state, live=pengajuan_live, pid=pid))
        except Exception as e:
            logger.warning("Pemeriksa gagal saat periksa_untuk_kala (%s), fallback deterministik", e)
            hasil = periksa_deterministik(state, live=pengajuan_live)
    else:
        hasil = periksa_deterministik(state, live=pengajuan_live)

    if not riwayat_list and hasil.get("riwayat"):
        riwayat_list = list(hasil["riwayat"])

    return {
        "cocok": bool(hasil.get("cocok", not hasil.get("selisih"))),
        "selisih": list(hasil.get("selisih") or []),
        "laporan": str(hasil.get("laporan") or ""),
        "diulang": bool(hasil.get("diulang", False)),
        "selisih_awal": list(hasil.get("selisih_awal") or []),
        "riwayat": riwayat_list,
    }
