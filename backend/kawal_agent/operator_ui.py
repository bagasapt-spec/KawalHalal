"""Operator Kala: mengisi web SIHALAL lewat browser seperti pengguna yang mengetik sendiri.

SIHALAL asli tidak punya API, jadi operator hanya memakai pintu yang sama dengan manusia: membuka halaman, mengisi
formulir, menekan tombol. Operator membaca keadaan dari respons yang sama dengan yang dilihat halaman, bukan dari
penyimpanan internal. Pekerjaan berjalan di latar belakang supaya Kala tetap membalas pengguna.

Aktif bila KALA_OPERATOR=ui. Bagian yang belum punya rutinitas formulir (proses produksi, lampiran) tetap ditulis
langsung oleh sinkron.sinkron setelah rutinitas formulir selesai.
"""
import contextlib
import copy
import difflib
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from . import sinkron as sk
from .kategori import KATEGORI

logger = logging.getLogger("kawalhalal.operator")

KUNCI_STATE = ("pengajuan_id", "kategori", "dok", "persetujuan", "anggota", "lampiran", "berkas_dibuat", "akun")
BAGIAN_FORMULIR = frozenset({"bahan", "produk", "pemetaan", "komitmen"})

KLASIFIKASI = {
    "Makanan": ["Produk olahan daging", "Makanan siap saji", "Roti dan kue", "Makanan ringan", "Bumbu dan saus"],
    "Minuman": ["Minuman berbasis teh", "Minuman berbasis kopi", "Minuman sari buah", "Minuman lainnya"],
    "Kosmetik": ["Perawatan kulit", "Perawatan rambut", "Tata rias", "Parfum dan wewangian"],
    "Barang Gunaan": ["Peralatan rumah tangga", "Kemasan dan wadah", "Pakaian dan aksesori", "Barang gunaan lainnya"],
    "Jasa": ["Penyembelihan", "Pengolahan", "Penyimpanan", "Pengemasan", "Distribusi", "Penjualan", "Penyajian"],
}
LABEL_TIPE = {"bersertifikat": "Bahan bersertifikat halal", "tidak-bersertifikat": "Bahan tidak bersertifikat"}
LABEL_JENIS = {"bahan": "Bahan", "kemasan": "Kemasan", "cleaning-agent": "Bahan pembersih"}
LABEL_POSISI = {"ketua": "Ketua", "anggota": "Anggota"}
SATUAN = ("kg", "gram", "liter", "ml", "pcs", "bungkus", "kotak")
CATATAN_SETUJU = "Disetujui pengguna lewat chat, diinput operator Kala"


def aktif() -> bool:
    return os.environ.get("KALA_OPERATOR", "").strip().lower() in ("ui", "1", "true")


def agen_aktif() -> bool:
    return os.environ.get("KALA_OPERATOR_AGEN", "").strip().lower() in ("1", "true", "ya", "ui")


def _base_url() -> str:
    return (os.environ.get("OPERATOR_BASE_URL") or f"http://127.0.0.1:{os.environ.get('PORT', '8000')}").rstrip("/")


def _tanggal_iso(teks) -> str | None:
    teks = str(teks or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(teks, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _persis(teks: str):
    """Nama tombol persis tetapi tanpa membedakan huruf besar kecil: layar bisa menulis 'Kecap Manis' sedangkan data 'Kecap manis'."""
    return re.compile(rf"^{re.escape(teks)}$", re.IGNORECASE)


def _rincian_valid(klasifikasi: str, rincian: str) -> str:
    opsi = KLASIFIKASI.get(klasifikasi) or KLASIFIKASI["Makanan"]
    cocok = {o.lower(): o for o in opsi}
    if (rincian or "").strip().lower() in cocok:
        return cocok[rincian.strip().lower()]
    dekat = difflib.get_close_matches((rincian or "").lower(), list(cocok), n=1, cutoff=0.5)
    return cocok[dekat[0]] if dekat else opsi[-1]


# ---------------------------------------------------------------- rencana (murni, tanpa browser)
def _bahan_diinginkan(state: dict) -> list[dict]:
    hasil = []
    for item in (state.get("dok") or {}).get("bahan", []):
        if not sk.bahan_siap_masuk(state, item):
            continue
        v = item.get("verifikasi") or {}
        nomor = v.get("nomor_dipakai") or ""
        # Bahan bercelah dicatat sebagai bersertifikat tanpa nomor: formulir sendiri yang menandai bukti 'kurang'.
        tipe = "tidak-bersertifikat" if (not nomor and v.get("verdict") == "bersih") else "bersertifikat"
        hasil.append({"nama": item["nama"], "jenis": item.get("jenis") or "bahan", "produsen": item.get("produsen") or "",
                      "tipe": tipe, "noSertifikat": nomor})
    return hasil


def _live_kosong() -> dict:
    return {
        "data": {"pabrikIds": []},
        "bahan": {"daftarBahan": [], "catatanPembelian": [], "pemeriksaan": []},
        "produk": [],
        "pemetaan": [],
        "komitmen": {"kebijakanHalal": None, "pengertianHalalHaram": None, "praktikSjph": None, "anggota": []},
        "proses": {"pernyataanBebasBabi": None},
    }


def rencana(state: dict, live: dict | bool = True) -> list[dict]:
    """Daftar langkah formulir yang masih perlu dikerjakan supaya SIHALAL sesuai data percakapan. Idempoten."""
    if not isinstance(live, dict):
        pid = state.get("pengajuan_id")
        if pid:
            try:
                import httpx

                r = httpx.get(f"{_base_url()}/api/sihalal/pengajuan/{pid}", timeout=5.0)
                live = r.json() if r.status_code == 200 else _live_kosong()
            except Exception:
                live = _live_kosong()
        else:
            live = _live_kosong()
    dok = state.get("dok") or {}
    kat = KATEGORI.get(state.get("kategori") or "", {})
    klasifikasi = kat.get("klasifikasi", "Makanan")
    tugas: list[dict] = []

    bahan_live = {sk._norm(b["nama"]): b for b in live["bahan"]["daftarBahan"]}
    nama_bahan_live = {b["id"]: b["nama"] for b in live["bahan"]["daftarBahan"]}
    diinginkan = _bahan_diinginkan(state)
    nama_diinginkan = {sk._norm(d["nama"]) for d in diinginkan}

    for d in diinginkan:
        ada = bahan_live.get(sk._norm(d["nama"]))
        if not ada:
            tugas.append({"aksi": "bahan_tambah", **d})
        elif (ada.get("tipe"), ada.get("jenis"), ada.get("produsen") or "", ada.get("noSertifikat") or "") != (d["tipe"], d["jenis"], d["produsen"], d["noSertifikat"]):
            tugas.append({"aksi": "bahan_ubah", **d})

    produk_live = {sk._norm(x["nama"]): x for x in live["produk"]}
    produk = []
    for r in dok.get("produk", []):
        entri = {"nama": r["nama"], "merek": r.get("merek") or "", "klasifikasi": klasifikasi, "rincian": _rincian_valid(klasifikasi, r.get("rincian") or "")}
        produk.append(entri)
        ada = produk_live.get(sk._norm(r["nama"]))
        if not ada:
            tugas.append({"aksi": "produk_tambah", **entri})
        elif (ada.get("merek") or "") != entri["merek"]:
            tugas.append({"aksi": "produk_ubah", **entri})

    bahan_produk = [d for d in diinginkan if d["jenis"] in ("bahan", "kemasan")]
    for entri in produk:
        ada = produk_live.get(sk._norm(entri["nama"]))
        terpasang = {sk._norm(nama_bahan_live.get(i, "")) for i in (ada or {}).get("bahanIds", [])}
        if bahan_produk and {sk._norm(d["nama"]) for d in bahan_produk} - terpasang:
            tugas.append({"aksi": "input_bahan", "produk": entri["nama"], "bahan": [{"nama": d["nama"], "jenis": d["jenis"]} for d in bahan_produk]})

    pembelian_live = {c["bahanId"]: c for c in live["bahan"]["catatanPembelian"]}
    pemeriksaan_live = {c["bahanId"]: c for c in live["bahan"]["pemeriksaan"]}
    for r in dok.get("pembelian", []):
        nama = r.get("bahan", "")
        if sk._norm(nama) not in nama_diinginkan:
            continue
        ada_b = bahan_live.get(sk._norm(nama))
        tgl, tgl_periksa = _tanggal_iso(r.get("tanggal")), _tanggal_iso(r.get("tanggal_periksa"))
        satuan = str(r.get("satuan", "")).lower()
        if tgl and satuan in SATUAN and sk._angka(r.get("jumlah")) > 0:
            c = pembelian_live.get(ada_b["id"]) if ada_b else None
            if not c or (sk._angka(c["jumlah"]), c["satuan"], c["tanggal"]) != (sk._angka(r.get("jumlah")), satuan, tgl):
                tugas.append({"aksi": "pembelian", "bahan": nama, "jumlah": sk._angka(r.get("jumlah")), "satuan": satuan, "tanggal": tgl})
        if tgl_periksa and r.get("lokasi_periksa"):
            c = pemeriksaan_live.get(ada_b["id"]) if ada_b else None
            if not c or (c["lokasi"], c["tanggal"]) != (r["lokasi_periksa"], tgl_periksa):
                tugas.append({"aksi": "pemeriksaan", "bahan": nama, "lokasi": r["lokasi_periksa"], "tanggal": tgl_periksa})

    persetujuan = state.get("persetujuan") or {}
    for kunci_state, field in sk.KOMITMEN_KUNCI.items():
        if kunci_state in persetujuan and live["komitmen"].get(field) is None:
            tugas.append({"aksi": "setuju_komitmen", "id": field})
    nama_anggota = {sk._norm(a["nama"]) for a in live["komitmen"]["anggota"]}
    for a in state.get("anggota") or []:
        if sk._norm(a["nama"]) not in nama_anggota:
            tugas.append({"aksi": "anggota_tambah", "nama": a["nama"], "jabatan": a["jabatan"], "posisi": a["posisi"]})
    if "bebas_babi" in persetujuan and live["proses"].get("pernyataanBebasBabi") is None:
        tugas.append({"aksi": "setuju_bebas_babi"})

    pabrik = live["data"].get("pabrikIds") or []
    if pabrik:
        for entri in produk:
            ada = produk_live.get(sk._norm(entri["nama"]))
            if not ada or not any(m["produkId"] == ada["id"] and m["pabrikId"] in pabrik for m in live["pemetaan"]):
                tugas.append({"aksi": "petakan", "produk": entri["nama"]})
    return tugas


# ---------------------------------------------------------------- pelaksana formulir (Playwright)
class _Layar:
    """Satu sesi browser atas nama pengguna. Semua aksi lewat elemen yang terlihat di halaman."""

    def __init__(self, ctx, pid: str, catat):
        self.ctx, self.pid, self.catat = ctx, pid, catat
        self.pg = ctx.new_page()
        self.pg.set_default_timeout(8000)
        self.tab = None

    def baca(self) -> dict:
        r = self.ctx.request.get(f"{_base_url()}/api/sihalal/pengajuan/{self.pid}")
        return r.json()

    def buka(self, tab: str) -> None:
        if self.tab == tab:
            return
        self.pg.goto(f"{_base_url()}/pengajuan/{self.pid}/ubah?tab={tab}")
        self.pg.get_by_role("tab", selected=True).wait_for()
        self.tab = tab
        self.catat(f"Membuka tab {tab}")

    def lihat(self, tab: str = "") -> str:
        target = (tab or "").strip() or self.tab or "bahan"
        self.buka(target)
        return self.pg.locator("body").inner_text()[:4000]

    def _tombol_tambah(self, judul_kartu: str = ""):
        if not judul_kartu:
            return self.pg.get_by_role("button", name="Tambah", exact=True).first
        return self.pg.locator(
            f"xpath=//h3[normalize-space()='{judul_kartu}']/ancestor::*[.//button[normalize-space()='Tambah']][1]//button[normalize-space()='Tambah']"
        ).first

    def _pilih(self, id_pemicu: str, label: str) -> None:
        self.pg.locator(f"#{id_pemicu}").click()
        self.pg.get_by_role("option", name=label, exact=True).click()

    def _simpan(self) -> None:
        dlg = self.pg.get_by_role("dialog")
        dlg.get_by_role("button", name=re.compile(r"^Simpan")).click()  # tombol input bahan berbunyi "Simpan (N bahan)"
        dlg.wait_for(state="hidden")

    def lakukan(self, t: dict) -> None:
        pg, jenis = self.pg, t["aksi"]
        if jenis in ("bahan_tambah", "bahan_ubah", "produk_tambah", "produk_ubah", "input_bahan", "pembelian", "pemeriksaan"):
            self.buka("bahan")
        if jenis == "bahan_tambah":
            self.catat(f"Menambah bahan {t['nama']}")
            self._tombol_tambah("Daftar Nama Bahan dan Kemasan").click()
            self._isi_bahan(t)
        elif jenis == "bahan_ubah":
            self.catat(f"Memperbarui bahan {t['nama']}")
            pg.get_by_role("button", name=_persis(f"Ubah {t['nama']}")).first.click()
            self._isi_bahan(t)
        elif jenis == "produk_tambah":
            self.catat(f"Menambah produk {t['nama']}")
            self._tombol_tambah("Daftar Nama Produk").click()
            self._pilih("pr-klasifikasi", t["klasifikasi"])
            self._pilih("pr-rincian", t["rincian"])
            pg.locator("#pr-nama").fill(t["nama"])
            pg.locator("#pr-merek").fill(t["merek"])
            self._simpan()
        elif jenis == "produk_ubah":
            self.catat(f"Memperbarui produk {t['nama']}")
            pg.get_by_role("button", name=_persis(f"Ubah {t['nama']}")).first.click()
            pg.locator("#pr-merek").fill(t["merek"])
            self._simpan()
        elif jenis == "input_bahan":
            self.catat(f"Memasang bahan ke produk {t['produk']}")
            pg.get_by_role("button", name=_persis(f"Input bahan {t['produk']}")).first.click()
            dlg = pg.get_by_role("dialog")
            for b in t["bahan"]:
                kotak = dlg.get_by_role("checkbox", name=_persis(f"{b['nama']} ({LABEL_JENIS.get(b['jenis'], 'Bahan')})"))
                if kotak.get_attribute("data-state") != "checked":
                    kotak.click()
            self._simpan()
        elif jenis == "pembelian":
            self.catat(f"Mencatat pembelian {t['bahan']}")
            pg.get_by_role("button", name=_persis(f"Ubah catatan pembelian {t['bahan']}")).first.click()
            pg.locator("#cp-jumlah").fill(f"{t['jumlah']:g}")
            self._pilih("cp-satuan", t["satuan"])
            pg.locator("#cp-tanggal").fill(t["tanggal"])
            self._simpan()
        elif jenis == "pemeriksaan":
            self.catat(f"Mencatat pemeriksaan {t['bahan']}")
            pg.get_by_role("button", name=_persis(f"Ubah pemeriksaan {t['bahan']}")).first.click()
            pg.locator("#pm-lokasi").fill(t["lokasi"])
            pg.locator("#pm-tanggal").fill(t["tanggal"])
            self._simpan()
        elif jenis == "setuju_komitmen":
            self.buka("komitmen")
            self.catat(f"Menyetujui pernyataan {t['id']} atas persetujuan pengguna")
            self._setuju(t["id"])
        elif jenis == "anggota_tambah":
            self.buka("komitmen")
            self.catat(f"Menambah anggota tim {t['nama']}")
            self._tombol_tambah().click()
            pg.locator("#ak-nama").fill(t["nama"])
            pg.locator("#ak-jabatan").fill(t["jabatan"])
            self._pilih("ak-posisi", LABEL_POSISI.get(t["posisi"], "Anggota"))
            self._simpan()
        elif jenis == "setuju_bebas_babi":
            self.buka("proses")
            self.catat("Menyetujui pernyataan bebas babi atas persetujuan pengguna")
            self._setuju("bebas-babi")
        elif jenis == "petakan":
            self.buka("produk")
            self.catat(f"Memetakan produk {t['produk']} ke fasilitas")
            kotak = pg.get_by_role("checkbox", name=re.compile(rf"^{re.escape(t['produk'])} dibuat di ")).first
            if kotak.get_attribute("data-state") != "checked":
                kotak.click()
            pg.get_by_role("button", name="Simpan", exact=True).click()
            pg.get_by_text("Pemetaan produk tersimpan").first.wait_for()
        else:
            raise ValueError(f"tugas tidak dikenal: {jenis}")

    def _isi_bahan(self, t: dict) -> None:
        """Isi modal bahan, baik tambah maupun ubah. Tipe dan jenis dipilih eksplisit supaya modal ubah ikut sesuai."""
        self._pilih("b-tipe", LABEL_TIPE[t["tipe"]])
        self._pilih("b-jenis", LABEL_JENIS.get(t["jenis"], "Bahan"))
        self.pg.locator("#b-nama").fill(t["nama"])
        self.pg.locator("#b-produsen").fill(t["produsen"])
        if t["tipe"] == "bersertifikat":
            self.pg.locator("#b-sertifikat").fill(t["noSertifikat"])
        self._simpan()

    def _setuju(self, kartu: str) -> None:
        self.pg.evaluate("c => { window.__kalaOperator = { ...(window.__kalaOperator || {}), catatan: c } }", CATATAN_SETUJU)
        self.pg.locator(f"#{kartu}-setuju").click()
        self.pg.locator("button:has-text('Saya setuju'):not([disabled])").first.click()
        self.pg.get_by_text("Disetujui", exact=True).first.wait_for()
        self.pg.evaluate("() => { window.__kalaOperator.catatan = undefined }")


# ---------------------------------------------------------------- pekerja latar belakang
class _Pekerja:
    def __init__(self, pelaksana=None, pembuat_layar=None):
        self._kunci = threading.Condition()
        self._menunggu: dict[str, dict] = {}   # pid -> pekerjaan terbaru (yang lama digantikan)
        self._berjalan: set[str] = set()
        self._riwayat: dict[str, deque] = {}
        self._thread: threading.Thread | None = None
        self._pelaksana = pelaksana or self._pelaksana_playwright
        self._pembuat_layar = pembuat_layar
        self._browser = None
        self._pw = None
        self._henti = False

    # ----- antrean
    def serahkan(self, state, ref: str) -> dict:
        pid = state.get("pengajuan_id")
        if not pid:
            return {"disinkronkan": False, "alasan": "Belum ada draf pengajuan di SIHALAL. Buat drafnya dulu."}
        snap = {k: copy.deepcopy(state.get(k)) for k in KUNCI_STATE}
        with self._kunci:
            self._menunggu[pid] = {"state": snap, "ref": ref, "pid": pid}
            if not self._thread or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="operator-kala", daemon=True)
                self._thread.start()
            self._kunci.notify_all()
        ditahan = [i["nama"] for i in (snap.get("dok") or {}).get("bahan", [])
                   if not sk.bahan_siap_masuk(snap, i) and (i.get("verifikasi") or {}).get("verdict") != "haram"]
        return {
            "disinkronkan": True,
            "mode": "operator_ui",
            "bahan_ditahan_menunggu_konfirmasi": ditahan,
            "pesan": "Operator Kala mengisi formulir SIHALAL di latar belakang dan hasilnya muncul bertahap dalam beberapa detik. "
                     "Jangan menyatakan sudah terisi sebelum pemeriksaan atau lihat_progres menunjukkannya.",
        }

    def tunggu(self, pid: str, batas: float = 60.0) -> bool:
        akhir = time.time() + batas
        with self._kunci:
            while pid in self._menunggu or pid in self._berjalan:
                sisa = akhir - time.time()
                if sisa <= 0:
                    return False
                self._kunci.wait(sisa)
        return True

    def sibuk(self, pid: str) -> bool:
        with self._kunci:
            return pid in self._menunggu or pid in self._berjalan

    def riwayat(self, pid: str) -> list[str]:
        return list(self._riwayat.get(pid, ()))

    def _catat(self, pid: str, teks: str) -> None:
        self._riwayat.setdefault(pid, deque(maxlen=200)).append(f"{datetime.now().strftime('%H:%M:%S')} {teks}")
        logger.info("[%s] %s", pid, teks)

    # ----- loop
    def _loop(self) -> None:
        while True:
            with self._kunci:
                while not self._menunggu and not self._henti:
                    self._kunci.wait()
                if self._henti:
                    break
                pid, kerja = next(iter(self._menunggu.items()))
                del self._menunggu[pid]
                self._berjalan.add(pid)
            try:
                self._kerjakan(kerja)
            except Exception:
                logger.exception("Operator gagal untuk %s", pid)
                self._catat(pid, "Operator gagal, isian yang belum masuk akan dicoba lagi pada sinkron berikutnya")
            finally:
                with self._kunci:
                    self._berjalan.discard(pid)
                    self._kunci.notify_all()
        if self._browser is not None:
            self._browser.close()
            self._pw.stop()
            self._browser = self._pw = None

    def tutup(self) -> None:
        """Hentikan pekerja dan tutup browser. Browser hanya boleh ditutup dari thread yang membukanya."""
        with self._kunci:
            self._henti = True
            self._kunci.notify_all()
        if self._thread:
            self._thread.join(timeout=15)
        self._henti = False

    def _kerjakan(self, kerja: dict) -> None:
        pid, state, ref = kerja["pid"], kerja["state"], kerja["ref"]
        mulai = time.time()
        username = (state.get("akun") or {}).get("username") or ""
        perlu_fallback = True
        if agen_aktif():
            try:
                gagal_agen = self._pelaksana_agen(pid, state, ref, username)
                if not gagal_agen:
                    perlu_fallback = False
                else:
                    self._catat(
                        pid,
                        f"{len(gagal_agen)} langkah belum berhasil oleh agen, beralih ke pelaksana deterministik",
                    )
            except Exception as e:
                logger.warning("Agen operator terkendala untuk %s (%s), fallback ke deterministik", pid, e)
                self._catat(pid, f"Agen operator terkendala ({type(e).__name__}), beralih ke pelaksana deterministik")
        if perlu_fallback:
            for percobaan in (1, 2):
                gagal = self._pelaksana(pid, state, ref, username)
                if not gagal:
                    break
                self._catat(pid, f"{len(gagal)} langkah belum berhasil (percobaan {percobaan})")
        sk.sinkron(state, ref, lewati=BAGIAN_FORMULIR)
        self._catat(pid, f"Selesai dalam {time.time() - mulai:.1f} detik")

    @contextlib.contextmanager
    def _buka_layar(self, pid: str, username: str, ref: str):
        if self._pembuat_layar is not None:
            yield self._pembuat_layar(pid, username, ref)
            return
        from playwright.sync_api import sync_playwright

        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=os.environ.get("OPERATOR_TAMPIL", "") not in ("1", "true"))
        ctx = self._browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script(
            "localStorage.setItem('kawalhalal-sesi', %r);"
            "window.__kalaOperator = { ref: %r, catatan: 'Diinput operator Kala lewat formulir' };" % (username or "operator", ref)
        )
        try:
            yield _Layar(ctx, pid, lambda teks: self._catat(pid, teks))
        finally:
            ctx.close()

    def _pelaksana_agen(self, pid: str, state: dict, ref: str, username: str) -> list[dict]:
        from . import agen_operator

        with self._buka_layar(pid, username, ref) as layar:
            if not rencana(state, layar.baca()):
                return []
            hasil = agen_operator.jalankan_sinkron(state, layar, pid=pid)
            return hasil.get("gagal") or []

    def _pelaksana_playwright(self, pid: str, state: dict, ref: str, username: str) -> list[dict]:
        gagal = []
        with self._buka_layar(pid, username, ref) as layar:
            for t in rencana(state, layar.baca()):
                try:
                    layar.lakukan(t)
                except Exception as e:
                    self._catat(pid, f"Gagal pada {t['aksi']}: {str(e).splitlines()[0][:120]}")
                    gagal.append(t)
                    layar.tab = None
                    if getattr(layar, "pg", None) is not None:
                        layar.pg.keyboard.press("Escape")
        return gagal


_pekerja = _Pekerja()


def serahkan(state, ref: str) -> dict:
    return _pekerja.serahkan(state, ref)


def tunggu(pid: str, batas: float = 60.0) -> bool:
    return _pekerja.tunggu(pid, batas)


def sibuk(pid: str) -> bool:
    return _pekerja.sibuk(pid)


def riwayat(pid: str) -> list[str]:
    return _pekerja.riwayat(pid)


def tutup() -> None:
    _pekerja.tutup()
