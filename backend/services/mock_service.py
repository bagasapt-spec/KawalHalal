import datetime
import uuid
from typing import Any, Dict, Optional


def get_mock_dossier(wa_number: str) -> Dict[str, Any]:
    """
    Generate a comprehensive mock dossier dataset for Frontend SiHalal Mockup auto-filling.
    Includes business details, ingredients, halal status, supplier info, and dummy image URLs.
    """
    clean_wa = wa_number.replace("whatsapp:", "").strip()
    formatted_wa = f"+{clean_wa.lstrip('+')}"

    return {
        "status": "success",
        "wa_number": formatted_wa,
        "business_name": "Bakso & Soto Barokah Pak Joko",
        "business_profile": {
            "business_name": "Bakso & Soto Barokah Pak Joko",
            "owner_name": "Joko Susanto",
            "phone_number": formatted_wa,
            "nib": "1284000392817",
            "business_scale": "Usaha Mikro (UMK)",
            "address": "Jl. Gegerkalong Hilir No. 45, RT 02 / RW 04, Sukasari, Kota Bandung, Jawa Barat 40152",
            "business_type": "Penyedia Makanan dan Minuman (Restoran/Warung Makan)",
            "product_name": "Bakso Daging Sapi & Soto Ayam Kampung",
            "registration_track": "Self-Declare (P3H)",
            "submission_status": "DOKUMEN_LENGKAP_SIAP_SUBMIT",
            "p3h_companion": {
                "name": "Sarah Nurhasanah, S.Pt.",
                "registration_number": "P3H-3273-00921",
                "institution": "LP3H Universitas Padjadjaran (UNPAD)",
                "contact": "+6281987654321",
            },
        },
        "halal_status": "TERVERIFIKASI_LENGKAP",
        "summary": {
            "total_ingredients": 7,
            "approved_count": 7,
            "critical_animal_ingredients": 2,
            "exempt_ingredients_kma1360": 3,
            "bpjph_certified_ingredients": 2,
            "compliance_score": 100.0,
            "is_ready_for_sihalal": True,
        },
        "ingredients": [
            {
                "id": "ing-001",
                "name": "Daging Sapi Segar (Has Luar)",
                "category": "Bahan Hewani Sembelihan",
                "halal_status": "TERVERIFIKASI",
                "verification_method": "RPH Provenance Mapping",
                "cert_id": "ID3222000019283",
                "supplier_info": {
                    "stall_name": "Lapak Daging Barokah Pak Slamet",
                    "market_name": "Pasar Tradisional Ciroyom Bandung",
                    "stall_location": "Blok B No. 12",
                    "slaughterhouse_name": "Rumah Potong Hewan (RPH) Ciroyom",
                    "halal_certificate": "ID3222000019283",
                    "valid_until": "2027-11-15",
                    "status": "TERDAFTAR_AKTIF",
                },
                "evidence_url": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=600&q=80",
                "notes": "Telah diverifikasi sesuai bukti surat distribusi Rumah Potong Hewan (RPH) Ciroyom.",
            },
            {
                "id": "ing-002",
                "name": "Daging Dada Ayam Fillet Segar",
                "category": "Bahan Hewani Sembelihan",
                "halal_status": "TERVERIFIKASI",
                "verification_method": "RPHU Provenance Mapping",
                "cert_id": "ID3211000188921",
                "supplier_info": {
                    "stall_name": "Lapak Ayam Segar Ibu Eni",
                    "market_name": "Pasar Tradisional Ciroyom Bandung",
                    "stall_location": "Blok A No. 05",
                    "slaughterhouse_name": "RPHU Ciroyom PD Bersama",
                    "halal_certificate": "ID3211000188921",
                    "valid_until": "2027-08-20",
                    "status": "TERDAFTAR_AKTIF",
                },
                "evidence_url": "https://images.unsplash.com/photo-1587593810167-a84920ea0781?auto=format&fit=crop&w=600&q=80",
                "notes": "Rantai pasok unggas terverifikasi dari RPHU terakreditasi.",
            },
            {
                "id": "ing-003",
                "name": "Tepung Tapioka / Sagu Aren",
                "category": "Bahan Alami Nabati",
                "halal_status": "EXEMPT",
                "verification_method": "KMA 1360/2021 (Positive List)",
                "cert_id": "KMA-1360-LAMP-II",
                "supplier_info": {
                    "stall_name": "Toko Bahan Kue Sinar Rejeki",
                    "market_name": "Pasar Baru Bandung",
                },
                "evidence_url": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=600&q=80",
                "notes": "Bahan nabati murni non-kritis sesuai Keputusan Menteri Agama No. 1360/2021 Lampiran II.",
            },
            {
                "id": "ing-004",
                "name": "Bawang Putih Kating & Bawang Merah Brebes",
                "category": "Bahan Alami Nabati (Rempah Murni)",
                "halal_status": "EXEMPT",
                "verification_method": "KMA 1360/2021 (Positive List)",
                "cert_id": "KMA-1360-LAMP-I",
                "supplier_info": {
                    "stall_name": "Lapak Sayur Segar Bu Tini",
                    "market_name": "Pasar Tradisional Ciroyom Bandung",
                },
                "evidence_url": "https://images.unsplash.com/photo-1540148426945-6cf22a6b2383?auto=format&fit=crop&w=600&q=80",
                "notes": "Sayuran dan bumbu rempah murni tanpa perlakuan fermentasi/kimiawi.",
            },
            {
                "id": "ing-005",
                "name": "Garam Laut Beriodium",
                "category": "Mineral Alami",
                "halal_status": "EXEMPT",
                "verification_method": "KMA 1360/2021 (Positive List)",
                "cert_id": "KMA-1360-LAMP-III",
                "supplier_info": {
                    "stall_name": "Toko Kelontong Berkah",
                    "market_name": "Sukasari Bandung",
                },
                "evidence_url": "https://images.unsplash.com/photo-1518110925495-5fe2fda0442c?auto=format&fit=crop&w=600&q=80",
                "notes": "Garam tambak alami non-kritis.",
            },
            {
                "id": "ing-006",
                "name": "Bumbu Kaldu Rasa Ayam (Masako)",
                "category": "Bahan Olahan Bermerek",
                "halal_status": "TERDAFTAR_BPJPH",
                "verification_method": "Registri Pangkalan Data BPJPH",
                "cert_id": "ID00410000008540420",
                "supplier_info": {
                    "manufacturer": "PT Ajinomoto Indonesia",
                    "brand": "Masako",
                    "valid_until": "2028-06-30",
                    "status": "TERBIT_AKTIF",
                },
                "evidence_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=600&q=80",
                "notes": "Nomor sertifikat cocok dengan pangkalan data BPJPH terpusat.",
            },
            {
                "id": "ing-007",
                "name": "Kecap Manis (Bango)",
                "category": "Bahan Olahan Bermerek",
                "halal_status": "TERDAFTAR_BPJPH",
                "verification_method": "Registri Pangkalan Data BPJPH",
                "cert_id": "ID00410000000100120",
                "supplier_info": {
                    "manufacturer": "PT Unilever Indonesia Tbk",
                    "brand": "Bango",
                    "valid_until": "2028-12-18",
                    "status": "TERBIT_AKTIF",
                },
                "evidence_url": "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=600&q=80",
                "notes": "Kedelai hitam dan gula kelapa bersertifikat halal resmi.",
            },
        ],
        "supplier_info": {
            "primary_meat_supplier": "Lapak Daging Barokah Pak Slamet (Pasar Ciroyom)",
            "primary_poultry_supplier": "Lapak Ayam Segar Ibu Eni (Pasar Ciroyom)",
            "accredited_slaughterhouse": "Rumah Potong Hewan (RPH) Ciroyom Kota Bandung",
        },
        "dummy_image_urls": {
            "kitchen_baseline_url": "https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&fit=crop&w=800&q=80",
            "kitchen_latest_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=800&q=80",
            "dossier_preview_thumbnail": "https://images.unsplash.com/photo-1568667256549-094345857637?auto=format&fit=crop&w=800&q=80",
            "raw_meat_evidence": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=600&q=80",
            "packaged_seasoning_evidence": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=600&q=80",
        },
        "kitchen_watchdog_audit": {
            "status": "CLEAR_NO_DRIFT",
            "conformity_score": 0.98,
            "detected_anomalies": [],
            "last_inspected_at": "2026-10-22T03:30:00Z",
            "notes": "Semua bahan dapur identik dengan profil registrasi. Tidak ada indikasi substitusi minyak curah atau daging tak berizin.",
        },
        "dossier_export": {
            "dossier_id": f"DOS-2026-{uuid.uuid4().hex[:8].upper()}",
            "pdf_download_url": "https://pxetupnmnhxuljionris.supabase.co/storage/v1/object/public/media/mockup/dossier_sihalal_pak_joko_preview.pdf",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    }


def mock_upload_document(
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    file_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Simulate document upload for Frontend mockup without writing to database or storage.
    """
    file_id = f"doc-{uuid.uuid4().hex[:12]}"
    clean_filename = filename or f"sihalal_dossier_{file_id}.pdf"
    clean_content_type = content_type or "application/pdf"

    mock_url = f"https://pxetupnmnhxuljionris.supabase.co/storage/v1/object/public/media/mockup/{clean_filename}"

    return {
        "status": "success",
        "message": "Dokumen berhasil diunggah (Simulasi Mockup SiHalal)",
        "file_id": file_id,
        "file_name": clean_filename,
        "content_type": clean_content_type,
        "file_size": file_size or 245760,
        "document_url": mock_url,
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
