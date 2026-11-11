"""
Generator dokumen .docx uji sintetis dengan berbagai variasi layout RPP:
1. sample_rpp_dotted_table.docx (tabel identitas 2 kolom + tabel tanda tangan bertitik-titik)
2. sample_rpp_existing_names.docx (tabel identitas 3 kolom + tabel tanda tangan nama lama & NIP)
3. sample_rpp_tab_signature.docx (paragraf tanda tangan bertabulasi)
4. sample_rpp_underline.docx (placeholder garis bawah inline)
"""
import os
from docx import Document


def create_sample_dotted_table(out_path: str):
    doc = Document()
    doc.add_heading("MODUL AJAR / RPP KURIKULUM MERDEKA", level=1)

    # Tabel identitas 2 kolom
    table = doc.add_table(rows=3, cols=2)
    rows_data = [
        ("Satuan Pendidikan", "SD Negeri 1 Contoh"),
        ("Tahun Pelajaran", "2025/2026"),
        ("Semester", "Ganjil"),
    ]
    for i, (k, v) in enumerate(rows_data):
        table.rows[i].cells[0].text = k
        table.rows[i].cells[1].text = v

    doc.add_paragraph("A. TUJUAN PEMBELAJARAN\nPeserta didik mampu memahami materi dengan baik.")
    doc.add_paragraph("B. KEGIATAN PEMBELAJARAN\nKegiatan inti diskusi dan penugasan.")

    # Tabel tanda tangan 2 kolom borderless
    sig_table = doc.add_table(rows=6, cols=2)
    # Kolom Kiri: Kepala Madrasah
    sig_table.rows[0].cells[0].text = "Mengetahui,"
    sig_table.rows[1].cells[0].text = "Kepala Madrasah"
    sig_table.rows[2].cells[0].text = ""
    sig_table.rows[3].cells[0].text = ""
    sig_table.rows[4].cells[0].text = "( ........................................ )"
    sig_table.rows[5].cells[0].text = "NIP. ........................................"

    # Kolom Kanan: Guru
    sig_table.rows[0].cells[1].text = "Kotaagung, ................ 2025"
    sig_table.rows[1].cells[1].text = "Guru Kelas IV"
    sig_table.rows[2].cells[1].text = ""
    sig_table.rows[3].cells[1].text = ""
    sig_table.rows[4].cells[1].text = "( ........................................ )"
    sig_table.rows[5].cells[1].text = "NIP. ........................................"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)


def create_sample_existing_names(out_path: str):
    doc = Document()
    doc.add_heading("RENCANA PELAKSANAAN PEMBELAJARAN", level=1)

    # Tabel identitas 3 kolom: Label | : | Nilai
    table = doc.add_table(rows=3, cols=3)
    rows_data = [
        ("Nama Sekolah", ":", "SD Negeri 5 Teluk"),
        ("Tahun Pelajaran", ":", "2024/2025"),
        ("Semester", ":", "Ganjil"),
    ]
    for i, (col1, col2, col3) in enumerate(rows_data):
        table.rows[i].cells[0].text = col1
        table.rows[i].cells[1].text = col2
        table.rows[i].cells[2].text = col3

    doc.add_paragraph("Uraian materi pembelajaran dan kompetensi dasar.")

    # Tabel tanda tangan dengan nama lama
    sig_table = doc.add_table(rows=5, cols=2)
    sig_table.rows[0].cells[0].text = "Mengetahui,\nKepala Sekolah"
    sig_table.rows[1].cells[0].text = ""
    sig_table.rows[2].cells[0].text = ""
    sig_table.rows[3].cells[0].text = "( Drs. H. Ahmad Dahlan, M.Pd )"
    sig_table.rows[4].cells[0].text = "NIP. 196805121994031002"

    sig_table.rows[0].cells[1].text = "Bandar Lampung, 15 Juli 2024\nGuru Kelas V"
    sig_table.rows[1].cells[1].text = ""
    sig_table.rows[2].cells[1].text = ""
    sig_table.rows[3].cells[1].text = "( Siti Fatimah, S.Pd.I )"
    sig_table.rows[4].cells[1].text = "NIP. 198203112006042015"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)


def create_sample_tab_signature(out_path: str):
    doc = Document()
    doc.add_heading("MODUL AJAR KURIKULUM MERDEKA", level=1)
    doc.add_paragraph("Disusun oleh : ................................")
    doc.add_paragraph("Materi pelajaran Bahasa Indonesia.")

    # Tanda tangan bertabulasi
    doc.add_paragraph("Mengetahui,\t\t\t\tJakarta, .......... 2026")
    doc.add_paragraph("Kepala Madrasah\t\t\t\tGuru Mata Pelajaran")
    doc.add_paragraph("\t\t\t\t")
    doc.add_paragraph("\t\t\t\t")
    doc.add_paragraph("( ................................ )\t\t\t\t( ................................ )")
    doc.add_paragraph("NIP. ....................\t\t\t\tNIP. ....................")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)


def create_sample_underline(out_path: str):
    doc = Document()
    doc.add_heading("IDENTITAS RPP", level=1)
    doc.add_paragraph("Nama Kepala Madrasah : ________________________")
    doc.add_paragraph("NIP Kepala : ________________________")
    doc.add_paragraph("Nama Guru : ________________________")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)


def create_sample_bab1(out_path: str):
    """Menghasilkan dokumen sintetis berformat BAB 1 (tabel 1-kolom, 20.. /20.., Kepala Sekolah)."""
    doc = Document()
    doc.add_heading("BAB 1: KETENTUAN UMUM PEMBELAJARAN", level=1)

    # Tabel identitas 1-kolom (label : nilai menyatu dalam satu sel)
    t = doc.add_table(rows=3, cols=1)
    t.rows[0].cells[0].paragraphs[0].text = "Satuan Pendidikan : SD Negeri 1 Contoh"
    t.rows[1].cells[0].paragraphs[0].text = "Tahun Pelajaran : 20.. /20.."
    t.rows[2].cells[0].paragraphs[0].text = "Semester : Ganjil"

    doc.add_paragraph("Materi pokok dan capaian pembelajaran kurikulum.")

    # Tabel tanda tangan 2-kolom dengan Kepala Sekolah
    sig_table = doc.add_table(rows=1, cols=2)
    cell0 = sig_table.rows[0].cells[0]
    cell0.paragraphs[0].text = "Mengetahui,\nKepala Sekolah"
    cell0.add_paragraph()
    cell0.add_paragraph("( ................................ )")
    cell0.add_paragraph("NIP. ....................")

    cell1 = sig_table.rows[0].cells[1]
    cell1.paragraphs[0].text = "Jakarta, .......... 20..\nGuru Mata Pelajaran"
    cell1.add_paragraph()
    cell1.add_paragraph("( ................................ )")
    cell1.add_paragraph("NIP. ....................")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)


def create_sample_modul_ajar(out_path: str):
    """Menghasilkan dokumen sintetis Modul Ajar (tabel 3-kolom, Kepala Madrasah, 2025/2026)."""
    doc = Document()
    doc.add_heading("MODUL AJAR KURIKULUM MERDEKA - UNIT 1", level=1)

    # Tabel identitas 3 kolom: Label | : | Nilai
    table = doc.add_table(rows=3, cols=3)
    rows_data = [
        ("Nama Madrasah", ":", "MI Al-Falah"),
        ("Tahun Pelajaran", ":", "2025/2026"),
        ("Semester", ":", "Ganjil"),
    ]
    for i, (col1, col2, col3) in enumerate(rows_data):
        table.rows[i].cells[0].text = col1
        table.rows[i].cells[1].text = col2
        table.rows[i].cells[2].text = col3

    doc.add_paragraph("Capaian pembelajaran dan aktivitas murid di kelas.")

    # Tabel tanda tangan 2 kolom dengan Kepala Madrasah
    sig_table = doc.add_table(rows=5, cols=2)
    sig_table.rows[0].cells[0].text = "Mengetahui,\nKepala Madrasah"
    sig_table.rows[1].cells[0].text = ""
    sig_table.rows[2].cells[0].text = ""
    sig_table.rows[3].cells[0].text = "( H. Syamsudin, M.Pd )"
    sig_table.rows[4].cells[0].text = "NIP. 197205101998031003"

    sig_table.rows[0].cells[1].text = "Bandar Lampung, 15 Juli 2025\nGuru Mata Pelajaran"
    sig_table.rows[1].cells[1].text = ""
    sig_table.rows[2].cells[1].text = ""
    sig_table.rows[3].cells[1].text = "( Nurul Hidayah, S.Pd )"
    sig_table.rows[4].cells[1].text = "NIP. 198308152009022004"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)


def generate_all_samples(base_dir: str = ""):
    if not base_dir:
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
    os.makedirs(base_dir, exist_ok=True)

    create_sample_dotted_table(os.path.join(base_dir, "sample_rpp_dotted_table.docx"))
    create_sample_existing_names(os.path.join(base_dir, "sample_rpp_existing_names.docx"))
    create_sample_tab_signature(os.path.join(base_dir, "sample_rpp_tab_signature.docx"))
    create_sample_underline(os.path.join(base_dir, "sample_rpp_underline.docx"))
    create_sample_bab1(os.path.join(base_dir, "sample_bab1.docx"))
    create_sample_modul_ajar(os.path.join(base_dir, "sample_modul_ajar.docx"))
    print(f"Sample files generated at: {base_dir}")


if __name__ == "__main__":
    generate_all_samples()
