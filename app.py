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

COL_NO_TRACKER = 0    # Kolom A
COL_SITE_ID = 2       # Kolom C
COL_SITE_NAME = 3     # Kolom D
COL_FOLDER_LINK = 17  # Kolom R

MAX_SITE = 50

# COVER
COVER_CLEAR_RECT = fitz.Rect(35, 350, 560, 485)
COVER_LINE_1_RECT = fitz.Rect(60, 405, 540, 435)
COVER_LINE_2_RECT = fitz.Rect(60, 435, 540, 475)

# PAGE 2
BEFORE_RECT = fitz.Rect(55, 100, 540, 360)
AFTER_RECT = fitz.Rect(55, 465, 540, 705)

# PAGE 3
GRAFIK_SINGLE_RECT = fitz.Rect(35, 70, 560, 500)
GRAFIK_1_RECT = fitz.Rect(55, 100, 540, 360)
GRAFIK_2_RECT = fitz.Rect(55, 465, 540, 705)

# CAT GIF
CAT_ANGRY = "https://media1.tenor.com/m/Pq5EqV3tfrMAAAAC/cat-scream-cat-screaming.gif"
CAT_PANIC = "https://media1.tenor.com/m/u7nO0ymB7i0AAAAd/exploding-cat-cat.gif"
CAT_HAPPY = "https://media1.tenor.com/m/NPVIhcsXdkAAAAAd/cat-ok.gif"
CAT_SLEEPY = "https://media1.tenor.com/m/Xn3TfHpAJiMAAAAd/scuba-cat-scuba.gif"


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="SSID RTGS Report Generator",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# UI STYLE
# ============================================================

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        height: 0rem !important;
        background: transparent !important;
    }

    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    #MainMenu,
    footer {
        visibility: hidden !important;
        display: none !important;
        height: 0rem !important;
    }

    section[data-testid="stSidebar"] {
        display: none !important;
    }

    .main .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 3rem !important;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255,145,196,.35), transparent 32%),
            radial-gradient(circle at top right, rgba(99,102,241,.25), transparent 30%),
            linear-gradient(135deg, #fdf2f8 0%, #eef2ff 45%, #fff7ed 100%);
    }

    .block-container {
        max-width: 1120px;
        padding-top: 0.8rem !important;
        padding-left: 1.2rem;
        padding-right: 1.2rem;
    }

    .glass-card {
        background: rgba(255,255,255,.62);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255,255,255,.55);
        border-radius: 28px;
        padding: 26px;
        margin-bottom: 20px;
        box-shadow: 0 18px 55px rgba(31,38,135,.13);
        animation: fadeIn .7s ease-in-out;
    }

    .hero-title {
        font-size: 44px;
        font-weight: 900;
        color: #2f3342;
        letter-spacing: -1px;
        margin: 0 0 6px 0;
        line-height: 1.08;
    }

    .hero-caption {
        color: #6b7280;
        font-size: 15px;
        margin-bottom: 18px;
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
        background: rgba(255,255,255,.55);
        border: 1px solid rgba(255,255,255,.55);
        padding: 16px;
        border-radius: 18px;
        box-shadow: 0 10px 28px rgba(31,38,135,.08);
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 14px;
        height: 48px;
        font-weight: 800;
    }

    .cat-gallery-card {
        background: rgba(255,255,255,.66);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255,255,255,.62);
        border-radius: 28px;
        padding: 22px 26px;
        margin: 22px auto 26px auto;
        width: fit-content;
        max-width: 100%;
        box-shadow: 0 18px 55px rgba(31,38,135,.12);
        animation: fadeIn .7s ease-in-out;
        overflow: hidden;
    }

    .cat-row-clean {
        display: flex;
        gap: 18px;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
    }

    .cat-img-clean {
        width: 165px;
        height: 165px;
        object-fit: cover;
        border-radius: 24px;
        box-shadow: 0 12px 28px rgba(0,0,0,.15);
        transition: all .28s ease;
    }

    .cat-img-clean:hover {
        transform: scale(1.045) rotate(-1deg);
    }

    textarea {
        border-radius: 18px !important;
    }

    div[data-testid="stAlert"] {
        border-radius: 14px !important;
    }

    @keyframes fadeIn {
        from {opacity:0; transform:translateY(16px);}
        to {opacity:1; transform:translateY(0);}
    }

    @media (max-width: 768px) {
        .hero-title { font-size: 32px; }
        .cat-img-clean { width:130px; height:130px; }
        .cat-gallery-card { padding:16px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CAT UI
# ============================================================

def get_cat_status(status):
    if status == "happy":
        return CAT_HAPPY, "😺 Happy Cat", "Semua aman. PDF siap dibuat.", "status-happy"
    if status == "angry":
        return CAT_ANGRY, "😾 Angry Cat", "Ada site atau foto yang perlu dicek.", "status-angry"
    if status == "panic":
        return CAT_PANIC, "🙀 Panic Cat", "Ada error atau input belum lengkap.", "status-panic"
    return CAT_SLEEPY, "😴 Sleepy Cat", "Menunggu input Site ID.", "status-sleepy"


def show_hero():
    st.markdown(
        """
        <div class="hero-title">🐱 SSID RTGS Report Generator</div>
        <div class="hero-caption">
            Generate PDF Perubahan SSID AP1 dari Google Sheet + Google Drive
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_result_cat_card(status="sleepy"):
    img, title, desc, css = get_cat_status(status)

    st.markdown(
        f"""
        <div class="glass-card">
            <div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap;">
                <img src="{img}"
                     style="width:165px;height:165px;object-fit:cover;
                            border-radius:24px;
                            box-shadow:0 12px 28px rgba(0,0,0,.15);">
                <div>
                    <div class="status-pill {css}">{title}</div>
                    <div class="small-muted">{desc}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_cat_gallery():
    st.markdown(
        f"""
        <div class="cat-gallery-card">
            <div class="cat-row-clean">
                <img src="{CAT_ANGRY}" class="cat-img-clean">
                <img src="{CAT_PANIC}" class="cat-img-clean">
                <img src="{CAT_HAPPY}" class="cat-img-clean">
                <img src="{CAT_SLEEPY}" class="cat-img-clean">
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        scopes=scopes,
    )

    return build(
        "drive",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )


drive_service = get_google_services()


# ============================================================
# LOAD DATABASE
# ============================================================

@st.cache_data(ttl=300)
def load_database():
    url = (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SHEET_ID}/export?format=csv&gid={GID}"
    )

    return pd.read_csv(url, dtype=str).fillna("")


try:
    df = load_database()
except Exception as error:
    show_hero()
    show_result_cat_card("panic")
    st.error(f"Gagal membaca database Google Sheet: {error}")
    st.stop()


# ============================================================
# HELPERS
# ============================================================

def parse_site_input(text):
    items = re.split(r"[\n,;]+", str(text))

    results = []
    seen = set()

    for item in items:
        site_id = item.strip().upper()

        if site_id and site_id not in seen:
            results.append(site_id)
            seen.add(site_id)

    return results


def is_valid_site_id(site_id):
    return bool(
        re.fullmatch(
            r"[A-Z]{2}[A-Z0-9]{8,30}",
            str(site_id).strip().upper(),
        )
    )


def clean_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "", str(text)).strip()


def extract_folder_id(link):
    link = str(link).strip()

    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", link)
    if match:
        return match.group(1)

    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", link)
    if match:
        return match.group(1)

    return None


def find_site(site_id):
    normalized_site_id = str(site_id).strip().upper()

    for _, row in df.iterrows():
        sheet_site_id = str(row.iloc[COL_SITE_ID]).strip().upper()

        if sheet_site_id == normalized_site_id:
            return {
                "no_tracker": str(row.iloc[COL_NO_TRACKER]).strip(),
                "site_id": str(row.iloc[COL_SITE_ID]).strip(),
                "site_name": str(row.iloc[COL_SITE_NAME]).strip(),
                "folder_link": str(row.iloc[COL_FOLDER_LINK]).strip(),
            }

    return None


def list_drive_files(folder_id):
    files = []
    page_token = None

    while True:
        response = (
            drive_service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,size)",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=1000,
            )
            .execute()
        )

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return files


def find_required_images(folder_id):
    files = list_drive_files(folder_id)

    before = None
    after = None
    grafik_single = None
    grafik_1 = None
    grafik_2 = None

    for file_info in files:
        file_name = file_info.get("name", "").lower().strip()
        normalized_name = re.sub(r"[\s_-]+", " ", file_name).strip()

        if "before" in file_name and before is None:
            before = file_info
            continue

        if "after" in file_name and after is None:
            after = file_info
            continue

        if re.search(r"\bgrafik\s*1\b", normalized_name):
            if grafik_1 is None:
                grafik_1 = file_info
            continue

        if re.search(r"\bgrafik\s*2\b", normalized_name):
            if grafik_2 is None:
                grafik_2 = file_info
            continue

        if "grafik" in file_name and grafik_single is None:
            grafik_single = file_info

    return before, after, grafik_single, grafik_1, grafik_2


def download_drive_file(file_id, output_path):
    request = drive_service.files().get_media(fileId=file_id)

    with io.FileIO(output_path, "wb") as file_handle:
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False

        while not done:
            _, done = downloader.next_chunk()

    return output_path


# ============================================================
# VALIDATION
# ============================================================

def filename_site_match(site_id, file_obj):
    if not file_obj:
        return False, "File tidak ditemukan"

    name = file_obj.get("name", "")
    normalized_name = re.sub(r"[^A-Z0-9]", "", name.upper())
    normalized_site = re.sub(r"[^A-Z0-9]", "", str(site_id).upper())

    if normalized_site in normalized_name:
        return True, "Nama file sesuai Site ID"

    candidates = re.findall(r"[A-Z]{2}[A-Z0-9]{8,30}", normalized_name)

    other_sites = [
        candidate
        for candidate in candidates
        if candidate != normalized_site
    ]

    if other_sites:
        return (
            False,
            f"Nama file kemungkinan berisi Site ID lain: {', '.join(other_sites[:3])}",
        )

    return None, "Nama file tidak berisi Site ID"


def optional_ocr_text(image_path):
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(image_path)) or ""
    except Exception:
        return ""


def ocr_site_match(site_id, image_path):
    text = optional_ocr_text(image_path)

    if not text:
        return None, "OCR tidak aktif atau teks tidak terbaca"

    normalized_text = re.sub(r"[^A-Z0-9]", "", text.upper())
    normalized_site = re.sub(r"[^A-Z0-9]", "", str(site_id).upper())

    if normalized_site in normalized_text:
        return True, "OCR sesuai Site ID"

    candidates = re.findall(r"[A-Z]{2}[A-Z0-9]{8,30}", normalized_text)

    other_sites = [
        candidate
        for candidate in candidates
        if candidate != normalized_site
    ]

    if other_sites:
        return (
            False,
            f"OCR menemukan Site ID lain: {', '.join(other_sites[:3])}",
        )

    return None, "OCR tidak menemukan Site ID yang dapat dipastikan"


def validate_capture(site_id, file_obj, image_path=None):
    if not file_obj:
        return "ERROR", "File tidak ditemukan"

    name_match, name_message = filename_site_match(site_id, file_obj)

    ocr_match = None
    ocr_message = "OCR belum dijalankan"

    if image_path:
        ocr_match, ocr_message = ocr_site_match(site_id, image_path)

    if name_match is True or ocr_match is True:
        return "OK", f"{name_message}; {ocr_message}"

    if name_match is False or ocr_match is False:
        return "ERROR", f"{name_message}; {ocr_message}"

    return "WARNING", f"{name_message}; {ocr_message}"


def insert_image(page, image_path, rect):
    page.insert_image(
        rect,
        filename=str(image_path),
        keep_proportion=True,
        overlay=True,
    )


# ============================================================
# PREVIEW
# ============================================================

def get_site_preview(site_id):
    if not is_valid_site_id(site_id):
        return {
            "Status": "😾 Check",
            "Site ID": site_id,
            "Nama Site": "-",
            "Folder": "❌ Tidak dicek",
            "Before": "❌ Tidak dicek",
            "After": "❌ Tidak dicek",
            "Grafik": "❌ Tidak dicek",
            "Catatan": "Format Site ID tidak valid",
        }

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
            "Catatan": "Site ID tidak ditemukan di database",
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
            "Catatan": "Folder ID tidak valid di kolom R",
        }

    try:
        (
            before_file,
            after_file,
            grafik_single_file,
            grafik_1_file,
            grafik_2_file,
        ) = find_required_images(folder_id)

        has_two_grafik = (
            grafik_1_file is not None
            and grafik_2_file is not None
        )

        before_validation = validate_capture(site_id, before_file)
        after_validation = validate_capture(site_id, after_file)

        validations = {
            "Before": before_validation,
            "After": after_validation,
        }

        if has_two_grafik:
            grafik_1_validation = validate_capture(site_id, grafik_1_file)
            grafik_2_validation = validate_capture(site_id, grafik_2_file)

            validations["Grafik 1"] = grafik_1_validation
            validations["Grafik 2"] = grafik_2_validation

            if any(
                item[0] == "ERROR"
                for item in (grafik_1_validation, grafik_2_validation)
            ):
                grafik_display = "❌ Bermasalah"
            elif any(
                item[0] == "WARNING"
                for item in (grafik_1_validation, grafik_2_validation)
            ):
                grafik_display = "⚠️ 2 grafik ditemukan"
            else:
                grafik_display = "✅ 2 grafik tersedia"

        elif grafik_single_file is not None:
            grafik_validation = validate_capture(site_id, grafik_single_file)
            validations["Grafik"] = grafik_validation

            if grafik_validation[0] == "ERROR":
                grafik_display = "❌ Bermasalah"
            elif grafik_validation[0] == "WARNING":
                grafik_display = "⚠️ 1 grafik ditemukan"
            else:
                grafik_display = "✅ 1 grafik tersedia"

        elif grafik_1_file is not None:
            validations["Grafik"] = (
                "ERROR",
                "Grafik 1 ditemukan, tetapi Grafik 2 tidak ditemukan",
            )
            grafik_display = "❌ Grafik 2 tidak ada"

        elif grafik_2_file is not None:
            validations["Grafik"] = (
                "ERROR",
                "Grafik 2 ditemukan, tetapi Grafik 1 tidak ditemukan",
            )
            grafik_display = "❌ Grafik 1 tidak ada"

        else:
            validations["Grafik"] = ("ERROR", "File grafik tidak ditemukan")
            grafik_display = "❌ Tidak ditemukan"

        def format_validation(validation):
            status, _ = validation

            if status == "OK":
                return "✅ Ada & sesuai"
            if status == "WARNING":
                return "⚠️ Ada, belum pasti"
            return "❌ Bermasalah"

        has_error = any(
            validation[0] == "ERROR"
            for validation in validations.values()
        )

        has_warning = any(
            validation[0] == "WARNING"
            for validation in validations.values()
        )

        notes = []

        for label, (status, message) in validations.items():
            if status != "OK":
                notes.append(f"{label}: {message}")

        if not notes:
            notes.append("Siap generate")

        if has_error:
            result_status = "😾 Check"
        elif has_warning:
            result_status = "⚠️ Warning"
        else:
            result_status = "😺 Ready"

        return {
            "Status": result_status,
            "Site ID": site["site_id"],
            "Nama Site": site["site_name"],
            "Folder": "✅ Valid",
            "Before": format_validation(before_validation),
            "After": format_validation(after_validation),
            "Grafik": grafik_display,
            "Catatan": " | ".join(notes),
        }

    except Exception as error:
        return {
            "Status": "🙀 Error",
            "Site ID": site_id,
            "Nama Site": site["site_name"],
            "Folder": "⚠️ Error akses",
            "Before": "❌ Tidak dicek",
            "After": "❌ Tidak dicek",
            "Grafik": "❌ Tidak dicek",
            "Catatan": str(error),
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
        raise ValueError("Folder ID tidak valid di kolom R")

    (
        before_file,
        after_file,
        grafik_single_file,
        grafik_1_file,
        grafik_2_file,
    ) = find_required_images(folder_id)

    if before_file is None:
        raise FileNotFoundError("File before tidak ditemukan")

    if after_file is None:
        raise FileNotFoundError("File after tidak ditemukan")

    has_single_grafik = grafik_single_file is not None
    has_two_grafik = (
        grafik_1_file is not None
        and grafik_2_file is not None
    )

    if not has_two_grafik and not has_single_grafik:
        if grafik_1_file is not None:
            raise FileNotFoundError(
                "Grafik 1 ditemukan, tetapi Grafik 2 tidak ditemukan"
            )

        if grafik_2_file is not None:
            raise FileNotFoundError(
                "Grafik 2 ditemukan, tetapi Grafik 1 tidak ditemukan"
            )

        raise FileNotFoundError(
            "File grafik tidak ditemukan. "
            "Gunakan Grafik.png atau pasangan Grafik 1.png dan Grafik 2.png"
        )

    site_work_dir = Path(work_dir) / clean_filename(site_id)
    site_work_dir.mkdir(parents=True, exist_ok=True)

    before_path = site_work_dir / "before.png"
    after_path = site_work_dir / "after.png"
    grafik_single_path = site_work_dir / "grafik.png"
    grafik_1_path = site_work_dir / "grafik_1.png"
    grafik_2_path = site_work_dir / "grafik_2.png"

    download_drive_file(before_file["id"], str(before_path))
    download_drive_file(after_file["id"], str(after_path))

    if has_two_grafik:
        download_drive_file(grafik_1_file["id"], str(grafik_1_path))
        download_drive_file(grafik_2_file["id"], str(grafik_2_path))
    else:
        download_drive_file(grafik_single_file["id"], str(grafik_single_path))

    validation_items = [
        (
            "Before",
            validate_capture(site_id, before_file, before_path),
        ),
        (
            "After",
            validate_capture(site_id, after_file, after_path),
        ),
    ]

    if has_two_grafik:
        validation_items.extend(
            [
                (
                    "Grafik 1",
                    validate_capture(
                        site_id,
                        grafik_1_file,
                        grafik_1_path,
                    ),
                ),
                (
                    "Grafik 2",
                    validate_capture(
                        site_id,
                        grafik_2_file,
                        grafik_2_path,
                    ),
                ),
            ]
        )
    else:
        validation_items.append(
            (
                "Grafik",
                validate_capture(
                    site_id,
                    grafik_single_file,
                    grafik_single_path,
                ),
            )
        )

    errors = []

    for label, (status, message) in validation_items:
        if status == "ERROR":
            errors.append(f"{label} salah: {message}")

    if errors:
        raise ValueError(" | ".join(errors))

    output_name = clean_filename(
        f"{no_tracker}. {site_id} {site_name}.pdf"
    )
    output_pdf = Path(output_dir) / output_name

    doc = fitz.open(TEMPLATE_PDF)

    try:
        if doc.page_count < 3:
            raise ValueError("Template PDF harus memiliki minimal 3 halaman")

        page_1 = doc[0]

        page_1.draw_rect(
            COVER_CLEAR_RECT,
            color=(1, 1, 1),
            fill=(1, 1, 1),
            overlay=True,
        )

        page_1.insert_textbox(
            COVER_LINE_1_RECT,
            f"{no_tracker}. {site_id}",
            fontsize=16,
            fontname="helv",
            align=1,
            color=(0, 0, 0),
            overlay=True,
        )

        page_1.insert_textbox(
            COVER_LINE_2_RECT,
            site_name,
            fontsize=16,
            fontname="helv",
            align=1,
            color=(0, 0, 0),
            overlay=True,
        )

        page_2 = doc[1]
        insert_image(page_2, before_path, BEFORE_RECT)
        insert_image(page_2, after_path, AFTER_RECT)

        page_3 = doc[2]

        if has_two_grafik:
            insert_image(page_3, grafik_1_path, GRAFIK_1_RECT)
            insert_image(page_3, grafik_2_path, GRAFIK_2_RECT)
        else:
            insert_image(page_3, grafik_single_path, GRAFIK_SINGLE_RECT)

        doc.save(
            str(output_pdf),
            garbage=4,
            deflate=True,
            clean=True,
        )

    finally:
        doc.close()

    if not output_pdf.exists():
        raise RuntimeError("File PDF gagal disimpan")

    return str(output_pdf)


# ============================================================
# APP
# ============================================================

show_hero()
show_cat_gallery()

site_input = st.text_area(
    "Masukkan Site ID maksimal 50",
    height=170,
    placeholder="AM16224669368205N\nAM16224669328205N",
)

col_1, col_2 = st.columns(2)

with col_1:
    preview_btn = st.button(
        "🔍 Preview Site",
        use_container_width=True,
    )

with col_2:
    generate_btn = st.button(
        "🚀 Generate PDF",
        type="primary",
        use_container_width=True,
    )


if preview_btn:
    site_ids = parse_site_input(site_input)

    if not site_ids:
        st.warning("Site ID belum diisi.")

    elif len(site_ids) > MAX_SITE:
        st.error(f"Maksimal {MAX_SITE} Site ID.")

    else:
        preview_data = []
        progress = st.progress(0)
        status_box = st.empty()

        for index, site_id in enumerate(site_ids, start=1):
            status_box.info(
                f"😺 Mengecek {site_id} ({index}/{len(site_ids)})..."
            )

            preview_data.append(
                get_site_preview(site_id)
            )

            progress.progress(
                index / len(site_ids)
            )

        status_box.empty()

        has_error = any(
            row["Status"] in {"😾 Check", "🙀 Error"}
            for row in preview_data
        )

        st.subheader("📋 Preview Site Lengkap Sebelum Generate")

        st.dataframe(
            preview_data,
            use_container_width=True,
            hide_index=True,
        )

        if has_error:
            show_result_cat_card("angry")
            st.warning(
                "Ada site yang perlu dicek. "
                "Perhatikan kolom Before/After/Grafik dan Catatan."
            )
        else:
            show_result_cat_card("happy")
            st.success("Semua site siap generate PDF.")


if generate_btn:
    site_ids = parse_site_input(site_input)

    if not site_ids:
        show_result_cat_card("panic")
        st.warning("Site ID belum diisi.")
        st.stop()

    if len(site_ids) > MAX_SITE:
        show_result_cat_card("panic")
        st.error(f"Maksimal {MAX_SITE} Site ID.")
        st.stop()

    generated_files = []
    log_entries = []

    st.subheader("🚀 Proses Generate PDF")

    progress = st.progress(0)
    status_box = st.empty()

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir) / "work"
        output_dir = Path(tmpdir) / "output"

        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        for index, site_id in enumerate(site_ids, start=1):
            status_box.info(
                f"😺 Memproses {site_id} ({index}/{len(site_ids)})..."
            )

            try:
                site = find_site(site_id)

                if not site:
                    log_entries.append(
                        f"FAILED - {site_id}: "
                        "Site ID tidak ditemukan di database"
                    )
                else:
                    pdf_path = generate_pdf(
                        site,
                        work_dir,
                        output_dir,
                    )

                    generated_files.append(pdf_path)

                    log_entries.append(
                        f"DONE - {site_id}: "
                        f"{os.path.basename(pdf_path)}"
                    )

            except Exception as error:
                log_entries.append(
                    f"FAILED - {site_id}: {error}"
                )

            progress.progress(
                index / len(site_ids)
            )

        status_box.empty()

        if not generated_files:
            show_result_cat_card("panic")
            st.error("Tidak ada PDF yang berhasil dibuat.")
            st.subheader("Log")
            st.code("\n".join(log_entries))
            st.stop()

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(
            zip_buffer,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as zip_file:
            for pdf_path in generated_files:
                zip_file.write(
                    pdf_path,
                    os.path.basename(pdf_path),
                )

            zip_file.writestr(
                "log.txt",
                "\n".join(log_entries),
            )

        zip_buffer.seek(0)

        failed_count = sum(
            entry.startswith("FAILED")
            for entry in log_entries
        )

        if failed_count:
            show_result_cat_card("angry")
        else:
            show_result_cat_card("happy")

        metric_1, metric_2, metric_3 = st.columns(3)

        metric_1.metric("Berhasil", len(generated_files))
        metric_2.metric("Gagal", failed_count)
        metric_3.metric("Total", len(site_ids))

        st.success(
            f"{len(generated_files)} PDF berhasil dibuat."
        )

        st.download_button(
            label="⬇️ Download ZIP",
            data=zip_buffer,
            file_name="SSID_RTGS_REPORT_RESULT.zip",
            mime="application/zip",
            use_container_width=True,
        )

        st.subheader("Log")
        st.code("\n".join(log_entries))
