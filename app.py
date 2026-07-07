
import os
import re
import io
import zipfile
import tempfile
from pathlib import Path

import fitz
import pandas as pd
import streamlit as st

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ============================================================
# CONFIG
# ============================================================

SHEET_ID = "17jaV5RykOT0SPZXRWoKO_UP7yNrpUq9hIXGAn-6ONPI"
GID = "0"

TEMPLATE_PDF = "TAMPLATE PERUBAHAN SSID AP1.pdf"

COL_NO_TRACKER = 0
COL_SITE_ID = 1
COL_SITE_NAME = 2
COL_FOLDER_LINK = 16

MAX_SITE = 50

# COVER
COVER_CLEAR_RECT = fitz.Rect(35, 350, 560, 485)
COVER_LINE_1_RECT = fitz.Rect(60, 405, 540, 435)
COVER_LINE_2_RECT = fitz.Rect(60, 435, 540, 475)

# PAGE 2
BEFORE_RECT = fitz.Rect(55, 100, 540, 360)
AFTER_RECT  = fitz.Rect(55, 465, 540, 705)

# PAGE 3
GRAFIK_RECT = fitz.Rect(35, 70, 560, 500)

# CAT GIF
CAT_ANGRY = "https://media1.tenor.com/m/Pq5EqV3tfrMAAAAC/cat-scream-cat-screaming.gif"
CAT_PANIC = "https://media1.tenor.com/m/u7nO0ymB7i0AAAAd/exploding-cat-cat.gif"
CAT_HAPPY = "https://media1.tenor.com/m/NPVIhcsXdkAAAAAd/cat-ok.gif"
CAT_SLEEPY = "https://media1.tenor.com/m/Xn3TfHpAJiMAAAAd/scuba-cat-scuba.gif"


# ============================================================
# UI STYLE
# ============================================================

st.set_page_config(
    page_title="RTGS Report Generator",
    page_icon="🐱",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(255, 145, 196, 0.35), transparent 32%),
        radial-gradient(circle at top right, rgba(99, 102, 241, 0.25), transparent 30%),
        linear-gradient(135deg, #fdf2f8 0%, #eef2ff 45%, #fff7ed 100%);
}

.block-container {
    max-width: 1120px;
    padding-top: 2.2rem;
}

.glass-card {
    background: rgba(255, 255, 255, 0.62);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.55);
    border-radius: 28px;
    padding: 26px;
    margin-bottom: 20px;
    box-shadow: 0 18px 55px rgba(31, 38, 135, 0.13);
    animation: fadeIn 0.7s ease-in-out;
}

.hero-title {
    font-size: 44px;
    font-weight: 900;
    color: #2f3342;
    letter-spacing: -1px;
    margin-bottom: 6px;
}

.hero-caption {
    color: #6b7280;
    font-size: 15px;
    margin-bottom: 18px;
}

.cat-row {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
}

.cat-img {
    width: 154px;
    height: 154px;
    object-fit: cover;
    border-radius: 22px;
    box-shadow: 0 12px 28px rgba(0,0,0,0.16);
    transition: all .28s ease;
}

.cat-img:hover {
    transform: scale(1.045) rotate(-1deg);
}

.status-pill {
    display: inline-block;
    padding: 11px 17px;
    border-radius: 999px;
    font-weight: 800;
    margin-bottom: 8px;
}

.status-happy { background:#ecfdf5; color:#047857; }
.status-angry { background:#fef2f2; color:#b91c1c; }
.status-sleepy { background:#eef2ff; color:#4338ca; }
.status-panic { background:#fff7ed; color:#c2410c; }

.small-muted {
    color: #6b7280;
    font-size: 14px;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.55);
    border: 1px solid rgba(255,255,255,0.55);
    padding: 16px;
    border-radius: 18px;
    box-shadow: 0 10px 28px rgba(31,38,135,0.08);
}

.stButton > button {
    border-radius: 14px;
    height: 48px;
    font-weight: 800;
}

.stDownloadButton > button {
    border-radius: 14px;
    height: 48px;
    font-weight: 800;
}

@keyframes fadeIn {
    from {opacity:0; transform: translateY(16px);}
    to {opacity:1; transform: translateY(0);}
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# CAT STATUS
# ============================================================

def get_cat_status(status):
    if status == "happy":
        return CAT_HAPPY, "😺 Happy Cat", "Semua aman. PDF siap dibuat.", "status-happy"
    if status == "angry":
        return CAT_ANGRY, "😾 Angry Cat", "Ada site/foto yang perlu dicek.", "status-angry"
    if status == "panic":
        return CAT_PANIC, "🙀 Panic Cat", "Ada error atau input belum lengkap.", "status-panic"
    return CAT_SLEEPY, "😴 Sleepy Cat", "Menunggu input Site ID.", "status-sleepy"


def show_hero(status="sleepy"):
    # Bagian status kucing di bawah judul DIHAPUS sesuai request.
    # Parameter status tetap dibiarkan supaya bagian preview/generate tidak perlu diubah banyak.
    st.markdown("""
    <div class="hero-title">🐱 RTGS Report Generator</div>
    <div class="hero-caption">Generate PDF Perubahan SSID AP1 dari Google Sheet + Google Drive</div>
    """, unsafe_allow_html=True)


def show_cat_gallery():
    st.markdown(f"""
    <div class="glass-card">
        <div class="cat-row">
            <img src="{CAT_ANGRY}" class="cat-img">
            <img src="{CAT_PANIC}" class="cat-img">
            <img src="{CAT_HAPPY}" class="cat-img">
            <img src="{CAT_SLEEPY}" class="cat-img">
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# GOOGLE SERVICE ACCOUNT
# ============================================================

@st.cache_resource
def get_google_services():
    creds_dict = dict(st.secrets["gcp_service_account"])

    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]

    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )

    drive_service = build("drive", "v3", credentials=creds)
    return drive_service


drive_service = get_google_services()


# ============================================================
# LOAD DATABASE
# ============================================================

@st.cache_data(ttl=300)
def load_database():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    df = pd.read_csv(url, dtype=str).fillna("")
    return df


try:
    df = load_database()
except Exception as e:
    show_hero("panic")
    st.error(f"Gagal membaca database Google Sheet: {e}")
    st.stop()


# ============================================================
# HELPER
# ============================================================

def parse_site_input(text):
    items = re.split(r"[\n,;]+", text)
    return [x.strip().upper() for x in items if x.strip()]


def is_valid_site_id(site_id):
    # Pola dibuat fleksibel untuk Site ID seperti AM16224669368205N.
    return bool(re.match(r"^[A-Z]{2}[A-Z0-9]{8,30}$", str(site_id).strip().upper()))


def clean_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "", str(text)).strip()


def extract_folder_id(link):
    link = str(link)

    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", link)
    if match:
        return match.group(1)

    match = re.search(r"id=([a-zA-Z0-9_-]+)", link)
    if match:
        return match.group(1)

    return None


def find_site(site_id):
    site_id = str(site_id).strip().upper()

    for _, row in df.iterrows():
        sheet_site_id = str(row.iloc[COL_SITE_ID]).strip().upper()

        if sheet_site_id == site_id:
            return {
                "no_tracker": str(row.iloc[COL_NO_TRACKER]).strip(),
                "site_id": str(row.iloc[COL_SITE_ID]).strip(),
                "site_name": str(row.iloc[COL_SITE_NAME]).strip(),
                "folder_link": str(row.iloc[COL_FOLDER_LINK]).strip()
            }

    return None


def list_drive_files(folder_id):
    files = []
    page_token = None

    while True:
        response = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return files


def find_required_images(folder_id):
    files = list_drive_files(folder_id)

    before = None
    after = None
    grafik = None

    for f in files:
        name = f["name"].lower()

        if "before" in name and before is None:
            before = f
        elif "after" in name and after is None:
            after = f
        elif "grafik" in name and grafik is None:
            grafik = f

    return before, after, grafik


def filename_site_match(site_id, file_obj):
    """
    Validasi ringan dari nama file.
    Jika nama file mencantumkan Site ID, harus sama dengan input.
    Jika nama file tidak mencantumkan Site ID, statusnya warning, bukan otomatis gagal.
    """
    if not file_obj:
        return False, "File tidak ada"

    name = file_obj.get("name", "")
    normalized_name = re.sub(r"[^A-Z0-9]", "", name.upper())
    normalized_site = re.sub(r"[^A-Z0-9]", "", site_id.upper())

    if normalized_site in normalized_name:
        return True, "Nama file sesuai Site ID"

    # Cari kemungkinan Site ID lain di nama file
    candidates = re.findall(r"[A-Z]{2}[A-Z0-9]{8,30}", normalized_name)
    if candidates:
        return False, f"Nama file kemungkinan berisi Site ID lain: {', '.join(candidates[:3])}"

    return None, "Nama file tidak berisi Site ID, perlu cek OCR/visual"


def download_drive_file(file_id, output_path):
    request = drive_service.files().get_media(fileId=file_id)

    with io.FileIO(output_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False

        while not done:
            _, done = downloader.next_chunk()

    return output_path


def optional_ocr_text(image_path):
    """
    OCR opsional.
    Agar aktif di Streamlit Cloud, tambahkan dependency:
    - pytesseract
    - pillow
    dan pastikan tesseract tersedia di environment.
    Jika tidak tersedia, fungsi ini otomatis return kosong.
    """
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(image_path))
        return text or ""
    except Exception:
        return ""


def ocr_site_match(site_id, image_path):
    text = optional_ocr_text(image_path)

    if not text:
        return None, "OCR tidak aktif / teks tidak terbaca"

    normalized_text = re.sub(r"[^A-Z0-9]", "", text.upper())
    normalized_site = re.sub(r"[^A-Z0-9]", "", site_id.upper())

    if normalized_site in normalized_text:
        return True, "OCR sesuai Site ID"

    candidates = re.findall(r"[A-Z]{2}[A-Z0-9]{8,30}", normalized_text)
    if candidates:
        return False, f"OCR menemukan Site ID lain: {', '.join(candidates[:3])}"

    return False, "OCR tidak menemukan Site ID input"


def validate_capture(site_id, file_obj, image_path=None):
    """
    Deteksi otomatis capture salah:
    1. Cek dari nama file.
    2. Jika image_path ada, coba OCR.
    Status:
    - OK: sesuai
    - WARNING: belum bisa dipastikan
    - ERROR: tidak sesuai / file hilang
    """
    if not file_obj:
        return "ERROR", "File tidak ditemukan"

    name_match, name_msg = filename_site_match(site_id, file_obj)

    if image_path:
        ocr_match, ocr_msg = ocr_site_match(site_id, image_path)
    else:
        ocr_match, ocr_msg = None, "OCR dicek saat generate / jika file diunduh"

    if name_match is True or ocr_match is True:
        return "OK", f"{name_msg}; {ocr_msg}"

    if name_match is False or ocr_match is False:
        return "ERROR", f"{name_msg}; {ocr_msg}"

    return "WARNING", f"{name_msg}; {ocr_msg}"


def insert_image(page, image_path, rect):
    page.insert_image(
        rect,
        filename=str(image_path),
        keep_proportion=True
    )


# ============================================================
# PREVIEW
# ============================================================

def get_site_preview(site_id):
    site = find_site(site_id)

    if not site:
        return {
            "Status": "😾 Check",
            "Site ID": site_id,
            "Nama Site": "-",
            "Folder": "❌ Tidak ada",
            "Before": "❌ Tidak dicek",
            "After": "❌ Tidak dicek",
            "Grafik": "❌ Tidak dicek",
            "Catatan": "Site ID tidak ditemukan di database"
        }

    folder_id = extract_folder_id(site["folder_link"])
    if not folder_id:
        return {
            "Status": "😾 Check",
            "Site ID": site_id,
            "Nama Site": site["site_name"],
            "Folder": "❌ Link folder invalid",
            "Before": "❌ Tidak dicek",
            "After": "❌ Tidak dicek",
            "Grafik": "❌ Tidak dicek",
            "Catatan": "Folder ID tidak valid di kolom Q"
        }

    try:
        before_file, after_file, grafik_file = find_required_images(folder_id)

        validations = {
            "Before": validate_capture(site_id, before_file),
            "After": validate_capture(site_id, after_file),
            "Grafik": validate_capture(site_id, grafik_file),
        }

        has_error = any(v[0] == "ERROR" for v in validations.values())
        has_warning = any(v[0] == "WARNING" for v in validations.values())

        def fmt(label):
            status, msg = validations[label]
            if status == "OK":
                return "✅ Ada & sesuai"
            if status == "WARNING":
                return "⚠️ Ada, belum pasti"
            return "❌ Bermasalah"

        notes = []
        for label, (status, msg) in validations.items():
            if status != "OK":
                notes.append(f"{label}: {msg}")

        if not notes:
            notes = ["Siap generate"]

        return {
            "Status": "😺 Ready" if not has_error else "😾 Check",
            "Site ID": site["site_id"],
            "Nama Site": site["site_name"],
            "Folder": "✅ Valid",
            "Before": fmt("Before"),
            "After": fmt("After"),
            "Grafik": fmt("Grafik"),
            "Catatan": " | ".join(notes)
        }

    except Exception as e:
        return {
            "Status": "🙀 Error",
            "Site ID": site_id,
            "Nama Site": site["site_name"],
            "Folder": "⚠️ Error akses",
            "Before": "❌ Tidak dicek",
            "After": "❌ Tidak dicek",
            "Grafik": "❌ Tidak dicek",
            "Catatan": str(e)
        }


# ============================================================
# GENERATE PDF
# ============================================================

def generate_pdf(site, work_dir, output_dir):
    no_tracker = site["no_tracker"]
    site_id = site["site_id"]
    site_name = site["site_name"]
    folder_link = site["folder_link"]

    folder_id = extract_folder_id(folder_link)

    if not folder_id:
        raise Exception("Folder ID tidak valid di kolom Q")

    before_file, after_file, grafik_file = find_required_images(folder_id)

    if before_file is None:
        raise Exception("File *before tidak ditemukan")

    if after_file is None:
        raise Exception("File *after tidak ditemukan")

    if grafik_file is None:
        raise Exception("File grafik tidak ditemukan")

    site_work_dir = Path(work_dir) / site_id
    site_work_dir.mkdir(parents=True, exist_ok=True)

    before_path = site_work_dir / "before.png"
    after_path = site_work_dir / "after.png"
    grafik_path = site_work_dir / "grafik.png"

    download_drive_file(before_file["id"], str(before_path))
    download_drive_file(after_file["id"], str(after_path))
    download_drive_file(grafik_file["id"], str(grafik_path))

    # Validasi capture setelah file di-download
    before_status, before_msg = validate_capture(site_id, before_file, before_path)
    after_status, after_msg = validate_capture(site_id, after_file, after_path)
    grafik_status, grafik_msg = validate_capture(site_id, grafik_file, grafik_path)

    bad_capture = []
    if before_status == "ERROR":
        bad_capture.append(f"Before salah: {before_msg}")
    if after_status == "ERROR":
        bad_capture.append(f"After salah: {after_msg}")
    if grafik_status == "ERROR":
        bad_capture.append(f"Grafik salah: {grafik_msg}")

    if bad_capture:
        raise Exception(" | ".join(bad_capture))

    output_name = clean_filename(f"{no_tracker}. {site_id} {site_name}.pdf")
    output_pdf = Path(output_dir) / output_name

    doc = fitz.open(TEMPLATE_PDF)

    # ========================================================
    # PAGE 1 - COVER
    # ========================================================
    page1 = doc[0]

    page1.draw_rect(
        COVER_CLEAR_RECT,
        color=(1, 1, 1),
        fill=(1, 1, 1),
        overlay=True
    )

    page1.insert_textbox(
        COVER_LINE_1_RECT,
        f"{no_tracker}. {site_id}",
        fontsize=16,
        fontname="helv",
        align=1,
        color=(0, 0, 0)
    )

    page1.insert_textbox(
        COVER_LINE_2_RECT,
        site_name,
        fontsize=16,
        fontname="helv",
        align=1,
        color=(0, 0, 0)
    )

    # ========================================================
    # PAGE 2 - BEFORE & AFTER
    # ========================================================
    page2 = doc[1]

    insert_image(page2, before_path, BEFORE_RECT)
    insert_image(page2, after_path, AFTER_RECT)

    # ========================================================
    # PAGE 3 - GRAFIK
    # ========================================================
    page3 = doc[2]

    insert_image(page3, grafik_path, GRAFIK_RECT)

    doc.save(str(output_pdf))
    doc.close()

    return str(output_pdf)


# ============================================================
# APP
# ============================================================

show_hero("sleepy")
show_cat_gallery()

site_input = st.text_area(
    "Masukkan Site ID maksimal 50",
    height=170,
    placeholder="AM16224669368205N\nAM16224669328205N"
)

site_ids_now = parse_site_input(site_input)
unique_count = len(set(site_ids_now))
duplicate_count = len(site_ids_now) - unique_count

# Bagian metric/card Site Input, Limit, Duplikat, Database row DIHAPUS sesuai request.

col1, col2 = st.columns(2)

with col1:
    preview_btn = st.button("🔍 Preview Site", use_container_width=True)

with col2:
    generate_btn = st.button("🚀 Generate PDF", type="primary", use_container_width=True)


if preview_btn:
    site_ids = parse_site_input(site_input)

    if len(site_ids) == 0:
        show_hero("panic")
        st.warning("Site ID belum diisi.")
    elif len(site_ids) > MAX_SITE:
        show_hero("angry")
        st.error(f"Maksimal {MAX_SITE} Site ID.")
    else:
        preview_data = []
        progress = st.progress(0)
        status_box = st.empty()

        for i, site_id in enumerate(site_ids, start=1):
            status_box.info(f"😺 Mengecek {site_id} ({i}/{len(site_ids)})...")
            preview_data.append(get_site_preview(site_id))
            progress.progress(i / len(site_ids))

        has_error = any(row["Status"] != "😺 Ready" for row in preview_data)

        st.subheader("📋 Preview Site Lengkap Sebelum Generate")
        st.dataframe(preview_data, use_container_width=True, hide_index=True)

        if has_error:
            st.warning("Ada site yang perlu dicek. Perhatikan kolom Before/After/Grafik dan Catatan.")
        else:
            st.success("Semua site siap generate PDF.")


if generate_btn:
    site_ids = parse_site_input(site_input)

    if len(site_ids) == 0:
        show_hero("panic")
        st.warning("Site ID belum diisi.")
        st.stop()

    if len(site_ids) > MAX_SITE:
        show_hero("angry")
        st.error(f"Maksimal {MAX_SITE} Site ID.")
        st.stop()

    generated_files = []
    log = []

    st.subheader("🚀 Proses Generate PDF")

    progress = st.progress(0)
    status = st.empty()

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir) / "work"
        output_dir = Path(tmpdir) / "output"

        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, site_id in enumerate(site_ids, start=1):
            status.info(f"😺 Memproses {site_id} ({i}/{len(site_ids)})...")

            try:
                site = find_site(site_id)

                if not site:
                    log.append(f"FAILED - {site_id}: Site ID tidak ditemukan di database")
                    continue

                pdf_path = generate_pdf(site, work_dir, output_dir)
                generated_files.append(pdf_path)
                log.append(f"DONE - {site_id}: {os.path.basename(pdf_path)}")

            except Exception as e:
                log.append(f"FAILED - {site_id}: {str(e)}")

            progress.progress(i / len(site_ids))

        if not generated_files:
            st.error("Tidak ada PDF yang berhasil dibuat.")
            st.subheader("Log")
            st.code("\n".join(log))
            st.stop()

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for pdf in generated_files:
                z.write(pdf, os.path.basename(pdf))

            z.writestr("log.txt", "\n".join(log))

        zip_buffer.seek(0)

        failed_count = len([x for x in log if x.startswith("FAILED")])

        c1, c2, c3 = st.columns(3)
        c1.metric("Berhasil", len(generated_files))
        c2.metric("Gagal", failed_count)
        c3.metric("Total", len(site_ids))

        st.success(f"{len(generated_files)} PDF berhasil dibuat.")

        st.download_button(
            label="⬇️ Download ZIP",
            data=zip_buffer,
            file_name="RTGS_REPORT_RESULT.zip",
            mime="application/zip",
            use_container_width=True
        )

        st.subheader("Log")
        st.code("\n".join(log))
