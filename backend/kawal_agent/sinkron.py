"""Menyelaraskan data kerja sesi (state) ke pengajuan di mock SIHALAL.

Idempoten: item buatan agen berprefiks 'ag-' diganti utuh setiap sinkron, item lain (hasil ketikan
pengguna di web) dibiarkan. Hanya bagian yang berubah yang ditulis, supaya audit tidak berisik.
Bahan yang belum bersih ditahan sampai pengguna menyetujui (gerbang masukkan_bahan_bermasalah).
"""
import copy
import re
from fastapi import HTTPException

import sihalal_mock as sm

from .kategori import KATEGORI

AWALAN = "ag-"
KOMITMEN_KUNCI = {
    "kebijakan_halal": "kebijakanHalal",
    "pengertian_halal_haram": "pengertianHalalHaram",
    "praktik_sjph": "praktikSjph",
}


def slug(teks: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (teks or "").lower()).strip("-")[:40] or "x"


def _norm(teks: str) -> str:
    return re.sub(r"\s+", " ", (teks or "").strip().lower())


def _angka(v) -> float:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _tanpa_sumber(obj):
    """Bandingkan isi tanpa cap waktu 'sumber' supaya sinkron berulang tidak menulis ulang tanpa perubahan."""
    if isinstance(obj, dict):
        return {k: _tanpa_sumber(v) for k, v in obj.items() if k not in ("sumber", "disetujuiPada")}
    if isinstance(obj, list):
        isi = [_tanpa_sumber(x) for x in obj]
        if isi and all(isinstance(x, dict) and "id" in x for x in isi):
            isi.sort(key=lambda x: str(x["id"]))  # urutan tidak berarti: item web dan item agen boleh berselang-seling
        return isi
    return obj


def _milik_pengguna(daftar: list[dict]) -> list[dict]:
    return [x for x in daftar if not str(x.get("id", "")).startswith(AWALAN)]


def _persetujuan(state, kunci: str, ref: str):
    waktu = (state.get("persetujuan") or {}).get(kunci)
    if not waktu:
        return None
    return {"disetujuiPada": waktu, "sumber": {"oleh": "pengguna", "waktu": waktu, "ref": ref, "catatan": "Disetujui pengguna lewat chat"}}


def bahan_siap_masuk(state, item: dict) -> bool:
    """Bersih langsung masuk. Yang bermasalah masuk hanya setelah pengguna menyetujui (flag per item)."""
    v = item.get("verifikasi") or {}
    if v.get("verdict") == "haram":
        return False
    return v.get("verdict") == "bersih" or bool(item.get("disetujui"))


def sinkron(state, ref: str = "") -> dict:
    pid = state.get("pengajuan_id")
    if not pid:
        return {"disinkronkan": False, "alasan": "Belum ada draf pengajuan di SIHALAL. Buat drafnya dulu."}
    dok = state.get("dok") or {}
    kat = KATEGORI.get(state.get("kategori") or "", {})
    diubah, ditahan, tak_cocok = [], [], []

    with sm._kunci:
        try:
            p = sm._cari(pid)
        except HTTPException as e:
            return {"disinkronkan": False, "alasan": e.detail}
        if not sm._bisa_diubah(p):
            return {"disinkronkan": False, "alasan": "Pengajuan sudah dikirim sehingga tidak bisa diubah."}
        p = copy.deepcopy(p)
        pabrik_id = (p["data"]["pabrikIds"] or [None])[0]

        def sumber(catatan: str, yakin: float = 0.95):
            return sm._sumber_agen(ref, yakin, catatan)

        def tulis(bagian: str, baru, aksi: str):
            if _tanpa_sumber(baru) != _tanpa_sumber(p[bagian]):
                try:
                    sm.ubah_bagian(pid, bagian, baru, pelaku="kawalhalal", aksi=aksi, ref=ref or None)
                except HTTPException as e:
                    tak_cocok.append(f"{bagian}: {e.detail}")
                    return
                p[bagian] = copy.deepcopy(baru)
                diubah.append(bagian)

        # ---- bahan ----
        bahan_sendiri = []
        id_bahan: dict[str, str] = {}
        for item in dok.get("bahan", []):
            v = item.get("verifikasi") or {}
            if not bahan_siap_masuk(state, item):
                if v.get("verdict") != "haram":
                    ditahan.append(item["nama"])
                continue
            bid = f"{AWALAN}b-{slug(item['nama'])}"
            id_bahan[_norm(item["nama"])] = bid
            baris = {
                "id": bid,
                "tipe": "bersertifikat" if v.get("nomor_dipakai") else "tidak-bersertifikat",
                "jenis": item.get("jenis") or "bahan",
                "nama": item["nama"],
                "bukti": v.get("bukti", "kurang"),
                "alasanBukti": (v.get("alasan", "") + (f" Langkah: {v['langkah_berikutnya']}" if v.get("langkah_berikutnya") else "")).strip(),
                "konfirmasi": "terkonfirmasi" if item.get("dikonfirmasi") else "perlu-konfirmasi",
                "sumber": sumber("Diverifikasi KawalHalal terhadap registri simulasi", 0.95 if v.get("verdict") == "bersih" else 0.6),
            }
            if item.get("produsen"):
                baris["produsen"] = item["produsen"]
            if v.get("nomor_dipakai"):
                baris["noSertifikat"] = v["nomor_dipakai"]
            if item.get("foto_bukti"):
                baris["fotoSumber"] = {"nama": item["foto_bukti"]}
            bahan_sendiri.append(baris)

        catatan_pembelian, pemeriksaan = [], []
        for i, r in enumerate(dok.get("pembelian", []), start=1):
            bid = id_bahan.get(_norm(r.get("bahan", "")))
            if not bid:
                tak_cocok.append(f"Pembelian '{r.get('bahan')}' belum cocok dengan bahan yang sudah masuk.")
                continue
            catatan_pembelian.append({"id": f"{AWALAN}cp-{i}", "bahanId": bid, "jumlah": _angka(r.get("jumlah")), "satuan": r.get("satuan", ""),
                                      "tanggal": r.get("tanggal", ""), "sumber": sumber("Dari jawaban pengguna", 1.0)})
            pemeriksaan.append({"id": f"{AWALAN}pk-{i}", "bahanId": bid, "lokasi": r.get("lokasi_periksa", ""),
                                "tanggal": r.get("tanggal_periksa", ""), "sumber": sumber("Dari jawaban pengguna", 1.0)})

        daftar_lama = p["bahan"]
        tulis("bahan", {
            "daftarBahan": _milik_pengguna(daftar_lama["daftarBahan"]) + bahan_sendiri,
            "catatanPembelian": _milik_pengguna(daftar_lama["catatanPembelian"]) + catatan_pembelian,
            "pemeriksaan": _milik_pengguna(daftar_lama["pemeriksaan"]) + pemeriksaan,
        }, "Menyelaraskan daftar bahan dari percakapan")

        # ---- produk dan pemetaan ----
        id_produk: dict[str, str] = {}
        produk_sendiri, pemetaan_sendiri = [], []
        ids_bahan_p = [b["id"] for b in bahan_sendiri if b["jenis"] in ("bahan", "kemasan")]
        for r in dok.get("produk", []):
            pr_id = f"{AWALAN}pr-{slug(r['nama'])}"
            id_produk[_norm(r["nama"])] = pr_id
            produk_sendiri.append({
                "id": pr_id, "klasifikasi": kat.get("klasifikasi", "Makanan"), "rincian": r.get("rincian") or "Lainnya",
                "nama": r["nama"], "merek": r.get("merek", ""), "bahanIds": ids_bahan_p, "sumber": sumber("Dari jawaban pengguna", 1.0),
            })
            if pabrik_id:
                pemetaan_sendiri.append({"id": f"{AWALAN}pm-{slug(r['nama'])}", "produkId": pr_id, "pabrikId": pabrik_id})
        tulis("produk", _milik_pengguna(p["produk"]) + produk_sendiri, "Menyelaraskan daftar produk dari percakapan")
        tulis("pemetaan", _milik_pengguna(p["pemetaan"]) + pemetaan_sendiri, "Memetakan produk ke fasilitas produksi")

        # ---- proses ----
        proses = copy.deepcopy(p["proses"])
        proses["alurProses"] = _milik_pengguna(proses["alurProses"]) + [
            {"id": f"{AWALAN}al-{i}", "judul": r["judul"],
             "langkah": [x.strip() for x in str(r.get("langkah", "")).split(";") if x.strip()], "sumber": sumber("Dari jawaban pengguna", 1.0)}
            for i, r in enumerate(dok.get("proses", []), start=1)
        ]
        simpan = []
        for i, r in enumerate(dok.get("penyimpanan", []), start=1):
            jenis = "produk" if _norm(r.get("jenis", "")) == "produk" else "bahan"
            ref_id = (id_produk if jenis == "produk" else id_bahan).get(_norm(r.get("item", "")))
            if not ref_id:
                tak_cocok.append(f"Penyimpanan '{r.get('item')}' belum cocok dengan {jenis} yang sudah masuk.")
                continue
            simpan.append({"id": f"{AWALAN}sp-{i}", "jenis": jenis, "refId": ref_id, "jumlah": _angka(r.get("jumlah")),
                           "tanggalMasuk": r.get("tanggal_masuk", ""), "sumber": sumber("Dari jawaban pengguna", 1.0)})
        proses["penyimpanan"] = _milik_pengguna(proses["penyimpanan"]) + simpan
        hasil = []
        for i, r in enumerate(dok.get("hasil", []), start=1):
            pr_id = id_produk.get(_norm(r.get("produk", "")))
            if not pr_id:
                tak_cocok.append(f"Hasil produksi '{r.get('produk')}' belum cocok dengan produk yang sudah masuk.")
                continue
            hasil.append({"id": f"{AWALAN}hp-{i}", "produkId": pr_id, "jumlah": _angka(r.get("jumlah")),
                          "tanggalProduksi": r.get("tanggal_produksi", ""), "sumber": sumber("Dari jawaban pengguna", 1.0)})
        proses["hasilProduksi"] = _milik_pengguna(proses["hasilProduksi"]) + hasil
        proses["distribusi"] = _milik_pengguna(proses["distribusi"]) + [
            {k: v for k, v in {
                "id": f"{AWALAN}ds-{i}", "tujuan": r.get("tujuan", ""), "produkId": id_produk.get(_norm(r.get("produk", ""))),
                "jumlah": _angka(r["jumlah"]) if r.get("jumlah") else None, "sumber": sumber("Dari jawaban pengguna", 1.0),
            }.items() if v not in (None, "")}
            for i, r in enumerate(dok.get("distribusi", []), start=1)
        ]
        lampiran = state.get("lampiran") or {}
        if lampiran.get("layout") and pabrik_id:
            proses["layout"] = _milik_pengguna(proses["layout"]) + [
                {"id": f"{AWALAN}ly-1", "pabrikId": pabrik_id, "berkas": lampiran["layout"], "sumber": sumber("Foto dikirim pengguna", 1.0)}
            ]
        proses["pernyataanBebasBabi"] = _persetujuan(state, "bebas_babi", ref) or proses["pernyataanBebasBabi"]
        tulis("proses", proses, "Menyelaraskan proses produksi dari percakapan")

        # ---- komitmen ----
        komitmen = copy.deepcopy(p["komitmen"])
        for k_state, k_field in KOMITMEN_KUNCI.items():
            komitmen[k_field] = _persetujuan(state, k_state, ref) or komitmen[k_field]
        komitmen["anggota"] = _milik_pengguna(komitmen["anggota"]) + [
            {"id": f"{AWALAN}an-{i}", "nama": a["nama"], "jabatan": a["jabatan"], "posisi": a["posisi"], "sumber": sumber("Dari jawaban pengguna", 1.0)}
            for i, a in enumerate(state.get("anggota") or [], start=1)
        ]
        tulis("komitmen", komitmen, "Menyelaraskan komitmen dan tanggung jawab dari percakapan")

        # ---- pemantauan (tanda tangan) ----
        pemantauan = copy.deepcopy(p["pemantauan"])
        if lampiran.get("tanda_tangan_pj") and lampiran.get("tanda_tangan_penyelia"):
            penyelia_id = (p["data"]["penyeliaIds"] or [""])[0]
            pemantauan["tandaTangan"] = _milik_pengguna(pemantauan["tandaTangan"]) + [{
                "id": f"{AWALAN}tt-1", "penanggungJawab": lampiran["tanda_tangan_pj"], "penyeliaId": penyelia_id,
                "penyelia": lampiran["tanda_tangan_penyelia"], "sumber": sumber("Dokumen bertanda tangan dikirim pengguna", 1.0),
            }]
        berkas_xlsx = state.get("berkas_dibuat") or []
        pemantauan["dokumenLain"] = _milik_pengguna(pemantauan["dokumenLain"]) + [
            {"id": f"{AWALAN}dl-{i}", "nama": b["nama"], "berkas": {"nama": b["nama"], "url": b.get("url")}}
            for i, b in enumerate(berkas_xlsx, start=1)
        ]
        tulis("pemantauan", pemantauan, "Menyelaraskan dokumen pendukung dari percakapan")

        kelengkapan = sm.hitung_kelengkapan(p)

    return {
        "disinkronkan": True,
        "bagian_diubah": diubah,
        "bahan_ditahan_menunggu_konfirmasi": ditahan,
        "baris_belum_cocok": tak_cocok,
        "kelengkapan": {k: f"{v['done']}/{v['total']}" for k, v in kelengkapan.items()},
    }


def rincian_kurang(p: dict) -> list[str]:
    """Isian wajib yang belum terpenuhi, dalam kalimat. Urutan dan aturannya sama dengan sihalal_mock.hitung_kelengkapan."""
    data, komitmen, bahan, produk = p["data"], p["komitmen"], p["bahan"], p["produk"]
    proses, pemetaan, pemantauan = p["proses"], p["pemetaan"], p["pemantauan"]
    bahan_ids = [b["id"] for b in bahan["daftarBahan"]]

    def semua(daftar):
        return bool(bahan_ids) and all(any(x["bahanId"] == i for x in daftar) for i in bahan_ids)

    cek = [
        ("Data Pengajuan", "nomor surat", data["nomorSurat"] != ""),
        ("Data Pengajuan", "tanggal surat", data["tanggalSurat"] != ""),
        ("Data Pengajuan", "jenis produk", data["jenisProduk"] != ""),
        ("Data Pengajuan", "merek", data["merek"] != ""),
        ("Data Pengajuan", "kode fasilitasi (untuk pendaftaran fasilitasi)", data["jenisPendaftaran"] == "mandiri" or bool(data.get("kodeFasilitasi"))),
        ("Data Pengajuan", "pabrik/fasilitas produksi", len(data["pabrikIds"]) > 0),
        ("Data Pengajuan", "penyelia halal", len(data["penyeliaIds"]) > 0),
        ("Komitmen", "persetujuan kebijakan halal", komitmen["kebijakanHalal"] is not None),
        ("Komitmen", "persetujuan pengertian halal dan haram", komitmen["pengertianHalalHaram"] is not None),
        ("Komitmen", "persetujuan praktik SJPH", komitmen["praktikSjph"] is not None),
        ("Komitmen", "anggota tim halal", len(komitmen["anggota"]) > 0),
        ("Bahan", "daftar bahan", len(bahan["daftarBahan"]) > 0),
        ("Bahan", "daftar produk", len(produk) > 0),
        ("Bahan", "bahan untuk setiap produk", len(produk) > 0 and all(len(x["bahanIds"]) > 0 for x in produk)),
        ("Bahan", "catatan pembelian untuk setiap bahan", semua(bahan["catatanPembelian"])),
        ("Bahan", "catatan pemeriksaan untuk setiap bahan", semua(bahan["pemeriksaan"])),
        ("Proses", "pernyataan bebas babi", proses["pernyataanBebasBabi"] is not None),
        ("Proses", "foto/denah layout produksi", len(proses["layout"]) > 0),
        ("Proses", "catatan penyimpanan", len(proses["penyimpanan"]) > 0),
        ("Proses", "alur proses produksi", len(proses["alurProses"]) > 0),
        ("Proses", "hasil produksi", len(proses["hasilProduksi"]) > 0),
        ("Proses", "distribusi", len(proses["distribusi"]) > 0),
        ("Produk", "pemetaan setiap produk ke fasilitas", len(produk) > 0 and all(any(m["produkId"] == x["id"] for m in pemetaan) for x in produk)),
        ("Pemantauan", "tanda tangan penanggung jawab dan penyelia", len(pemantauan["tandaTangan"]) > 0),
    ]
    return [f"{tab}: {apa}" for tab, apa, ok in cek if not ok]
