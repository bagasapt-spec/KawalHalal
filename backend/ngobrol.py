"""Ngobrol dengan agen KawalHalal dari terminal (butuh GEMINI_API_KEY di .env).

  python ngobrol.py                      # nomor demo bawaan
  python ngobrol.py 6281234567890        # nomor sendiri (sesi terpisah per nomor)

Perintah di dalam chat:
  /file jalur/ke/foto-label.jpg          kirim lampiran (jpg, png, webp, pdf, docx, xlsx) bersama pesan berikutnya
  /state                                 lihat state sesi
  /reset                                 hapus sesi dan data mock SIHALAL
  /keluar
"""
import asyncio
import mimetypes
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import sihalal_mock as sm  # noqa: E402
from kawal_agent.agent import agen_aktif, di_loop_agen, hapus_sesi, jalankan, lihat_state  # noqa: E402


def main() -> None:
    if not agen_aktif():
        sys.exit("GEMINI_API_KEY belum diatur. Isi di backend/.env lalu jalankan lagi.")
    user = re.sub(r"\D", "", sys.argv[1]) if len(sys.argv) > 1 else "6281200000000"
    antre: list[dict] = []
    print(f"KawalHalal (nomor {user}). Ketik /keluar untuk berhenti.\n")
    while True:
        try:
            teks = input("Anda: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if teks == "/keluar":
            break
        if teks == "/state":
            print(asyncio.run(di_loop_agen(lihat_state(user)))); continue
        if teks == "/reset":
            asyncio.run(di_loop_agen(hapus_sesi(user))); sm.muat_seed(); print("Sesi dan data mock direset."); continue
        if teks.startswith("/file "):
            p = Path(teks[6:].strip().strip('"'))
            if not p.is_file():
                print("Berkas tidak ditemukan."); continue
            antre.append({"nama": p.name, "mime": mimetypes.guess_type(p.name)[0] or "application/octet-stream", "data": p.read_bytes()})
            print(f"({p.name} akan dikirim bersama pesan berikutnya)"); continue
        hasil = asyncio.run(di_loop_agen(jalankan(user, teks, antre)))
        antre = []
        print(f"\nKawalHalal: {hasil['balasan']}\n   [tool: {', '.join(hasil['alat']) or '-'}]\n")


if __name__ == "__main__":
    main()
