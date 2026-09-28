import datetime
import io
import os
import re
import zipfile
import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
from PIL import Image
import pytesseract
import streamlit as st

# ================= Tesseract Executable Path Config =================
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

# ================= Streamlit Page Config =================
st.set_page_config(
    page_title="Smart Utility",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================= Custom Colorful & Professional CSS =================
st.markdown(
    """
    <style>
    /* Main Background Gradient */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Header Card Style */
    .header-card {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 22px;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        margin-bottom: 25px;
    }
    .header-card h1 {
        color: #ffffff;
        margin: 0;
        font-size: 2.0rem;
    }
    .date-badge {
        background-color: #ff7e5f;
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.95rem;
        display: inline-block;
        margin-top: 10px;
    }

    /* Metric Cards */
    .metric-card {
        background: white;
        padding: 18px;
        border-radius: 12px;
        border-left: 6px solid #1e3c72;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 15px;
    }
    .metric-card h4 {
        margin: 0 0 5px 0;
        color: #333;
    }
    .metric-card p {
        margin: 0;
        font-size: 1.2rem;
        font-weight: bold;
        color: #1e3c72;
    }

    /* Tab & Menu Standard Icon/Text Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 8px 8px 0 0;
        padding: 10px 16px !important;
        font-size: 15px !important;
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3c72 !important;
        color: white !important;
    }

    /* Sidebar and Menu Icon Standardizing (24px) */
    [data-testid="stSidebarNav"] svg, 
    [data-testid="collapsedControl"] svg {
        width: 24px !important;
        height: 24px !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ================= হেলপার ফাংশনসমূহ =================
def clean_sheet_name(name):
    cleaned = re.sub(r"[\\/*?:\[\]]", "", name)
    return cleaned[:30]


def make_unique_columns(columns):
    seen = {}
    unique_cols = []
    for idx, col in enumerate(columns):
        col_str = str(col).strip()
        if not col_str:
            col_str = f"Unnamed_Col_{idx+1}"

        if col_str in seen:
            seen[col_str] += 1
            unique_cols.append(f"{col_str}_{seen[col_str]}")
        else:
            seen[col_str] = 0
            unique_cols.append(col_str)
    return unique_cols


def add_years_to_date(original_date, years):
    """Leap year নিরাপদে হ্যান্ডেল করে বছর যোগ করার ফাংশন"""
    try:
        return original_date.replace(year=original_date.year + years)
    except ValueError:
        return original_date.replace(
            year=original_date.year + years, month=2, day=28
        )


def get_last_day_of_month(any_date):
    """মাসের শেষ তারিখ বের করার হেলপার"""
    if any_date.month == 12:
        return any_date.replace(day=31)
    return any_date.replace(
        month=any_date.month + 1, day=1
    ) - datetime.timedelta(days=1)


# ================= ১. আল্ট্রা-ফাস্ট ডিজিটাল এক্সট্র্যাক্টর =================
def extract_tables_fast(file_bytes):
    all_rows = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for tab in tabs.tables:
                    df_tab = tab.extract()
                    for r in df_tab:
                        cleaned = [
                            (
                                ""
                                if c is None
                                else " ".join(str(c).split())
                            )
                            for c in r
                        ]
                        if any(cleaned):
                            all_rows.append(cleaned)
    except Exception:
        pass

    if not all_rows:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if not tables:
                        text_lines = page.extract_text()
                        if text_lines:
                            for line in text_lines.split("\n"):
                                parts = re.split(r"\s{2,}", line.strip())
                                if len(parts) > 1:
                                    all_rows.append(parts)
                    else:
                        for table in tables:
                            for row in table:
                                cleaned = [
                                    (
                                        ""
                                        if cell is None
                                        else " ".join(str(cell).split())
                                    )
                                    for cell in row
                                ]
                                if any(cleaned):
                                    all_rows.append(cleaned)
        except Exception:
            pass

    if all_rows:
        max_cols = max(len(r) for r in all_rows)
        header_idx = 0
        for i, row in enumerate(all_rows):
            row_str = " ".join(str(c).upper() for c in row)
            if any(
                k in row_str
                for k in [
                    "NAME",
                    "ROLL",
                    "SL",
                    "NO",
                    "DISTRICT",
                    "CANDIDATE",
                    "SCHOOL",
                    "DATE",
                    "SET",
                ]
            ):
                header_idx = i
                break

        raw_header = all_rows[header_idx]
        if len(raw_header) < max_cols:
            raw_header += [
                f"Extra_Col_{i+1}" for i in range(max_cols - len(raw_header))
            ]

        header = make_unique_columns(raw_header)
        padded_rows = []
        for r in all_rows[header_idx + 1 :]:
            if r == raw_header:
                continue
            if len(r) < max_cols:
                r = r + [""] * (max_cols - len(r))
            elif len(r) > max_cols:
                r = r[:max_cols]
            padded_rows.append(r)

        if padded_rows:
            df = pd.DataFrame(padded_rows, columns=header)
            if len(df.columns) > 1 and len(df) > 0:
                return df

    return None


# ================= ২. অ্যাডভান্সড টেবিল-সচেতন ইমেজ OCR এক্সট্র্যাক্টর =================
def process_image_file(image_obj):
    try:
        image = Image.open(image_obj).convert("RGB")
        custom_config = r"--oem 3 --psm 6 -l eng+ben"
        data = pytesseract.image_to_data(
            image, config=custom_config, output_type=pytesseract.Output.DATAFRAME
        )

        data = data[data.text.notnull() & (data.text.str.strip() != "")]
        if data.empty:
            return None

        data = data.sort_values(by=["top", "left"])

        rows = []
        current_row = []
        last_top = None

        for _, row in data.iterrows():
            top = row["top"]
            text = str(row["text"]).strip()
            left = row["left"]

            if last_top is None:
                current_row.append({"x": left, "text": text})
                last_top = top
            else:
                if abs(top - last_top) <= 15:
                    current_row.append({"x": left, "text": text})
                else:
                    current_row.sort(key=lambda item: item["x"])
                    rows.append([item["text"] for item in current_row])
                    current_row = [{"x": left, "text": text}]
                    last_top = top

        if current_row:
            current_row.sort(key=lambda item: item["x"])
            rows.append([item["text"] for item in current_row])

        if rows:
            cleaned_rows = []
            for r in rows:
                row_str = " ".join(r)
                parts = re.split(r"\s{2,}|\|", row_str)
                cleaned_rows.append(parts)

            max_cols = max(len(r) for r in cleaned_rows)
            padded_rows = [
                r + [""] * (max_cols - len(r)) for r in cleaned_rows
            ]

            header = make_unique_columns(padded_rows[0])
            return pd.DataFrame(padded_rows[1:], columns=header)

    except Exception as e:
        st.error(f"ইমেজ প্রসেস করতে সমস্যা: {e}")
    return None


# ================= ৩. PDF to Image কনভার্টার =================
def convert_pdf_to_images(file_bytes, dpi=150):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append((f"page_{page_num+1}.png", img_bytes))
    return images


# ================= ৪. বয়স গণনার নিখুঁত হেলপার =================
def calculate_exact_age(dob, target_date):
    if dob > target_date:
        return None
    years = target_date.year - dob.year
    months = target_date.month - dob.month
    days = target_date.day - dob.day

    if days < 0:
        months -= 1
        last_month = (
            target_date.month - 1 if target_date.month > 1 else 12
        )
        year_to_check = (
            target_date.year
            if target_date.month > 1
            else target_date.year - 1
        )
        if last_month in [1, 3, 5, 7, 8, 10, 12]:
            days += 31
        elif last_month in [4, 6, 9, 11]:
            days += 30
        else:
            days += (
                29
                if (
                    year_to_check % 4 == 0
                    and (year_to_check % 100 != 0 or year_to_check % 400 == 0)
                )
                else 28
            )

    if months < 0:
        years -= 1
        months += 12

    return years, months, days


# ================= Header with Live Date/Time =================
now = datetime.datetime.now()
formatted_now = now.strftime("%A, %d/%m/%Y | %I:%M:%S %p")

st.markdown(
    f"""
    <div class="header-card">
        <h1>📑 প্রফেশনাল ইউটিলিটি ড্যাশবোর্ড</h1>
        <div class="date-badge">📅 বর্তমান সময়: {formatted_now}</div>
    </div>
""",
    unsafe_allow_html=True,
)

# ================= Main Navigation Tabs =================
(
    tab_opt1,
    tab_opt2,
    tab_merge,
    tab_split,
    tab_comp_pdf,
    tab_comp_img,
    tab_img2pdf,
    tab_age,
    tab_emp,
) = st.tabs([
    "🚀  ডাটা এক্সট্র্যাক্ট",
    "🖼️  PDF to Image",
    "🔗 মার্জ PDF",
    "✂️ স্প্লিট PDF",
    "📉 PDF কম্প্রেশন",
    "🖼️ ইমেজ কম্প্রেশন",
    "🖼️➡️📄 ইমেজ to PDF",
    "🎂 বয়স ক্যালকুলেটর",
    "👔 কর্মচারী সেবা",
])

# ----------------- 🚀 অপশন ১ (ডাটা এক্সট্র্যাকশন) -----------------
with tab_opt1:
    st.subheader("📊 PDF বা ইমেজ আপলোড করে Excel ডাটা বের করুন")
    uploaded_files = st.file_uploader(
        "ফাইল আপলোড করুন (PDF, PNG, JPG, JPEG)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="extractor_uploader",
    )

    if uploaded_files:
        if st.button(
            "🚀 এক্সট্র্যাক্ট শুরু করুন", type="primary", key="btn_extract"
        ):
            processed_data = {}
            failed_files = []

            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(uploaded_files)

            for idx, file in enumerate(uploaded_files):
                status_text.text(
                    f"প্রসেস করা হচ্ছে: {file.name} ({idx+1}/{total})..."
                )
                file_bytes = file.read()
                file_type = file.name.split(".")[-1].lower()
                df = None

                if file_type == "pdf":
                    df = extract_tables_fast(file_bytes)
                elif file_type in ["png", "jpg", "jpeg"]:
                    df = process_image_file(file)

                if df is not None and not df.empty:
                    raw_name = file.name.split(".")[0]
                    sheet_name = clean_sheet_name(raw_name)
                    if sheet_name in processed_data:
                        sheet_name = clean_sheet_name(f"{sheet_name}_{idx+1}")
                    processed_data[sheet_name] = df
                else:
                    failed_files.append(file.name)

                progress_bar.progress((idx + 1) / total)

            status_text.text("প্রসেসিং সম্পন্ন হয়েছে!")

            if failed_files:
                st.warning(
                    f"⚠️ নিচের ফাইলগুলো থেকে ডাটা সনাক্ত করা যায়নি: {', '.join(failed_files)}"
                )

            if processed_data:
                st.session_state["extracted_data"] = processed_data
                st.success(
                    f"🎉 মোট {len(processed_data)}টি ফাইল সফলভাবে প্রসেস হয়েছে!"
                )

    if "extracted_data" in st.session_state:
        processed_data = st.session_state["extracted_data"]
        tab_names = list(processed_data.keys())
        ui_tabs = st.tabs(tab_names)

        for i, tab_name in enumerate(tab_names):
            with ui_tabs[i]:
                st.dataframe(
                    processed_data[tab_name], use_container_width=True
                )

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            for s_name, df_sheet in processed_data.items():
                df_sheet.to_excel(writer, index=False, sheet_name=s_name)

        st.download_button(
            label="📥 Excel ফাইল ডাউনলোড করুন",
            data=excel_buffer.getvalue(),
            file_name="Extracted_Tables.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_dl_excel",
        )

# ----------------- 🖼️ অপশন ২ (PDF to Image কনভার্টার) -----------------
with tab_opt2:
    st.subheader("🖼️ PDF কে ইমেজে রূপান্তর করুন")
    pdf_file = st.file_uploader(
        "PDF ফাইল সিলেক্ট করুন", type=["pdf"], key="converter_uploader"
    )

    if pdf_file:
        col1, col2 = st.columns([2, 1])
        with col1:
            dpi = st.slider(
                "ইমেজের কোয়ালিটি (DPI)",
                min_value=100,
                max_value=300,
                value=150,
                step=50,
            )

        if st.button(
            "🔄 ইমেজে রূপান্তর করুন", type="primary", key="btn_convert"
        ):
            with st.spinner("PDF থেকে পেজগুলোকে ইমেজে রূপান্তর করা হচ্ছে..."):
                images = convert_pdf_to_images(pdf_file.read(), dpi=dpi)

                st.success(
                    f"সফলভাবে {len(images)}টি পেজ ইমেজে রূপান্তর করা হয়েছে!"
                )

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                    for img_name, img_bytes in images:
                        zip_file.writestr(img_name, img_bytes)

                st.download_button(
                    label="📦 সকল ইমেজের ZIP ফাইল ডাউনলোড করুন",
                    data=zip_buffer.getvalue(),
                    file_name=f"{pdf_file.name.split('.')[0]}_images.zip",
                    mime="application/zip",
                    key="btn_dl_zip",
                )

                st.subheader("🖼️ ইমেজের প্রিভিউ:")
                cols = st.columns(3)
                for idx, (img_name, img_bytes) in enumerate(images):
                    with cols[idx % 3]:
                        st.image(
                            img_bytes,
                            caption=img_name,
                            use_container_width=True,
                        )

# ----------------- 🔗 মার্জ পিডিএফ -----------------
with tab_merge:
    st.subheader("🔗 একাধিক PDF ফাইল একসাথে সংযুক্ত (Merge) করুন")
    merge_files = st.file_uploader(
        "একাধিক PDF আপলোড করুন",
        type=["pdf"],
        accept_multiple_files=True,
        key="merge_pdf_uploader",
    )
    if merge_files and st.button("🧩 PDF মার্জ করুন", type="primary"):
        merged_doc = fitz.open()
        for f in merge_files:
            doc = fitz.open(stream=f.read(), filetype="pdf")
            merged_doc.insert_pdf(doc)

        output_buffer = io.BytesIO()
        merged_doc.save(output_buffer)
        st.success("সফলভাবে PDF ফাইলগুলো একত্রিত করা হয়েছে!")
        st.download_button(
            "📥 Merged PDF ডাউনলোড করুন",
            data=output_buffer.getvalue(),
            file_name="Merged_Document.pdf",
            mime="application/pdf",
        )

# ----------------- ✂️ স্প্লিট পিডিএফ -----------------
with tab_split:
    st.subheader("✂️ PDF পেজ স্প্লিট/আলাদা করুন")
    split_file = st.file_uploader(
        "PDF ফাইল আপলোড করুন", type=["pdf"], key="split_pdf_uploader"
    )
    if split_file:
        doc = fitz.open(stream=split_file.read(), filetype="pdf")
        total_pages = len(doc)
        st.info(f"📄 মোট পেজ সংখ্যা: {total_pages}")

        start_p, end_p = st.slider(
            "পেজ রেঞ্জ সিলেক্ট করুন (Start - End)",
            1,
            total_pages,
            (1, max(1, total_pages)),
        )
        if st.button("✂️ পেজ আলাদা করুন", type="primary"):
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start_p - 1, to_page=end_p - 1)
            out_buf = io.BytesIO()
            new_doc.save(out_buf)
            st.success(
                f"পেজ {start_p} থেকে {end_p} সফলভাবে আলাদা করা হয়েছে!"
            )
            st.download_button(
                "📥 Split PDF ডাউনলোড করুন",
                data=out_buf.getvalue(),
                file_name=f"Split_Pages_{start_p}_to_{end_p}.pdf",
                mime="application/pdf",
            )

# ----------------- 📉 পিডিএফ কম্প্রেশন -----------------
with tab_comp_pdf:
    st.subheader("📉 PDF ফাইল সাইজ কমান (Compression)")
    comp_pdf_file = st.file_uploader(
        "PDF ফাইল সিলেক্ট করুন", type=["pdf"], key="comp_pdf_uploader"
    )
    if comp_pdf_file and st.button("📉 কমপ্রেস করুন", type="primary"):
        doc = fitz.open(stream=comp_pdf_file.read(), filetype="pdf")
        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True, clean=True)
        st.success("PDF সফলভাবে কমপ্রেস করা হয়েছে!")
        st.download_button(
            "📥 Compressed PDF ডাউনলোড করুন",
            data=out_buf.getvalue(),
            file_name="Compressed_Document.pdf",
            mime="application/pdf",
        )

# ----------------- 🖼️ ইমেজ কম্প্রেশন -----------------
with tab_comp_img:
    st.subheader("🖼️ ইমেজ ফাইল সাইজ কমান")
    img_file = st.file_uploader(
        "ইমেজ ফাইল আপলোড করুন",
        type=["jpg", "jpeg", "png"],
        key="comp_img_uploader",
    )
    if img_file:
        quality = st.slider(
            "ইমেজ কোয়ালিটি % (কমলে ফাইল সাইজ কমবে)", 10, 95, 70
        )
        if st.button("📉 ইমেজ কমপ্রেস করুন", type="primary"):
            img = Image.open(img_file).convert("RGB")
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=quality, optimize=True)
            st.success("ইমেজ কমপ্রেস করা সম্পন্ন!")
            st.download_button(
                "📥 Compressed Image ডাউনলোড করুন",
                data=out_buf.getvalue(),
                file_name="Compressed_Image.jpg",
                mime="image/jpeg",
            )

# ----------------- 🖼️➡️📄 ইমেজ থেকে পিডিএফ -----------------
with tab_img2pdf:
    st.subheader("🖼️➡️📄 একাধিক ইমেজ থেকে একটি PDF তৈরি করুন")
    images_for_pdf = st.file_uploader(
        "ইমেজ ফাইলসমূহ সিলেক্ট করুন",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="img2pdf_uploader",
    )
    if images_for_pdf and st.button("📄 PDF এ রূপান্তর করুন", type="primary"):
        img_list = []
        for f in images_for_pdf:
            img = Image.open(f).convert("RGB")
            img_list.append(img)

        pdf_buf = io.BytesIO()
        img_list[0].save(
            pdf_buf, format="PDF", save_all=True, append_images=img_list[1:]
        )
        st.success("সফলভাবে PDF তৈরি হয়েছে!")
        st.download_button(
            "📥 Converted PDF ডাউনলোড করুন",
            data=pdf_buf.getvalue(),
            file_name="Images_Converted.pdf",
            mime="application/pdf",
        )

# ----------------- 🎂 বয়স ক্যালকুলেটর -----------------
with tab_age:
    st.subheader("🎂 বর্তমান বয়স এবং স্কুল ভর্তি ক্লাস হিসাব")

    col_dob, _ = st.columns([2, 1])
    with col_dob:
        dob = st.date_input(
            "জন্ম তারিখ নির্বাচন করুন (DD/MM/YYYY)",
            datetime.date(2018, 1, 1),
            min_value=datetime.date(1940, 1, 1),
            format="DD/MM/YYYY",  # DD/MM/YYYY ফরম্যাট
            key="dob_input",
        )

    today = datetime.date.today()
    age_today = calculate_exact_age(dob, today)

    if age_today:
        y, m, d = age_today
        st.success(
            f"📅 **আজকের তারিখে ({today.strftime('%d/%m/%Y')}) বর্তমান বয়স:** {y} বছর, {m} মাস, {d} দিন"
        )
    else:
        st.error("জন্ম তারিখ বর্তমান তারিখের চেয়ে বড় হতে পারে না!")

    st.markdown("---")
    st.subheader("🏫 ০১/০১/২০২৬ তারিখে বয়স এবং ভর্তিযোগ্য স্কুল ক্লাস:")

    target_2026 = datetime.date(2026, 1, 1)
    age_2026 = calculate_exact_age(dob, target_2026)

    if age_2026:
        y_26, m_26, d_26 = age_2026
        st.info(
            f"📌 **০১/০১/২০২৬ তারিখে হিসাবকৃত বয়স:** {y_26} বছর, {m_26} মাস, {d_26} দিন"
        )

        class_mapping = {
            6: "Class 1 (প্রথম শ্রেণী)",
            7: "Class 2 (দ্বিতীয় শ্রেণী)",
            8: "Class 3 (তৃতীয় শ্রেণী)",
            9: "Class 4 (চতুর্থ শ্রেণী)",
            10: "Class 5 (পঞ্চম শ্রেণী)",
            11: "Class 6 (ষষ্ঠ শ্রেণী)",
            12: "Class 7 (সপ্তম শ্রেণী)",
            13: "Class 8 (অষ্টম শ্রেণী)",
        }

        assigned_class = class_mapping.get(y_26, None)
        if assigned_class:
            st.markdown(
                f"🎓 **নির্ধারিত ক্লাস:** <span style='font-size:1.4rem; color:#1e3c72; font-weight:bold;'>{assigned_class}</span>",
                unsafe_allow_html=True,
            )
        elif y_26 < 6:
            st.warning(
                "⚠️ শিশুটির বয়স ৬ বছরের কম (প্রাক-প্রাথমিক শিক্ষাক্রমের অধীন)।"
            )
        else:
            st.warning(
                "⚠️ বয়স ১৩ বছরের বেশি (Class 8 এর পরবর্তী উচ্চতর শ্রেণী)।"
            )

# ----------------- 👔 কর্মচারী সেবা -----------------
with tab_emp:
    st.subheader("👔 কর্মচারী চাকরির মেয়াদকাল ও অবসর তথ্য")

    col_emp1, col_emp2 = st.columns(2)
    with col_emp1:
        emp_dob = st.date_input(
            "কর্মচারীর জন্ম তারিখ (DD/MM/YYYY)",
            datetime.date(1985, 1, 1),
            format="DD/MM/YYYY",  # DD/MM/YYYY ফরম্যাট
            key="emp_dob_val",
        )
    with col_emp2:
        emp_doj = st.date_input(
            "প্রথম যোগদানের তারিখ (DD/MM/YYYY)",
            datetime.date(2010, 1, 1),
            format="DD/MM/YYYY",  # DD/MM/YYYY ফরম্যাট
            key="emp_doj_val",
        )

    if st.button("📊 তথ্য হিসাব করুন", type="primary"):
        if emp_doj < emp_dob:
            st.error("যোগদানের তারিখ জন্ম তারিখের পূর্বে হতে পারে না!")
        else:
            date_10_yr = add_years_to_date(emp_doj, 10)
            date_18_yr = add_years_to_date(emp_doj, 18)

            dob_60_years = add_years_to_date(emp_dob, 60)
            retire_date = get_last_day_of_month(dob_60_years)

            st.success("🎉 সফলভাবে হিসাব করা হয়েছে!")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    f"""
                <div class="metric-card">
                    <h4>📅 ১০ বছর চাকরি পূর্তি</h4>
                    <p>{date_10_yr.strftime('%d/%m/%Y')}</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f"""
                <div class="metric-card">
                    <h4>📅 ১৮ বছর চাকরি পূর্তি</h4>
                    <p>{date_18_yr.strftime('%d/%m/%Y')}</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f"""
                <div class="metric-card" style="border-left-color: #ff7e5f;">
                    <h4>🏖️ ৬০ বছর বয়সে অবসর (Superannuation)</h4>
                    <p>{retire_date.strftime('%d/%m/%Y')}</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )