"""
Pembuat dokumen Word sintetis untuk keperluan pengujian otomatis (Unit Testing).
Menerapkan 100% KEBIJAKAN ZERO PII (hanya nama dummy, NIP dummy, dan instansi fiktif).
"""
import os
from docx import Document
from docx.shared import Inches
from docx.oxml import parse_xml


def create_sample_rpp(file_path: str) -> str:
    """Membuat dokumen RPP / Modul Ajar sintetis dengan tabel identitas dan blok tanda tangan."""
    doc = Document()
    doc.add_heading("MODUL AJAR KURIKULUM MERDEKA", level=1)
    doc.add_paragraph("INFORMASI UMUM PERANGKAT PEMBELAJARAN")

    # Tabel Identitas Modul
    tbl = doc.add_table(rows=4, cols=2)
    tbl.rows[0].cells[0].text = "Nama Penyusun"
    tbl.rows[0].cells[1].text = "Siti Aminah, S.Pd"
    tbl.rows[1].cells[0].text = "Nama Sekolah"
    tbl.rows[1].cells[1].text = "MIN 1 Contoh"
    tbl.rows[2].cells[0].text = "Tahun Pelajaran"
    tbl.rows[2].cells[1].text = "2025/2026"
    tbl.rows[3].cells[0].text = "Mata Pelajaran"
    tbl.rows[3].cells[1].text = "Matematika"

    doc.add_heading("KOMPONEN INTI", level=2)
    doc.add_paragraph("Tujuan Pembelajaran: Peserta didik memahami konsep dasar operasi bilangan cacah.")
    doc.add_paragraph("Alokasi Waktu: 2 JP x 35 Menit")

    # Blok Tanda Tangan
    doc.add_paragraph("Mengetahui,\t\t\t\tBandar Lampung, 15 Juli 2025")
    doc.add_paragraph("Kepala Madrasah\t\t\t\tGuru Mata Pelajaran")
    doc.add_paragraph("Budi Santoso, M.Pd\t\t\t\tSiti Aminah, S.Pd")
    doc.add_paragraph("NIP. 198001012005011001\t\t\t\tNIP. 198502022010012002")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path


def create_sample_sk(file_path: str) -> str:
    """Membuat dokumen Surat Keputusan (SK) sintetis standar."""
    doc = Document()
    doc.add_paragraph("KEMENTERIAN AGAMA REPUBLIK INDONESIA")
    doc.add_paragraph("KANTOR KEMENTERIAN AGAMA KABUPATEN CONTOH")
    doc.add_paragraph("MADRASAH IBTIDAIYAH NEGERI 1 CONTOH")

    doc.add_paragraph("KEPUTUSAN KEPALA MADRASAH IBTIDAIYAH NEGERI 1 CONTOH")
    doc.add_paragraph("NOMOR : 421.2/015/MIN.1/SK/2025")
    doc.add_paragraph("TENTANG")
    doc.add_paragraph("PEMBAGIAN TUGAS GURU DALAM PROSES BELAJAR MENGAJAR TAHUN PELAJARAN 2025/2026")

    doc.add_paragraph("Menimbang : a. bahwa dalam rangka memperlancar proses pembelajaran...")
    doc.add_paragraph("Mengingat : 1. Undang-Undang Nomor 20 Tahun 2003 tentang Sistem Pendidikan Nasional...")
    doc.add_paragraph("MEMUTUSKAN:")
    doc.add_paragraph("Menetapkan :")
    doc.add_paragraph("KESATU : Menetapkan pembagian tugas mengajar guru sebagaimana tercantum dalam lampiran keputusan ini.")
    doc.add_paragraph("KEDUA : Segala biaya yang timbul dibebankan pada DIPA madrasah.")

    doc.add_paragraph("Ditetapkan di : Kota Contoh")
    doc.add_paragraph("Pada tanggal : 14 Juli 2025")
    doc.add_paragraph("Kepala Madrasah,")
    doc.add_paragraph("Budi Santoso, M.Pd")
    doc.add_paragraph("NIP. 198001012005011001")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path


def create_sample_sk_with_attachment(file_path: str) -> str:
    """Membuat dokumen SK lengkap dengan halaman lampiran dan blok header lampiran."""
    doc = Document()
    doc.add_paragraph("KEMENTERIAN AGAMA REPUBLIK INDONESIA")
    doc.add_paragraph("MADRASAH IBTIDAIYAH NEGERI 1 CONTOH")

    doc.add_paragraph("KEPUTUSAN KEPALA MADRASAH IBTIDAIYAH NEGERI 1 CONTOH")
    doc.add_paragraph("NOMOR : 421.2/015/MIN.1/SK/2025")
    doc.add_paragraph("TENTANG")
    doc.add_paragraph("PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2025/2026")

    doc.add_paragraph("MEMUTUSKAN:")
    doc.add_paragraph("Menetapkan :")
    doc.add_paragraph("KESATU : Menetapkan tugas guru.")

    doc.add_paragraph("Ditetapkan di : Kota Contoh")
    doc.add_paragraph("Pada tanggal : 14 Juli 2025")
    doc.add_paragraph("Kepala Madrasah,")
    doc.add_paragraph("Budi Santoso, M.Pd")
    doc.add_paragraph("NIP. 198001012005011001")

    # Bagian Lampiran SK
    doc.add_page_break()
    doc.add_paragraph("LAMPIRAN KEPUTUSAN KEPALA MADRASAH IBTIDAIYAH NEGERI 1 CONTOH")
    doc.add_paragraph("Nomor : 421.2/015/MIN.1/SK/2025")
    doc.add_paragraph("Tanggal : 14 Juli 2025")
    doc.add_paragraph("Tentang : PEMBAGIAN TUGAS GURU TAHUN PELAJARAN 2025/2026")

    tbl = doc.add_table(rows=2, cols=3)
    tbl.rows[0].cells[0].text = "No"
    tbl.rows[0].cells[1].text = "Nama Guru"
    tbl.rows[0].cells[2].text = "Tugas Mengajar"
    tbl.rows[1].cells[0].text = "1"
    tbl.rows[1].cells[1].text = "Siti Aminah, S.Pd"
    tbl.rows[1].cells[2].text = "Guru Kelas 4"

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path


def create_sample_sk_with_textbox_kop(file_path: str) -> str:
    """Membuat dokumen SK dengan kop surat di dalam elemen textbox / AlternateContent."""
    doc = Document()

    # Tambahkan kop dalam mc:AlternateContent (Choice & Fallback)
    xml_kop = """<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <mc:Choice Requires="wps">
            <w:drawing>
                <w:txbxContent>
                    <w:p><w:r><w:t>KOP SURAT MADRASAH DALAM KOTAK TEKS CHOICE</w:t></w:r></w:p>
                </w:txbxContent>
            </w:drawing>
        </mc:Choice>
        <mc:Fallback>
            <w:pict>
                <w:txbxContent>
                    <w:p><w:r><w:t>KOP SURAT MADRASAH DALAM KOTAK TEKS CHOICE</w:t></w:r></w:p>
                </w:txbxContent>
            </w:pict>
        </mc:Fallback>
    </mc:AlternateContent>"""
    el = parse_xml(xml_kop)
    doc._body._element.insert(0, el)

    doc.add_paragraph("KEPUTUSAN KEPALA MADRASAH IBTIDAIYAH NEGERI 1 CONTOH")
    doc.add_paragraph("NOMOR : 421.2/015/MIN.1/SK/2025")
    doc.add_paragraph("TENTANG")
    doc.add_paragraph("PENETAPAN PANITIA UJIAN MADRASAH TAHUN PELAJARAN 2025/2026")
    doc.add_paragraph("MEMUTUSKAN:")
    doc.add_paragraph("Menetapkan :")
    doc.add_paragraph("KESATU : Susunan panitia ujian.")
    doc.add_paragraph("Ditetapkan di : Kota Contoh")
    doc.add_paragraph("Pada tanggal : 14 Juli 2025")
    doc.add_paragraph("Kepala Madrasah,")
    doc.add_paragraph("Budi Santoso, M.Pd")
    doc.add_paragraph("NIP. 198001012005011001")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path


def create_sample_surat_dinas(file_path: str) -> str:
    """Membuat dokumen Surat Dinas / Undangan Resmi sintetis."""
    doc = Document()
    doc.add_paragraph("KOP SURAT MADRASAH CONTOH")
    doc.add_paragraph("Nomor : B-025/Min.01/PP.00/07/2025")
    doc.add_paragraph("Sifat : Penting")
    doc.add_paragraph("Lampiran : -")
    doc.add_paragraph("Hal : Undangan Rapat Kerja Pembagian Tugas")

    doc.add_paragraph("Kepada Yth.")
    doc.add_paragraph("Bapak/Ibu Dewan Guru MIN 1 Contoh")
    doc.add_paragraph("di Tempat")

    doc.add_paragraph("Assalamu'alaikum Wr. Wb.")
    doc.add_paragraph("Dengan hormat, mengharap kehadiran Bapak/Ibu pada acara rapat yang akan dilaksanakan pada:")
    doc.add_paragraph("Hari, Tanggal : Senin, 14 Juli 2025")
    doc.add_paragraph("Waktu : Pukul 09.00 WIB s.d Selesai")
    doc.add_paragraph("Tempat : Aula Pertemuan Madrasah")
    doc.add_paragraph("Acara : Koordinasi Pembagian Tugas Guru")

    doc.add_paragraph("Demikian surat undangan ini kami sampaikan, atas kehadirannya diucapkan terima kasih.")
    doc.add_paragraph("Wassalamu'alaikum Wr. Wb.")
    doc.add_paragraph("Kepala Madrasah,")
    doc.add_paragraph("Budi Santoso, M.Pd")
    doc.add_paragraph("NIP. 198001012005011001")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path


def create_sample_spt(file_path: str) -> str:
    """Membuat dokumen Surat Perintah Tugas (SPT) sintetis."""
    doc = Document()
    doc.add_paragraph("KOP SURAT INSTANSI CONTOH")
    doc.add_paragraph("SURAT PERINTAH TUGAS")
    doc.add_paragraph("Nomor : 800/012/SPT/2025")
    doc.add_paragraph("Dasar : Surat Kepala Kantor Kementerian Agama Nomor...")
    doc.add_paragraph("Menugaskan kepada :")

    tbl = doc.add_table(rows=2, cols=4)
    tbl.rows[0].cells[0].text = "No"
    tbl.rows[0].cells[1].text = "Nama / NIP"
    tbl.rows[0].cells[2].text = "Pangkat / Gol"
    tbl.rows[0].cells[3].text = "Jabatan"

    tbl.rows[1].cells[0].text = "1"
    tbl.rows[1].cells[1].text = "Siti Aminah, S.Pd / 198502022010012002"
    tbl.rows[1].cells[2].text = "Penata / III.c"
    tbl.rows[1].cells[3].text = "Guru Kelas"

    doc.add_paragraph("Untuk mengikuti Bimbingan Teknis Implementasi Kurikulum Merdeka.")
    doc.add_paragraph("Ditetapkan di Kota Contoh pada tanggal 10 Juli 2025.")
    doc.add_paragraph("Kepala Madrasah, Budi Santoso, M.Pd")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path


def create_sample_berita_acara(file_path: str) -> str:
    """Membuat dokumen Berita Acara sintetis."""
    doc = Document()
    doc.add_paragraph("BERITA ACARA SERAH TERIMA JABATAN")
    doc.add_paragraph("Nomor : 001/BA-STJ/2025")
    doc.add_paragraph("Pada hari ini Selasa tanggal Lima Belas bulan Juli tahun Dua Ribu Dua Puluh Lima (15-07-2025)...")
    doc.add_paragraph("PIHAK KESATU: Budi Santoso, M.Pd, Jabatan: Kepala Madrasah Lama")
    doc.add_paragraph("PIHAK KEDUA: Ahmad Dahlan, M.Pd, Jabatan: Kepala Madrasah Baru")
    doc.add_paragraph("Kedua belah pihak telah sepakat mengadakan serah terima dokumen...")

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    doc.save(file_path)
    return file_path
