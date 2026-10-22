"""Latihan demo dengan Gemini asli dan operator browser. Jalankan dari folder backend: python latih_operator.py"""
import asyncio, mimetypes, os, socket, sys, threading, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
os.environ["KALA_OPERATOR"] = "ui"
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]
os.environ["OPERATOR_BASE_URL"] = f"http://127.0.0.1:{PORT}"
from dotenv import load_dotenv
load_dotenv(override=True)
os.environ["KALA_OPERATOR"] = "ui"
import uvicorn, main
from services import telegram_bot
telegram_bot.aktif = lambda: False
main.sajikan_frontend(Path("../frontend/dist").resolve())
srv = uvicorn.Server(uvicorn.Config(main.app, port=PORT, log_level="warning"))
threading.Thread(target=srv.run, daemon=True).start()
while not srv.started: time.sleep(0.1)

import sihalal_mock as sm
from kawal_agent import operator_ui
from kawal_agent.agent import di_loop_agen, hapus_sesi, jalankan, lihat_state
ASET = Path("../docs/demo/aset").resolve()
U = "6281200000777"
def berkas(n): p = ASET / n; return {"nama": p.name, "mime": mimetypes.guess_type(p.name)[0] or "application/octet-stream", "data": p.read_bytes()}
BEAT = [
 ("kategori", "Halo", []),
 ("data usaha", "1. Saya Pak Joko, usaha Bakso Pak Joko, email joko@example.com, HP 081234567890, NIB 9120001234567, alamat Jl. Mawar 1 Bandung 40135 Jawa Barat, skala mikro. Punya 1 outlet, omzet 500 juta per tahun.", []),
 ("foto kecap", "Produk saya Bakso Sapi, merek Bakso Pak Joko, jenis produk olahan daging. Ini label kecap saya.", ["1-label-kecap.jpg"]),
 ("daging+gelatin", "Daging sapinya saya beli di lapak Pak Udin, Pasar Kosambi. Saya juga pakai gelatin, tanpa merek dan tanpa sertifikat.", []),
 ("ya", "ya", []),
 ("excel", "Tolong masukkan isi berkas Excel ini.", ["3-berkas-isian-pak-joko.xlsx"]),
 ("periksa", "Periksa pengajuan saya, apakah sudah bisa dikirim?", []),
]
sm.muat_seed(); asyncio.run(di_loop_agen(hapus_sesi(U)))
for nama, teks, lamp in BEAT:
    t = time.time()
    h = asyncio.run(di_loop_agen(jalankan(U, teks, [berkas(x) for x in lamp])))
    d = time.time() - t
    sibuk = operator_ui.sibuk(next(iter(sm._pengajuan), {}).get("id", "")) if sm._pengajuan else False
    print(f"\n=== {nama} (balasan {d:.0f} dtk, operator masih sibuk: {sibuk})\nalat: {h['alat']}\n{h['balasan'][:700]}", flush=True)
    for p in sm._pengajuan:
        operator_ui.tunggu(p["id"], 90)
st = asyncio.run(di_loop_agen(lihat_state(U)))
p = sm._cari(st["pengajuan_id"])
print("\n=== STATE")
print("bahan:", [(b["nama"], b["bukti"], b["konfirmasi"], b["sumber"]["oleh"]) for b in p["bahan"]["daftarBahan"]])
print("produk:", [(x["nama"], len(x["bahanIds"])) for x in p["produk"]], "pemetaan:", len(p["pemetaan"]))
print("kelengkapan:", {k: f"{v['done']}/{v['total']}" for k, v in sm.hitung_kelengkapan(p).items()})
print("log operator:"); print("\n".join(operator_ui.riwayat(p["id"])))
operator_ui.tutup(); srv.should_exit = True
