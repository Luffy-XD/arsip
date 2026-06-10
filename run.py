#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║           PDF COMPRESSOR PRO - Tools Kompresi PDF                ║
║           Versi 2.0.0 | Tanpa Mengurangi Kualitas                ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import shutil
import hashlib
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict

# ── Library checks ────────────────────────────────────────────────────────────
try:
    import pikepdf
except ImportError:
    print("[ERROR] pikepdf tidak ditemukan. Jalankan: pip install pikepdf")
    sys.exit(1)

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("[ERROR] pypdf tidak ditemukan. Jalankan: pip install pypdf")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich import box
    from rich.columns import Columns
    from rich.align import Align
    from rich.rule import Rule
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("[INFO] Instal 'rich' untuk tampilan lebih baik: pip install rich")

# ── Global Console ────────────────────────────────────────────────────────────
console = Console() if RICH_AVAILABLE else None

VERSION = "2.0.0"
APP_NAME = "PDF Compressor Pro"
LOG_FILE = "pdf_compressor_log.json"


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def print_msg(msg: str, style: str = "white", newline: bool = True):
    """Print dengan rich jika tersedia, fallback ke print biasa."""
    if RICH_AVAILABLE and console:
        console.print(msg, style=style, end="\n" if newline else "")
    else:
        end = "\n" if newline else ""
        print(msg, end=end)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def format_size(size_bytes: int) -> str:
    """Format ukuran file ke string yang mudah dibaca."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def get_file_size(path: str) -> int:
    """Dapatkan ukuran file dalam bytes."""
    return os.path.getsize(path)


def calculate_reduction(original: int, compressed: int) -> Tuple[float, str]:
    """Hitung persentase pengurangan ukuran."""
    if original == 0:
        return 0.0, "0%"
    reduction = ((original - compressed) / original) * 100
    return reduction, f"{reduction:.1f}%"


def get_md5(filepath: str) -> str:
    """Hitung MD5 hash file untuk verifikasi integritas."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def count_pdf_pages(filepath: str) -> int:
    """Hitung jumlah halaman dalam PDF."""
    try:
        with pikepdf.open(filepath) as pdf:
            return len(pdf.pages)
    except Exception:
        try:
            reader = PdfReader(filepath)
            return len(reader.pages)
        except Exception:
            return 0


def validate_pdf(filepath: str) -> Tuple[bool, str]:
    """Validasi apakah file adalah PDF yang valid."""
    if not os.path.exists(filepath):
        return False, "File tidak ditemukan"
    if not filepath.lower().endswith(".pdf"):
        return False, "File bukan PDF (ekstensi tidak .pdf)"
    if get_file_size(filepath) == 0:
        return False, "File kosong"
    try:
        with pikepdf.open(filepath):
            return True, "OK"
    except pikepdf.PasswordError:
        return False, "PDF terenkripsi/dilindungi password"
    except Exception as e:
        return False, f"File PDF rusak: {e}"


def generate_output_path(input_path: str, suffix: str = "_compressed", output_dir: Optional[str] = None) -> str:
    """Generate path output file."""
    p = Path(input_path)
    stem = p.stem + suffix
    filename = stem + p.suffix
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)
    return str(p.parent / filename)


def load_log() -> List[Dict]:
    """Muat log kompresi dari file JSON."""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_log(entry: Dict):
    """Simpan entry log ke file JSON."""
    logs = load_log()
    logs.append(entry)
    # Batasi log 500 entri terakhir
    if len(logs) > 500:
        logs = logs[-500:]
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPRESSION ENGINES
# ══════════════════════════════════════════════════════════════════════════════

def compress_lossless_pikepdf(input_path: str, output_path: str, level: int = 9) -> Dict:
    """
    Kompresi lossless menggunakan pikepdf.
    Mengoptimalkan struktur internal PDF tanpa mengubah konten.
    Level: 1-9 (1=cepat, 9=maksimal)
    """
    result = {
        "method": "Lossless (pikepdf)",
        "success": False,
        "error": None,
        "original_size": get_file_size(input_path),
        "compressed_size": 0,
        "pages": 0,
        "time_elapsed": 0,
    }

    start_time = time.time()
    try:
        compress_streams = level >= 3
        object_streams = pikepdf.ObjectStreamMode.generate if level >= 5 else pikepdf.ObjectStreamMode.preserve
        stream_data = pikepdf.StreamDataMode.compress if level >= 2 else pikepdf.StreamDataMode.preserve

        with pikepdf.open(input_path, suppress_warnings=True) as pdf:
            result["pages"] = len(pdf.pages)

            # Hapus metadata yang tidak perlu (opsional)
            if level >= 7 and "/Info" in pdf.trailer:
                info = pdf.trailer["/Info"]
                # Pertahankan metadata penting
                keys_to_keep = ["/Title", "/Author", "/Subject", "/Creator", "/Producer"]
                for key in list(info.keys()):
                    if key not in keys_to_keep:
                        try:
                            del info[key]
                        except Exception:
                            pass

            pdf.save(
                output_path,
                compress_streams=compress_streams,
                object_stream_mode=object_streams,
                stream_data_mode=stream_data,
                normalize_content=False,
                linearize=False,
            )

        result["compressed_size"] = get_file_size(output_path)
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        if os.path.exists(output_path):
            os.remove(output_path)

    result["time_elapsed"] = time.time() - start_time
    return result


def compress_with_qpdf(input_path: str, output_path: str) -> Dict:
    """
    Kompresi menggunakan qpdf (jika tersedia di sistem).
    Linearize + re-compress streams.
    """
    result = {
        "method": "QPDF Optimization",
        "success": False,
        "error": None,
        "original_size": get_file_size(input_path),
        "compressed_size": 0,
        "pages": count_pdf_pages(input_path),
        "time_elapsed": 0,
    }

    if shutil.which("qpdf") is None:
        result["error"] = "qpdf tidak ditemukan di sistem"
        return result

    start_time = time.time()
    try:
        cmd = f'qpdf --compress-streams=y --recompress-flate --compression-level=9 "{input_path}" "{output_path}"'
        ret = os.system(cmd + " 2>/dev/null")
        if ret == 0 and os.path.exists(output_path):
            result["compressed_size"] = get_file_size(output_path)
            result["success"] = True
        else:
            result["error"] = "qpdf gagal memproses file"
    except Exception as e:
        result["error"] = str(e)

    result["time_elapsed"] = time.time() - start_time
    return result


def compress_lossless_pypdf(input_path: str, output_path: str) -> Dict:
    """
    Kompresi menggunakan pypdf - re-write PDF dengan kompresi.
    Cocok sebagai fallback.
    """
    result = {
        "method": "Lossless (pypdf)",
        "success": False,
        "error": None,
        "original_size": get_file_size(input_path),
        "compressed_size": 0,
        "pages": 0,
        "time_elapsed": 0,
    }

    start_time = time.time()
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        result["pages"] = len(reader.pages)

        for page in reader.pages:
            writer.add_page(page)

        # Kompres setiap objek
        for page in writer.pages:
            page.compress_content_streams()

        with open(output_path, "wb") as f:
            writer.write(f)

        result["compressed_size"] = get_file_size(output_path)
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        if os.path.exists(output_path):
            os.remove(output_path)

    result["time_elapsed"] = time.time() - start_time
    return result


def compress_smart(input_path: str, output_path: str, level: int = 6) -> Dict:
    """
    Mode pintar: mencoba beberapa metode dan memilih hasil terbaik.
    """
    methods = []
    temp_files = []

    # Method 1: pikepdf level tinggi
    tmp1 = output_path + ".tmp1.pdf"
    temp_files.append(tmp1)
    r1 = compress_lossless_pikepdf(input_path, tmp1, level=level)
    if r1["success"]:
        methods.append((r1, tmp1))

    # Method 2: pikepdf + pypdf gabungan
    tmp2 = output_path + ".tmp2.pdf"
    temp_files.append(tmp2)
    if r1["success"]:
        r2 = compress_lossless_pypdf(tmp1, tmp2)
    else:
        r2 = compress_lossless_pypdf(input_path, tmp2)
    if r2["success"]:
        r2["method"] = "Lossless Gabungan (pikepdf + pypdf)"
        methods.append((r2, tmp2))

    # Method 3: qpdf jika tersedia
    tmp3 = output_path + ".tmp3.pdf"
    temp_files.append(tmp3)
    r3 = compress_with_qpdf(input_path, tmp3)
    if r3["success"]:
        methods.append((r3, tmp3))

    if not methods:
        return {
            "method": "Smart Compression",
            "success": False,
            "error": "Semua metode kompresi gagal",
            "original_size": get_file_size(input_path),
            "compressed_size": 0,
            "pages": 0,
            "time_elapsed": 0,
        }

    # Pilih hasil terkecil
    best_result, best_tmp = min(methods, key=lambda x: x[0]["compressed_size"])

    shutil.copy2(best_tmp, output_path)
    best_result["method"] = f"Smart ({best_result['method']})"

    # Cleanup temp files
    for tmp in temp_files:
        if os.path.exists(tmp):
            os.remove(tmp)

    return best_result


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """Tampilkan banner aplikasi."""
    clear_screen()
    if RICH_AVAILABLE and console:
        banner = Panel.fit(
            Align.center(
                Text.from_markup(
                    f"[bold cyan]██████╗ ██████╗ ███████╗\n"
                    f"[bold cyan]██╔══██╗██╔══██╗██╔════╝\n"
                    f"[bold cyan]██████╔╝██║  ██║█████╗  \n"
                    f"[bold cyan]██╔═══╝ ██║  ██║██╔══╝  \n"
                    f"[bold cyan]██║     ██████╔╝██║     \n"
                    f"[bold cyan]╚═╝     ╚═════╝ ╚═╝     \n\n"
                    f"[bold white]{APP_NAME}[/bold white]  "
                    f"[dim]v{VERSION}[/dim]\n"
                    f"[dim]Kompresi PDF Tanpa Mengurangi Kualitas[/dim]"
                )
            ),
            border_style="bright_blue",
            padding=(1, 4),
        )
        console.print(banner)
    else:
        print("=" * 60)
        print(f"  {APP_NAME} v{VERSION}")
        print("  Kompresi PDF Tanpa Mengurangi Kualitas")
        print("=" * 60)
    print()


def print_result_table(results: List[Dict]):
    """Tampilkan tabel hasil kompresi."""
    if not results:
        return

    if RICH_AVAILABLE and console:
        table = Table(
            title="📊 Hasil Kompresi",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold cyan",
            show_lines=True,
        )
        table.add_column("No", justify="center", style="dim", width=4)
        table.add_column("File", style="white", max_width=30)
        table.add_column("Sebelum", justify="right", style="yellow")
        table.add_column("Sesudah", justify="right", style="green")
        table.add_column("Hemat", justify="right", style="bold green")
        table.add_column("Halaman", justify="center", style="cyan")
        table.add_column("Waktu", justify="right", style="dim")
        table.add_column("Status", justify="center")

        for i, r in enumerate(results, 1):
            filename = Path(r.get("input_path", "?")).name
            if len(filename) > 28:
                filename = filename[:25] + "..."

            orig = r.get("original_size", 0)
            comp = r.get("compressed_size", 0)
            reduction, pct = calculate_reduction(orig, comp)

            if r.get("success"):
                status = "[bold green]✓ Berhasil[/bold green]"
                hemat = f"[bold green]-{pct}[/bold green]" if reduction > 0 else f"[yellow]{pct}[/yellow]"
            else:
                status = "[bold red]✗ Gagal[/bold red]"
                hemat = "-"

            table.add_row(
                str(i),
                filename,
                format_size(orig),
                format_size(comp) if r.get("success") else "-",
                hemat,
                str(r.get("pages", "-")),
                f"{r.get('time_elapsed', 0):.1f}s",
                status,
            )

        console.print(table)

        # Summary
        success_list = [r for r in results if r.get("success")]
        if success_list:
            total_orig = sum(r.get("original_size", 0) for r in success_list)
            total_comp = sum(r.get("compressed_size", 0) for r in success_list)
            total_red, pct = calculate_reduction(total_orig, total_comp)
            console.print(
                Panel(
                    f"[bold]Total file diproses:[/bold] {len(results)}  |  "
                    f"[bold]Berhasil:[/bold] [green]{len(success_list)}[/green]  |  "
                    f"[bold]Gagal:[/bold] [red]{len(results)-len(success_list)}[/red]\n"
                    f"[bold]Total ruang dihemat:[/bold] [green]{format_size(total_orig - total_comp)} ({pct})[/green]",
                    border_style="green",
                    title="📈 Ringkasan",
                )
            )
    else:
        print("\n" + "=" * 80)
        print(f"{'HASIL KOMPRESI':^80}")
        print("=" * 80)
        for i, r in enumerate(results, 1):
            filename = Path(r.get("input_path", "?")).name
            orig = r.get("original_size", 0)
            comp = r.get("compressed_size", 0)
            _, pct = calculate_reduction(orig, comp)
            status = "BERHASIL" if r.get("success") else "GAGAL"
            print(f"  {i}. {filename}")
            print(f"     Sebelum: {format_size(orig)} | Sesudah: {format_size(comp)} | Hemat: {pct} | {status}")
        print("=" * 80)


def print_info_box(pdf_path: str):
    """Tampilkan info detail PDF."""
    valid, msg = validate_pdf(pdf_path)
    if not valid:
        print_msg(f"[red]✗ {msg}[/red]")
        return

    size = get_file_size(pdf_path)
    pages = count_pdf_pages(pdf_path)
    md5 = get_md5(pdf_path)
    modified = datetime.fromtimestamp(os.path.getmtime(pdf_path)).strftime("%d/%m/%Y %H:%M:%S")
    created = datetime.fromtimestamp(os.path.getctime(pdf_path)).strftime("%d/%m/%Y %H:%M:%S")

    # Metadata
    meta_info = {}
    try:
        with pikepdf.open(pdf_path, suppress_warnings=True) as pdf:
            if pdf.docinfo:
                for k in ["/Title", "/Author", "/Subject", "/Creator", "/Producer", "/CreationDate"]:
                    v = pdf.docinfo.get(k)
                    if v:
                        meta_info[k.strip("/")] = str(v)
    except Exception:
        pass

    if RICH_AVAILABLE and console:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Key", style="bold cyan", width=16)
        table.add_column("Value", style="white")

        table.add_row("📄 File", Path(pdf_path).name)
        table.add_row("📁 Path", str(Path(pdf_path).parent))
        table.add_row("📦 Ukuran", format_size(size))
        table.add_row("📑 Halaman", str(pages))
        table.add_row("🕐 Dimodifikasi", modified)
        table.add_row("📅 Dibuat", created)
        table.add_row("🔑 MD5", md5)

        if meta_info:
            table.add_row("", "")
            for k, v in meta_info.items():
                table.add_row(f"  {k}", v[:60])

        console.print(Panel(table, title="📋 Informasi PDF", border_style="bright_blue"))
    else:
        print(f"\n  File   : {Path(pdf_path).name}")
        print(f"  Ukuran : {format_size(size)}")
        print(f"  Halaman: {pages}")
        print(f"  MD5    : {md5}")
        for k, v in meta_info.items():
            print(f"  {k}: {v}")


# ══════════════════════════════════════════════════════════════════════════════
#  CORE COMPRESSION WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

def run_compression(
    input_path: str,
    output_path: str,
    mode: str = "smart",
    level: int = 6,
    verify: bool = True,
    backup: bool = False,
) -> Dict:
    """
    Jalankan kompresi PDF dengan konfigurasi yang ditentukan.

    Args:
        input_path: Path file PDF input
        output_path: Path file PDF output
        mode: 'smart' | 'pikepdf' | 'pypdf' | 'qpdf'
        level: Level kompresi 1-9
        verify: Verifikasi hasil setelah kompresi
        backup: Buat backup file asli

    Returns:
        Dict berisi hasil kompresi
    """
    result = {"input_path": input_path, "output_path": output_path}

    # Validasi input
    valid, msg = validate_pdf(input_path)
    if not valid:
        return {**result, "success": False, "error": msg, "original_size": 0,
                "compressed_size": 0, "pages": 0, "time_elapsed": 0}

    # Backup jika diminta
    if backup:
        backup_path = input_path + ".backup"
        shutil.copy2(input_path, backup_path)

    # Jalankan kompresi sesuai mode
    if mode == "smart":
        res = compress_smart(input_path, output_path, level)
    elif mode == "pikepdf":
        res = compress_lossless_pikepdf(input_path, output_path, level)
    elif mode == "pypdf":
        res = compress_lossless_pypdf(input_path, output_path)
    elif mode == "qpdf":
        res = compress_with_qpdf(input_path, output_path)
    else:
        res = compress_smart(input_path, output_path, level)

    result.update(res)

    # Jika hasil lebih besar dari asli, simpan asli
    if res["success"] and res.get("compressed_size", 0) >= res.get("original_size", 0):
        shutil.copy2(input_path, output_path)
        result["compressed_size"] = res["original_size"]
        result["note"] = "File tidak dapat dikompres lebih lanjut, disalin tanpa perubahan"

    # Verifikasi hasil
    if verify and res["success"]:
        valid_out, msg_out = validate_pdf(output_path)
        if not valid_out:
            result["success"] = False
            result["error"] = f"Verifikasi gagal: {msg_out}"
            if os.path.exists(output_path):
                os.remove(output_path)

    # Simpan log
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "input": input_path,
        "output": output_path,
        "original_size": result.get("original_size", 0),
        "compressed_size": result.get("compressed_size", 0),
        "success": result.get("success", False),
        "method": result.get("method", ""),
        "error": result.get("error"),
    }
    save_log(log_entry)

    return result


def compress_single_file(output_dir: Optional[str] = None, mode: str = "smart", level: int = 6):
    """Menu: Kompresi satu file PDF."""
    print_msg("\n[bold cyan]═══ Kompresi Satu File ═══[/bold cyan]")

    # Input path
    if RICH_AVAILABLE:
        input_path = Prompt.ask("\n  📂 Masukkan path file PDF").strip().strip('"').strip("'")
    else:
        input_path = input("\n  Masukkan path file PDF: ").strip().strip('"').strip("'")

    valid, msg = validate_pdf(input_path)
    if not valid:
        print_msg(f"\n  [red]✗ Error: {msg}[/red]")
        input("\n  Tekan Enter untuk lanjut...")
        return

    print_info_box(input_path)

    # Output path
    default_out = generate_output_path(input_path, "_compressed", output_dir)
    if RICH_AVAILABLE:
        out = Prompt.ask(f"\n  💾 Path output", default=default_out)
    else:
        out = input(f"\n  Path output (Enter={default_out}): ").strip() or default_out

    # Konfirmasi
    if RICH_AVAILABLE:
        confirm = Confirm.ask("\n  ▶ Mulai kompresi?", default=True)
    else:
        confirm = input("\n  Mulai kompresi? (Y/n): ").strip().lower() != "n"

    if not confirm:
        return

    print_msg("\n  [yellow]⚙ Memproses...[/yellow]")

    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Mengkompresi PDF...", total=100)
            progress.update(task, advance=30)
            result = run_compression(input_path, out, mode, level)
            progress.update(task, advance=70)
    else:
        result = run_compression(input_path, out, mode, level)

    result["input_path"] = input_path
    print_result_table([result])

    if result["success"]:
        print_msg(f"\n  [green]✓ File tersimpan: {out}[/green]")
    else:
        print_msg(f"\n  [red]✗ Gagal: {result.get('error', 'Unknown error')}[/red]")

    input("\n  Tekan Enter untuk lanjut...")


def compress_batch_files(output_dir: Optional[str] = None, mode: str = "smart", level: int = 6):
    """Menu: Kompresi banyak file sekaligus (batch)."""
    print_msg("\n[bold cyan]═══ Kompresi Batch (Banyak File) ═══[/bold cyan]")
    print_msg("  [dim]Masukkan path folder atau pola glob (misal: /dokumen/*.pdf)[/dim]\n")

    if RICH_AVAILABLE:
        pattern = Prompt.ask("  📂 Path folder / pola file").strip().strip('"').strip("'")
    else:
        pattern = input("  Path folder / pola file: ").strip().strip('"').strip("'")

    # Cari file PDF
    if os.path.isdir(pattern):
        files = sorted(glob.glob(os.path.join(pattern, "**", "*.pdf"), recursive=True))
    else:
        files = sorted(glob.glob(pattern, recursive=True))
        files = [f for f in files if f.lower().endswith(".pdf")]

    if not files:
        print_msg("\n  [yellow]⚠ Tidak ada file PDF ditemukan.[/yellow]")
        input("\n  Tekan Enter untuk lanjut...")
        return

    print_msg(f"\n  [green]✓ Ditemukan {len(files)} file PDF[/green]")
    for i, f in enumerate(files[:10], 1):
        print_msg(f"    {i}. {Path(f).name} ({format_size(get_file_size(f))})")
    if len(files) > 10:
        print_msg(f"    ... dan {len(files)-10} file lainnya")

    # Output dir
    if RICH_AVAILABLE:
        out_dir = Prompt.ask("\n  💾 Folder output", default=output_dir or "output_compressed")
    else:
        out_dir = input(f"\n  Folder output (Enter=output_compressed): ").strip() or "output_compressed"

    os.makedirs(out_dir, exist_ok=True)

    if RICH_AVAILABLE:
        confirm = Confirm.ask(f"\n  ▶ Kompresi {len(files)} file ke '{out_dir}'?", default=True)
    else:
        confirm = input(f"\n  Kompresi {len(files)} file ke '{out_dir}'? (Y/n): ").strip().lower() != "n"

    if not confirm:
        return

    results = []
    failed = []

    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Memproses file...", total=len(files))

            for f in files:
                progress.update(task, description=f"[cyan]{Path(f).name[:40]}[/cyan]")
                out_path = os.path.join(out_dir, Path(f).name.replace(".pdf", "_compressed.pdf"))
                result = run_compression(f, out_path, mode, level)
                result["input_path"] = f
                results.append(result)
                if not result["success"]:
                    failed.append(f)
                progress.advance(task)
    else:
        for i, f in enumerate(files, 1):
            print(f"  [{i}/{len(files)}] {Path(f).name}...", end=" ")
            out_path = os.path.join(out_dir, Path(f).name.replace(".pdf", "_compressed.pdf"))
            result = run_compression(f, out_path, mode, level)
            result["input_path"] = f
            results.append(result)
            print("✓" if result["success"] else "✗")
            if not result["success"]:
                failed.append(f)

    print_result_table(results)

    if failed:
        print_msg(f"\n  [red]File gagal diproses ({len(failed)}):[/red]")
        for f in failed:
            print_msg(f"    [red]• {f}[/red]")

    input("\n  Tekan Enter untuk lanjut...")


def compress_overwrite(mode: str = "smart", level: int = 6):
    """Menu: Kompresi dan timpa file asli (dengan backup otomatis)."""
    print_msg("\n[bold cyan]═══ Kompresi & Timpa File Asli ═══[/bold cyan]")
    print_msg("  [yellow]⚠ Peringatan: File asli akan ditimpa (backup dibuat otomatis)[/yellow]\n")

    if RICH_AVAILABLE:
        input_path = Prompt.ask("  📂 Path file PDF").strip().strip('"').strip("'")
    else:
        input_path = input("  Path file PDF: ").strip().strip('"').strip("'")

    valid, msg = validate_pdf(input_path)
    if not valid:
        print_msg(f"\n  [red]✗ {msg}[/red]")
        input("\n  Tekan Enter untuk lanjut...")
        return

    print_info_box(input_path)

    if RICH_AVAILABLE:
        confirm = Confirm.ask("\n  ⚠ Lanjutkan? (backup .bak akan dibuat)", default=False)
    else:
        confirm = input("\n  Lanjutkan? File .bak akan dibuat (y/N): ").strip().lower() == "y"

    if not confirm:
        return

    # Buat backup
    backup_path = input_path + ".bak"
    shutil.copy2(input_path, backup_path)
    print_msg(f"  [dim]Backup disimpan: {backup_path}[/dim]")

    # Kompresi ke file temp
    tmp_out = input_path + ".tmp_compressed.pdf"
    result = run_compression(input_path, tmp_out, mode, level, backup=False)

    if result["success"]:
        shutil.move(tmp_out, input_path)
        print_msg(f"\n  [green]✓ File berhasil dikompresi dan ditimpa[/green]")
    else:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        print_msg(f"\n  [red]✗ Gagal: {result.get('error')}[/red]")
        print_msg(f"  [yellow]File asli tidak berubah. Backup: {backup_path}[/yellow]")

    result["input_path"] = input_path
    print_result_table([result])
    input("\n  Tekan Enter untuk lanjut...")


def compare_methods():
    """Menu: Bandingkan semua metode kompresi pada satu file."""
    print_msg("\n[bold cyan]═══ Perbandingan Metode Kompresi ═══[/bold cyan]")

    if RICH_AVAILABLE:
        input_path = Prompt.ask("\n  📂 Path file PDF untuk dibandingkan").strip().strip('"').strip("'")
    else:
        input_path = input("\n  Path file PDF: ").strip().strip('"').strip("'")

    valid, msg = validate_pdf(input_path)
    if not valid:
        print_msg(f"\n  [red]✗ {msg}[/red]")
        input("\n  Tekan Enter untuk lanjut...")
        return

    print_info_box(input_path)
    print_msg("\n  [yellow]⚙ Menguji semua metode...[/yellow]")

    compare_results = []
    methods_config = [
        ("pikepdf (Level 3 - Cepat)", "pikepdf", 3),
        ("pikepdf (Level 6 - Seimbang)", "pikepdf", 6),
        ("pikepdf (Level 9 - Maksimal)", "pikepdf", 9),
        ("pypdf (Lossless)", "pypdf", 6),
    ]

    if shutil.which("qpdf"):
        methods_config.append(("QPDF", "qpdf", 6))

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, mode, level in methods_config:
            out = os.path.join(tmpdir, f"test_{mode}_{level}.pdf")
            if mode == "pikepdf":
                r = compress_lossless_pikepdf(input_path, out, level)
            elif mode == "pypdf":
                r = compress_lossless_pypdf(input_path, out)
            elif mode == "qpdf":
                r = compress_with_qpdf(input_path, out)
            else:
                continue
            r["method"] = name
            r["input_path"] = input_path
            compare_results.append(r)
            print_msg(f"  [dim]✓ {name}[/dim]")

    # Tampilkan tabel perbandingan
    if RICH_AVAILABLE and console:
        table = Table(
            title="🔬 Perbandingan Metode",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold cyan",
        )
        table.add_column("Metode", style="white")
        table.add_column("Ukuran Output", justify="right", style="green")
        table.add_column("Pengurangan", justify="right", style="bold cyan")
        table.add_column("Waktu", justify="right", style="yellow")
        table.add_column("Status", justify="center")

        orig = get_file_size(input_path)
        for r in compare_results:
            comp = r.get("compressed_size", 0)
            _, pct = calculate_reduction(orig, comp)
            status = "[green]✓[/green]" if r.get("success") else "[red]✗[/red]"
            table.add_row(
                r["method"],
                format_size(comp) if r.get("success") else "-",
                pct if r.get("success") else "-",
                f"{r.get('time_elapsed', 0):.2f}s",
                status,
            )

        console.print(table)
    else:
        print("\n  Perbandingan Metode:")
        orig = get_file_size(input_path)
        for r in compare_results:
            comp = r.get("compressed_size", 0)
            _, pct = calculate_reduction(orig, comp)
            print(f"  • {r['method']}: {format_size(comp)} ({pct})")

    input("\n  Tekan Enter untuk lanjut...")


def view_pdf_info():
    """Menu: Lihat informasi detail file PDF."""
    print_msg("\n[bold cyan]═══ Informasi File PDF ═══[/bold cyan]")

    if RICH_AVAILABLE:
        input_path = Prompt.ask("\n  📂 Path file PDF").strip().strip('"').strip("'")
    else:
        input_path = input("\n  Path file PDF: ").strip().strip('"').strip("'")

    print_info_box(input_path)
    input("\n  Tekan Enter untuk lanjut...")


def view_history():
    """Menu: Lihat riwayat kompresi."""
    print_msg("\n[bold cyan]═══ Riwayat Kompresi ═══[/bold cyan]")

    logs = load_log()
    if not logs:
        print_msg("\n  [yellow]Belum ada riwayat kompresi.[/yellow]")
        input("\n  Tekan Enter untuk lanjut...")
        return

    # Tampilkan 20 entri terakhir
    recent = logs[-20:][::-1]

    if RICH_AVAILABLE and console:
        table = Table(
            title=f"📜 Riwayat Kompresi (20 Terakhir dari {len(logs)} total)",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold cyan",
        )
        table.add_column("Waktu", style="dim", width=18)
        table.add_column("File Input", style="white", max_width=25)
        table.add_column("Sebelum", justify="right", style="yellow")
        table.add_column("Sesudah", justify="right", style="green")
        table.add_column("Hemat", justify="right", style="bold cyan")
        table.add_column("Status", justify="center")

        for entry in recent:
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            fname = Path(entry.get("input", "?")).name[:23]
            orig = entry.get("original_size", 0)
            comp = entry.get("compressed_size", 0)
            _, pct = calculate_reduction(orig, comp)
            status = "[green]✓[/green]" if entry.get("success") else "[red]✗[/red]"
            table.add_row(ts, fname, format_size(orig), format_size(comp), pct, status)

        console.print(table)

        # Statistik keseluruhan
        success_logs = [l for l in logs if l.get("success")]
        if success_logs:
            total_orig = sum(l.get("original_size", 0) for l in success_logs)
            total_comp = sum(l.get("compressed_size", 0) for l in success_logs)
            _, pct_all = calculate_reduction(total_orig, total_comp)
            console.print(Panel(
                f"Total file berhasil diproses: [green]{len(success_logs)}[/green]  |  "
                f"Total ruang dihemat: [green]{format_size(total_orig - total_comp)} ({pct_all})[/green]",
                border_style="green",
                title="📈 Statistik Keseluruhan",
            ))
    else:
        for entry in recent:
            ts = entry.get("timestamp", "")[:19]
            fname = Path(entry.get("input", "?")).name
            orig = entry.get("original_size", 0)
            comp = entry.get("compressed_size", 0)
            _, pct = calculate_reduction(orig, comp)
            status = "OK" if entry.get("success") else "GAGAL"
            print(f"  {ts} | {fname} | {format_size(orig)} → {format_size(comp)} ({pct}) | {status}")

    input("\n  Tekan Enter untuk lanjut...")


def clear_history():
    """Menu: Hapus riwayat kompresi."""
    print_msg("\n[bold cyan]═══ Hapus Riwayat ═══[/bold cyan]")
    logs = load_log()
    print_msg(f"\n  Total entri log: [yellow]{len(logs)}[/yellow]")

    if RICH_AVAILABLE:
        confirm = Confirm.ask("  Hapus semua riwayat?", default=False)
    else:
        confirm = input("  Hapus semua riwayat? (y/N): ").strip().lower() == "y"

    if confirm and os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        print_msg("  [green]✓ Riwayat berhasil dihapus.[/green]")
    else:
        print_msg("  [dim]Dibatalkan.[/dim]")

    input("\n  Tekan Enter untuk lanjut...")


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS MENU
# ══════════════════════════════════════════════════════════════════════════════

def settings_menu(config: Dict) -> Dict:
    """Sub-menu pengaturan."""
    while True:
        clear_screen()
        print_msg("\n[bold cyan]═══ ⚙ Pengaturan ═══[/bold cyan]\n")

        mode_names = {
            "smart": "Smart (Otomatis Pilih Terbaik)",
            "pikepdf": "pikepdf (Disarankan)",
            "pypdf": "pypdf (Fallback)",
            "qpdf": "QPDF (Jika Tersedia)",
        }

        if RICH_AVAILABLE and console:
            table = Table(box=box.SIMPLE, show_header=False)
            table.add_column("No", style="bold cyan", width=4)
            table.add_column("Pengaturan", style="white")
            table.add_column("Nilai", style="yellow")
            table.add_row("1", "Mode Kompresi", mode_names.get(config["mode"], config["mode"]))
            table.add_row("2", "Level Kompresi (1-9)", str(config["level"]))
            table.add_row("3", "Folder Output Default", config["output_dir"] or "(Sama dengan input)")
            table.add_row("4", "Verifikasi Setelah Kompresi", "Ya" if config["verify"] else "Tidak")
            table.add_row("5", "Buat Backup Otomatis", "Ya" if config["backup"] else "Tidak")
            table.add_row("0", "[dim]Kembali ke Menu Utama[/dim]", "")
            console.print(table)
            choice = Prompt.ask("\n  Pilih", choices=["0","1","2","3","4","5"], default="0")
        else:
            print(f"  1. Mode Kompresi       : {mode_names.get(config['mode'], config['mode'])}")
            print(f"  2. Level Kompresi (1-9): {config['level']}")
            print(f"  3. Folder Output       : {config['output_dir'] or '(Sama dengan input)'}")
            print(f"  4. Verifikasi          : {'Ya' if config['verify'] else 'Tidak'}")
            print(f"  5. Backup Otomatis     : {'Ya' if config['backup'] else 'Tidak'}")
            print("  0. Kembali")
            choice = input("\n  Pilih: ").strip()

        if choice == "1":
            print_msg("\n  Mode tersedia:")
            modes = list(mode_names.keys())
            for i, (k, v) in enumerate(mode_names.items(), 1):
                print_msg(f"    {i}. {v}")
            if RICH_AVAILABLE:
                idx = Prompt.ask("  Pilih mode", choices=["1","2","3","4"])
            else:
                idx = input("  Pilih mode (1-4): ").strip()
            try:
                config["mode"] = modes[int(idx) - 1]
                print_msg(f"  [green]✓ Mode diubah ke: {config['mode']}[/green]")
            except Exception:
                pass

        elif choice == "2":
            if RICH_AVAILABLE:
                lvl = Prompt.ask("  Level kompresi (1=cepat, 9=maksimal)", default=str(config["level"]))
            else:
                lvl = input(f"  Level (1-9, Enter={config['level']}): ").strip() or str(config["level"])
            try:
                config["level"] = max(1, min(9, int(lvl)))
                print_msg(f"  [green]✓ Level diubah ke: {config['level']}[/green]")
            except Exception:
                pass

        elif choice == "3":
            if RICH_AVAILABLE:
                d = Prompt.ask("  Folder output (kosong = sama dengan input)", default=config["output_dir"] or "")
            else:
                d = input("  Folder output (kosong=sama dengan input): ").strip()
            config["output_dir"] = d or None

        elif choice == "4":
            config["verify"] = not config["verify"]
            print_msg(f"  [green]✓ Verifikasi: {'Aktif' if config['verify'] else 'Nonaktif'}[/green]")

        elif choice == "5":
            config["backup"] = not config["backup"]
            print_msg(f"  [green]✓ Backup otomatis: {'Aktif' if config['backup'] else 'Nonaktif'}[/green]")

        elif choice == "0":
            break

        if choice != "0":
            time.sleep(0.8)

    return config


# ══════════════════════════════════════════════════════════════════════════════
#  HELP MENU
# ══════════════════════════════════════════════════════════════════════════════

def show_help():
    """Tampilkan panduan penggunaan."""
    clear_screen()
    if RICH_AVAILABLE and console:
        help_text = """
[bold cyan]TENTANG APLIKASI[/bold cyan]
PDF Compressor Pro menggunakan teknik kompresi lossless yang TIDAK mengurangi
kualitas visual, teks, atau data dalam file PDF Anda.

[bold cyan]METODE KOMPRESI[/bold cyan]
• [yellow]Smart[/yellow]     : Otomatis mencoba semua metode dan memilih hasil terkecil
• [yellow]pikepdf[/yellow]   : Library Python tercepat, hasil terbaik untuk kebanyakan PDF
• [yellow]pypdf[/yellow]     : Alternatif stabil, re-kompresi stream konten
• [yellow]qpdf[/yellow]      : Tool sistem eksternal, excellent untuk PDF kompleks

[bold cyan]LEVEL KOMPRESI[/bold cyan]
• [green]1-3[/green] : Cepat, hemat CPU — cocok untuk file kecil
• [green]4-6[/green] : Seimbang antara kecepatan dan kompresi (direkomendasikan)  
• [green]7-9[/green] : Maksimal — lambat tapi menghasilkan file paling kecil

[bold cyan]TIPS[/bold cyan]
• PDF yang sudah dikompresi mungkin tidak dapat dikurangi lebih lanjut
• Gunakan mode "Smart" untuk hasil terbaik secara otomatis
• Aktifkan "Verifikasi" untuk memastikan file output valid
• Gunakan "Bandingkan Metode" untuk menemukan metode terbaik per file

[bold cyan]FORMAT FILE YANG DIDUKUNG[/bold cyan]
• File PDF standar (tidak terenkripsi)
• PDF versi 1.0 hingga 2.0
• File PDF hasil scan (tidak dapat dikompres, hanya re-struktur)

[bold cyan]BATASAN[/bold cyan]
• File PDF terenkripsi tidak dapat diproses
• File PDF yang rusak tidak dapat diproses
        """
        console.print(Panel(help_text, title="❓ Panduan Penggunaan", border_style="bright_blue"))
    else:
        print("""
  PANDUAN PENGGUNAAN PDF COMPRESSOR PRO
  ======================================
  Aplikasi ini menggunakan kompresi LOSSLESS yang tidak mengurangi kualitas.
  
  METODE:
    Smart   - Otomatis pilih metode terbaik
    pikepdf - Library Python, hasil terbaik
    pypdf   - Alternatif stabil
    qpdf    - Tool eksternal (jika tersedia)
  
  LEVEL 1-3: Cepat | 4-6: Seimbang | 7-9: Maksimal
        """)
    input("\n  Tekan Enter untuk kembali...")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

def main_menu():
    """Menu utama aplikasi."""
    config = {
        "mode": "smart",
        "level": 6,
        "output_dir": None,
        "verify": True,
        "backup": False,
    }

    while True:
        print_banner()

        qpdf_status = "[green]✓ Tersedia[/green]" if shutil.which("qpdf") else "[red]✗ Tidak Ada[/red]"
        if RICH_AVAILABLE and console:
            # Status bar
            status_items = [
                f"Mode: [yellow]{config['mode']}[/yellow]",
                f"Level: [yellow]{config['level']}[/yellow]",
                f"QPDF: {qpdf_status}",
            ]
            console.print("  " + "  |  ".join(status_items))
            console.print(Rule(style="bright_blue"))

            # Menu items
            menu_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
            menu_table.add_column("No", style="bold cyan", width=4)
            menu_table.add_column("Menu", style="white")
            menu_table.add_column("Deskripsi", style="dim")

            menu_table.add_row("", "[bold]── KOMPRESI ──[/bold]", "")
            menu_table.add_row("1", "Kompresi Satu File", "Kompresi file PDF tunggal")
            menu_table.add_row("2", "Kompresi Batch", "Kompresi banyak file sekaligus")
            menu_table.add_row("3", "Kompresi & Timpa File", "Timpa file asli (dengan backup)")
            menu_table.add_row("", "", "")
            menu_table.add_row("", "[bold]── ANALISIS ──[/bold]", "")
            menu_table.add_row("4", "Informasi File PDF", "Lihat detail & metadata PDF")
            menu_table.add_row("5", "Bandingkan Metode", "Uji semua metode pada satu file")
            menu_table.add_row("", "", "")
            menu_table.add_row("", "[bold]── RIWAYAT & LOG ──[/bold]", "")
            menu_table.add_row("6", "Lihat Riwayat", "Riwayat kompresi sebelumnya")
            menu_table.add_row("7", "Hapus Riwayat", "Bersihkan log kompresi")
            menu_table.add_row("", "", "")
            menu_table.add_row("", "[bold]── SISTEM ──[/bold]", "")
            menu_table.add_row("8", "Pengaturan", "Konfigurasi mode & level")
            menu_table.add_row("9", "Panduan", "Petunjuk penggunaan")
            menu_table.add_row("0", "[red]Keluar[/red]", "Tutup aplikasi")

            console.print(menu_table)
            choice = Prompt.ask(
                "\n  [bold cyan]Pilih menu[/bold cyan]",
                choices=["0","1","2","3","4","5","6","7","8","9"],
                default="1",
            )
        else:
            print(f"  Mode: {config['mode']} | Level: {config['level']}")
            print("-" * 50)
            print("  ── KOMPRESI ──")
            print("  1. Kompresi Satu File")
            print("  2. Kompresi Batch (Banyak File)")
            print("  3. Kompresi & Timpa File Asli")
            print()
            print("  ── ANALISIS ──")
            print("  4. Informasi File PDF")
            print("  5. Bandingkan Metode Kompresi")
            print()
            print("  ── RIWAYAT ──")
            print("  6. Lihat Riwayat Kompresi")
            print("  7. Hapus Riwayat")
            print()
            print("  ── SISTEM ──")
            print("  8. Pengaturan")
            print("  9. Panduan")
            print("  0. Keluar")
            choice = input("\n  Pilih (0-9): ").strip()

        if choice == "1":
            compress_single_file(config["output_dir"], config["mode"], config["level"])
        elif choice == "2":
            compress_batch_files(config["output_dir"], config["mode"], config["level"])
        elif choice == "3":
            compress_overwrite(config["mode"], config["level"])
        elif choice == "4":
            view_pdf_info()
        elif choice == "5":
            compare_methods()
        elif choice == "6":
            view_history()
        elif choice == "7":
            clear_history()
        elif choice == "8":
            config = settings_menu(config)
        elif choice == "9":
            show_help()
        elif choice == "0":
            if RICH_AVAILABLE and console:
                console.print("\n  [bold cyan]Terima kasih telah menggunakan PDF Compressor Pro! 👋[/bold cyan]\n")
            else:
                print("\n  Terima kasih! Sampai jumpa.\n")
            sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND LINE INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

def cli_mode():
    """Mode command-line langsung tanpa menu interaktif."""
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{VERSION} - Kompresi PDF Lossless",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input", nargs="?", help="File PDF input")
    parser.add_argument("-o", "--output", help="Path file output")
    parser.add_argument("-m", "--mode", default="smart",
                        choices=["smart", "pikepdf", "pypdf", "qpdf"],
                        help="Metode kompresi (default: smart)")
    parser.add_argument("-l", "--level", type=int, default=6,
                        help="Level kompresi 1-9 (default: 6)")
    parser.add_argument("-b", "--batch", help="Folder/pola glob untuk batch processing")
    parser.add_argument("--no-verify", action="store_true", help="Lewati verifikasi output")
    parser.add_argument("--info", action="store_true", help="Tampilkan info PDF saja")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} v{VERSION}")

    args = parser.parse_args()

    if args.batch:
        if os.path.isdir(args.batch):
            files = glob.glob(os.path.join(args.batch, "**", "*.pdf"), recursive=True)
        else:
            files = glob.glob(args.batch)
            files = [f for f in files if f.lower().endswith(".pdf")]

        out_dir = args.output or "output_compressed"
        os.makedirs(out_dir, exist_ok=True)
        results = []
        for f in files:
            out = os.path.join(out_dir, Path(f).name.replace(".pdf", "_compressed.pdf"))
            r = run_compression(f, out, args.mode, args.level, not args.no_verify)
            r["input_path"] = f
            results.append(r)
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {Path(f).name}: {format_size(r.get('original_size',0))} → "
                  f"{format_size(r.get('compressed_size',0))}")
        print_result_table(results)
        return

    if args.input:
        if args.info:
            print_info_box(args.input)
            return

        out = args.output or generate_output_path(args.input)
        r = run_compression(args.input, out, args.mode, args.level, not args.no_verify)
        r["input_path"] = args.input
        print_result_table([r])
        if r["success"]:
            print(f"\nOutput: {out}")
        sys.exit(0 if r.get("success") else 1)

    # Tidak ada argumen, masuk mode interaktif
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        # Jika ada argumen CLI, jalankan mode CLI
        if len(sys.argv) > 1:
            result = cli_mode()
            if result is not False:
                sys.exit(0)
            # Jika tidak ada file input di CLI, lanjut ke menu interaktif
            if not any(sys.argv[1:]):
                main_menu()
        else:
            # Mode interaktif
            main_menu()
    except KeyboardInterrupt:
        print("\n\n  [Dibatalkan oleh pengguna]\n")
        sys.exit(0)
