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


# ============================================================
# UI
# ============================================================

st.set_page_config(
    page_title="RTGS Report Generator",
    page_icon="📄",
    layout="centered"
)

st.title("📄 Doc Report Generator")
st.caption("Generate PDF Perubahan SSID AP1 dari Google Sheet + Google Drive")
from PIL import Image
from pathlib import Path

logo1 = Image.open("logo.png")
logo2 = Image.open("logo2.png")

col1, col2, col3 = st.columns(3)

with col1:
    st.image("logo.png", width=250)

with col2:
    st.image("logo2.png", width=250)

with col3:
    st.image(
        "https://media1.tenor.com/m/Xn3TfHpAJiMAAAAd/scuba-cat-scuba.gif",
        width=250
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
    st.error(f"Gagal membaca database Google Sheet: {e}")
    st.stop()


# ============================================================
# HELPER
# ============================================================

def parse_site_input(text):
    items = re.split(r"[\n,;]+", text)
    return [x.strip().upper() for x in items if x.strip()]


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


def download_drive_file(file_id, output_path):
    request = drive_service.files().get_media(fileId=file_id)

    with io.FileIO(output_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False

        while not done:
            _, done = downloader.next_chunk()

    return output_path


def insert_image(page, image_path, rect):
    page.insert_image(
        rect,
        filename=str(image_path),
        keep_proportion=True
    )


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

site_input = st.text_area(
    "Masukkan Site ID maksimal 50",
    height=170,
    placeholder="AM16224669368205N\nAM16224669328205N"
)

col1, col2 = st.columns(2)

with col1:
    preview_btn = st.button("Preview Site", use_container_width=True)

with col2:
    generate_btn = st.button("Generate PDF", type="primary", use_container_width=True)


if preview_btn:
    site_ids = parse_site_input(site_input)

    if len(site_ids) == 0:
        st.warning("Site ID belum diisi.")
    elif len(site_ids) > MAX_SITE:
        st.error("Maksimal 15 Site ID.")
    else:
        st.subheader("Preview")
        for site_id in site_ids:
            site = find_site(site_id)

            if site:
                st.success(f"{site['site_id']} - {site['site_name']}")
            else:
                st.error(f"{site_id} tidak ditemukan di database")


if generate_btn:
    site_ids = parse_site_input(site_input)

    if len(site_ids) == 0:
        st.warning("Site ID belum diisi.")
        st.stop()

    if len(site_ids) > MAX_SITE:
        st.error("Maksimal 15 Site ID.")
        st.stop()

    generated_files = []
    log = []

    progress = st.progress(0)
    status = st.empty()

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir) / "work"
        output_dir = Path(tmpdir) / "output"

        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, site_id in enumerate(site_ids, start=1):
            status.info(f"Memproses {site_id} ({i}/{len(site_ids)})...")

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

        st.success(f"{len(generated_files)} PDF berhasil dibuat.")

        st.download_button(
            label="Download ZIP",
            data=zip_buffer,
            file_name="RTGS_REPORT_RESULT.zip",
            mime="application/zip",
            use_container_width=True
        )

        st.subheader("Log")
        st.code("\n".join(log))
