"""Verifikasi bahan: gabungan tool deterministik. Dipakai tool agen dan aturan masuk ke mockup.

Hasil selalu berupa status kelengkapan bukti, bukan penetapan kehalalan (BR-07, BR-16).
verdict:
  bersih               bukti lengkap, boleh langsung dimasukkan ke mockup
  perlu_tindak_lanjut  ada celah, jelaskan ke pengguna dan minta konfirmasi sebelum dimasukkan
  haram                mengandung bahan yang tidak dapat disertifikasi (BR-14), tidak dimasukkan
"""
import re
from typing import Optional

from tools import bedah_titik_kritis, cek_bukti_hewan_sembelihan

from . import registri

_STOP = {"dan", "cap", "merek", "produk", "pt", "cv", "rasa", "instan", "bahan", "asli"}


def _token(teks: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (teks or "").lower()) if t not in _STOP and len(t) > 1}


def verifikasi_bahan(
    nama: str,
    jenis: str,
    produsen: str,
    nomor_sertifikat: str,
    pemasok: str,
    jenis_hewan: str,
) -> dict:
    bedah = bedah_titik_kritis(nama)
    kl = bedah["klasifikasi"]
    hewan = (jenis_hewan or bedah.get("jenis_hewan") or "").lower()
    nomor = re.sub(r"[\s\-]", "", nomor_sertifikat or "").upper()
    dasar = {
        "nama": nama,
        "klasifikasi": kl,
        "jenis_hewan": hewan or None,
        "nomor_dipakai": nomor or None,
        "catatan_penelusuran": [],
        "kandidat_registri": [],
        "sumber_data": registri.SUMBER_DATA,
    }

    def hasil(verdict: str, bukti: str, tipe: str, alasan: str, langkah: str = "") -> dict:
        return {**dasar, "verdict": verdict, "bukti": bukti, "tipe": tipe, "alasan": alasan, "langkah_berikutnya": langkah}

    if kl == "haram":
        return hasil("haram", "kurang", "tidak-bersertifikat", bedah["alasan"], "Tidak dimasukkan ke pengajuan halal.")

    # Hewan sembelihan: jalur RPH/RPU, boleh ditelusuri dari nama lapak.
    if kl == "hewani_sembelihan" and jenis == "bahan":
        nama_cek = "" if nomor else pemasok  # nama lapak tidak sama dengan nama RPH/RPU, jadi jangan dicocokkan ke sertifikat
        if not nomor and pemasok:
            cocok = registri.cari_pemasok_daging(pemasok, jenis_hewan=hewan)
            if len(cocok) > 1 and cocok[0]["skor"] == cocok[1]["skor"]:
                dasar["catatan_penelusuran"].append(
                    "Lebih dari satu lapak cocok dengan nama itu, minta nama lengkap lapak atau nomor sertifikat RPH/RPU."
                )
            elif cocok and cocok[0]["nomor_sertifikat"]:
                lapak = cocok[0]
                nomor = lapak["nomor_sertifikat"]
                dasar["nomor_dipakai"] = nomor
                nama_cek = lapak["rph_rpu"] or ""
                dasar["catatan_penelusuran"].append(
                    f"Lapak '{lapak['lapak']}' ({lapak['pasar']}) tercatat memasok dari {lapak['rph_rpu']} di registri simulasi."
                )
            elif cocok:
                dasar["catatan_penelusuran"].append(f"Lapak '{cocok[0]['lapak']}' ada di registri tetapi belum terhubung ke RPH/RPU bersertifikat.")
            else:
                dasar["catatan_penelusuran"].append(f"Lapak '{pemasok}' tidak ditemukan di registri.")
        bukti = cek_bukti_hewan_sembelihan(hewan, nama_cek, nomor)
        status = {"ada": "ada", "kurang": "kurang", "tidak_jelas": "tidak-jelas", "di_luar_cakupan": "tidak-jelas"}[bukti["status_bukti"]]
        verdict = "bersih" if status == "ada" else "perlu_tindak_lanjut"
        return hasil(verdict, status, "bersertifikat" if nomor else "tidak-bersertifikat", bukti["alasan"], bukti["langkah_berikutnya"])

    # Ada nomor sertifikat: cocokkan dengan registri produk.
    if nomor:
        rec = registri.cari_nomor(nomor)
        if rec is None:
            return hasil("perlu_tindak_lanjut", "tidak-jelas", "bersertifikat",
                         f"Nomor sertifikat {nomor} tidak ditemukan di registri.",
                         "Periksa ulang nomor di kemasan atau kirim foto label yang lebih jelas.")
        if rec["status"] != "Berlaku":
            return hasil("perlu_tindak_lanjut", "kurang", "bersertifikat",
                         f"Sertifikat {nomor} ({rec['nama_produk']}) berstatus {rec['status']} sejak {rec['tanggal_kadaluarsa']}.",
                         "Cari produk pengganti yang sertifikatnya masih berlaku atau minta sertifikat terbaru dari pemasok.")
        dicocokkan = _token(nama) & _token(f"{rec['nama_produk']} {rec['merek']} {rec['produsen']}") or (
            _token(produsen) & _token(f"{rec['merek']} {rec['produsen']}")
        )
        if not dicocokkan:
            return hasil("perlu_tindak_lanjut", "tidak-jelas", "bersertifikat",
                         f"Nomor {nomor} terdaftar untuk '{rec['nama_produk']}' ({rec['merek']}), berbeda dengan '{nama}'.",
                         "Konfirmasi apakah ini produk yang sama atau periksa kembali nomornya.")
        return hasil("bersih", "ada", "bersertifikat",
                     f"Sertifikat {nomor} berlaku s.d. {rec['tanggal_kadaluarsa']} untuk '{rec['nama_produk']}' ({rec['produsen']}).")

    if jenis == "kemasan":
        return hasil("bersih", "ada", "tidak-bersertifikat", "Kemasan dicatat dari keterangan pengguna.")

    if kl == "aman_exempt":
        return hasil("bersih", "ada", "tidak-bersertifikat",
                     "Bahan nabati/mineral alami yang umumnya tidak termasuk titik kritis (pengecualian KMA 1360). Tetap pastikan tanpa proses olahan lain.")

    # Sisanya butuh bukti: coba beri kandidat dari registri sebagai petunjuk, jangan dipakai otomatis.
    kandidat = registri.cari_produk(f"{nama} {produsen}")
    dasar["kandidat_registri"] = [
        {"nama_produk": k["nama_produk"], "merek": k["merek"], "nomor_sertifikat": k["nomor_sertifikat"], "status": k["status"]}
        for k in kandidat
    ]
    if kl == "kritis_hewani":
        return hasil("perlu_tindak_lanjut", "kurang", "tidak-bersertifikat",
                     f"{bedah['alasan']} Belum ada nomor sertifikat bahan.",
                     "Kirim foto kemasan yang menampilkan logo dan nomor sertifikat halal, atau sebutkan nomornya.")
    if kl == "tidak_dikenal":
        return hasil("perlu_tindak_lanjut", "tidak-jelas", "tidak-bersertifikat",
                     bedah["alasan"], "Jelaskan bahan ini (nama lengkap atau komposisinya) dan kirim foto labelnya.")
    return hasil("perlu_tindak_lanjut", "kurang", "tidak-bersertifikat",
                 "Belum ada nomor sertifikat halal untuk bahan ini.",
                 "Kirim foto kemasan yang menampilkan logo dan nomor sertifikat halal.")
