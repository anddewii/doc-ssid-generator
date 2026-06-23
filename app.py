import os
import re
import io
import zipfile
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import fitz  # PyMuPDF
import gdown
import streamlit as st

# ============================================================
# CONFIG
# ============================================================
SHEET_ID = "17jaV5RykOT0SPZXRWoKO_UP7yNrpUq9hIXGAn-6ONPI"
GID = "0"
TEMPLATE_PDF = "TAMPLATE PERUBAHAN SSID AP1.pdf"

# Mapping kolom database sesuai format Anda
COL_NO_TRACKER = 0     # A = No Tracker PMO, contoh: 3749
COL_SITE_ID = 1        # B = Site ID, contoh: AM16224669368205N
COL_SITE_NAME = 2      # C = Site Name
COL_FOLDER_LINK = 16   # Q = Link Dokumen

MAX_SITE = 15

# Koordinat PDF. Jika gambar kurang pas, ubah angka Rect di sini saja.
COVER_CLEAR_RECT = fitz.Rect(50, 390, 560, 505)
COVER_LINE_1_RECT = fitz.Rect(60, 405, 540, 440)
COVER_LINE_2_RECT = fitz.Rect(60, 440, 540, 495)
BEFORE_RECT = fitz.Rect(60, 150, 535, 360)
AFTER_RECT = fitz.Rect(60, 455, 535, 725)
GRAFIK_RECT = fitz.Rect(45, 145, 550, 690)

# ============================================================
# UI CONFIG
# ============================================================
st.set_page_config(
    page_title="RTGS Report Generator",
    page_icon="📄",
    layout="centered",
)

st.title("📄 RTGS Report Generator")
st.caption("Generate PDF Perubahan SSID AP1 dari Google Sheet + Google Drive")

# ============================================================
# HELPERS
# ============================================================
@st.cache_data(ttl=300)
def load_database():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    df = pd.read_csv(url, dtype=str).fillna("")
    return df


def parse_site_input(text):
    items = re.split(r"[\n,;]+", text)
    return [x.strip().upper() for x in items if x.strip()]


def clean_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "", str(text)).strip()


def find_site(df, site_id):
    site_id = str(site_id).strip().upper()
    for _, row in df.iterrows():
        sheet_site_id = str(row.iloc[COL_SITE_ID]).strip().upper()
        if sheet_site_id == site_id:
            return {
                "no_tracker": str(row.iloc[COL_NO_TRACKER]).strip(),
                "site_id": str(row.iloc[COL_SITE_ID]).strip(),
                "site_name": str(row.iloc[COL_SITE_NAME]).strip(),
                "folder_link": str(row.iloc[COL_FOLDER_LINK]).strip(),
            }
    return None


def download_public_folder(folder_link, target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    result = gdown.download_folder(
        url=folder_link,
        output=target_dir,
        quiet=True,
        use_cookies=False,
    )
    return result


def find_images(folder_path):
    before = None
    after = None
    grafik = None

    for root, _, files in os.walk(folder_path):
        for file in files:
            name = file.lower()
            full_path = os.path.join(root, file)

            if "_before" in name and before is None:
                before = full_path
            elif "_after" in name and after is None:
                after = full_path
            elif "grafik" in name and grafik is None:
                grafik = full_path

    return before, after, grafik


def insert_image(page, image_path, rect):
    page.insert_image(rect, filename=image_path, keep_proportion=True)


def generate_pdf(site, base_work_dir):
    no_tracker = site["no_tracker"]
    site_id = site["site_id"]
    site_name = site["site_name"]
    folder_link = site["folder_link"]

    site_work_dir = os.path.join(base_work_dir, clean_filename(site_id))
    download_public_folder(folder_link, site_work_dir)

    before_img, after_img, grafik_img = find_images(site_work_dir)

    if before_img is None:
        raise Exception("File *_before tidak ditemukan")
    if after_img is None:
        raise Exception("File *_after tidak ditemukan")
    if grafik_img is None:
        raise Exception("File Grafik Zabbix tidak ditemukan")

    output_name = clean_filename(f"{no_tracker}. {site_id} {site_name}.pdf")
    output_pdf = os.path.join(base_work_dir, output_name)

    doc = fitz.open(TEMPLATE_PDF)

    # PAGE 1 - COVER
    page1 = doc[0]
    page1.draw_rect(COVER_CLEAR_RECT, color=(1, 1, 1), fill=(1, 1, 1))

    page1.insert_textbox(
        COVER_LINE_1_RECT,
        f"{no_tracker}. {site_id}",
        fontsize=18,
        fontname="helv-bold",
        align=1,
        color=(0, 0, 0),
    )

    page1.insert_textbox(
        COVER_LINE_2_RECT,
        site_name,
        fontsize=18,
        fontname="helv-bold",
        align=1,
        color=(0, 0, 0),
    )

    # PAGE 2 - BEFORE & AFTER
    page2 = doc[1]
    insert_image(page2, before_img, BEFORE_RECT)
    insert_image(page2, after_img, AFTER_RECT)

    # PAGE 3 - GRAFIK
    page3 = doc[2]
    insert_image(page3, grafik_img, GRAFIK_RECT)

    doc.save(output_pdf)
    doc.close()

    return output_pdf


def make_zip(pdf_paths, logs):
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for pdf in pdf_paths:
            z.write(pdf, os.path.basename(pdf))
        z.writestr("log.txt", "\n".join(logs))
    mem_zip.seek(0)
    return mem_zip

# ============================================================
# APP
# ============================================================
with st.expander("Syarat agar aplikasi bisa berjalan", expanded=False):
    st.markdown(
        """
        - Nama file di folder site harus mengandung:
          - `_before`
          - `_after`
          - `grafik`
        """
    )

try:
    df = load_database()
    st.success(f"Database terbaca: {len(df):,} baris")
except Exception as e:
    st.error(f"Gagal membaca Google Sheet: {e}")
    st.stop()

site_text = st.text_area(
    "Masukkan Site ID maksimal 15",
    height=180,
    placeholder="Contoh:\nAM16224669368205N\nAM16224669328205N",
)

col1, col2 = st.columns([1, 1])

with col1:
    preview_btn = st.button("Preview Site", use_container_width=True)

with col2:
    generate_btn = st.button("Generate PDF", type="primary", use_container_width=True)

site_ids = parse_site_input(site_text)

if preview_btn:
    if not site_ids:
        st.warning("Site ID belum diisi.")
    elif len(site_ids) > MAX_SITE:
        st.error("Maksimal 15 Site ID.")
    else:
        preview_rows = []
        for sid in site_ids:
            site = find_site(df, sid)
            if site:
                preview_rows.append({
                    "Site ID": site["site_id"],
                    "No Tracker": site["no_tracker"],
                    "Site Name": site["site_name"],
                    "Status": "Ditemukan",
                })
            else:
                preview_rows.append({
                    "Site ID": sid,
                    "No Tracker": "",
                    "Site Name": "",
                    "Status": "Tidak ditemukan",
                })
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True)

if generate_btn:
    if not site_ids:
        st.warning("Site ID belum diisi.")
        st.stop()

    if len(site_ids) > MAX_SITE:
        st.error("Maksimal 15 Site ID.")
        st.stop()

    if not Path(TEMPLATE_PDF).exists():
        st.error(f"Template PDF tidak ditemukan: {TEMPLATE_PDF}")
        st.stop()

    generated_files = []
    logs = []

    progress = st.progress(0)
    status_box = st.empty()

    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, sid in enumerate(site_ids, start=1):
            status_box.info(f"Memproses {sid} ({idx}/{len(site_ids)})...")

            try:
                site = find_site(df, sid)
                if not site:
                    logs.append(f"FAILED - {sid}: Site ID tidak ditemukan di database")
                    progress.progress(idx / len(site_ids))
                    continue

                pdf_path = generate_pdf(site, tmpdir)
                generated_files.append(pdf_path)
                logs.append(f"DONE - {sid}: {os.path.basename(pdf_path)}")

            except Exception as e:
                logs.append(f"FAILED - {sid}: {str(e)}")

            progress.progress(idx / len(site_ids))

        if generated_files:
            zip_data = make_zip(generated_files, logs)
            st.success(f"Selesai. {len(generated_files)} PDF berhasil dibuat.")
            st.download_button(
                label="Download ZIP",
                data=zip_data,
                file_name="RTGS_REPORT_RESULT.zip",
                mime="application/zip",
                use_container_width=True,
            )
        else:
            st.error("Tidak ada PDF yang berhasil dibuat.")

        st.subheader("Log")
        st.code("\n".join(logs))
