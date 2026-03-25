"""tab_to_pdf.py — Export a VFX TAB spreadsheet to a PDF with thumbnails.

Usage:
    tab-to-pdf <tab_file> [-t <images_dir>] [-o <output_pdf>]

Layout per VFX ID:
    - Section header (dark banner with VFX ID + shot number)
    - Image on the LEFT, fields on the RIGHT in a 3-column grid

Thumbnail matching:
    Filenames like '0000 GDN_053_0010.jpg' are matched by extracting the part
    after the leading digits+space prefix.  Plain '<VFX_ID>.jpg' also works.

Columns are read at runtime from the TAB file header — no hardcoded schema.
"""

import argparse
import os
import re
import sys

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Image, KeepTogether, Paragraph, SimpleDocTemplate,
        Spacer, Table, TableStyle,
    )
except ImportError:
    print("Error: reportlab is required. Install with: pipx inject vfx-turnover reportlab")
    sys.exit(1)


THUMB_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}

# Columns not shown in the field grid (handled separately or irrelevant)
SKIP_COLS = {'#', 'Thumbnail', 'Name'}

# Page geometry
PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm
USABLE_W = PAGE_W - 2 * MARGIN      # ~538 pt

THUMB_COL_W = 5.5 * cm
FIELDS_COL_W = USABLE_W - THUMB_COL_W

FIELDS_PER_ROW = 3
CELL_W = FIELDS_COL_W / FIELDS_PER_ROW

# Palette
HEADER_BG   = colors.HexColor('#1a2535')
CARD_BORDER = colors.HexColor('#9aabb8')
ROW_ALT     = colors.HexColor('#f4f7fa')
NO_THUMB_BG = colors.HexColor('#eef1f4')


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_tab(path: str) -> tuple[list[str], list[dict]]:
    """Return (headers, rows) from a TAB file.

    The header line may begin with '#\\t' (Avid format); that leading '#' is
    kept as the first column name so row numbering is preserved.
    """
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f if l.strip()]
    if not lines:
        return [], []

    headers = lines[0].split('\t')
    rows = []
    for line in lines[1:]:
        parts = line.split('\t')
        parts += [''] * (len(headers) - len(parts))
        rows.append(dict(zip(headers, [p.strip() for p in parts])))
    return headers, rows


# ── Image lookup ──────────────────────────────────────────────────────────────

_PREFIX_RE = re.compile(r'^\d+\s+')

def build_image_map(thumbdir: str) -> dict[str, str]:
    """Return {vfx_id: filepath} for all images in thumbdir.

    Handles filenames like '0000 GDN_053_0010.jpg' by stripping the leading
    digits-and-space prefix to extract the VFX ID.
    """
    mapping: dict[str, str] = {}
    if not thumbdir or not os.path.isdir(thumbdir):
        return mapping
    for fname in os.listdir(thumbdir):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in THUMB_EXTENSIONS:
            continue
        stem = os.path.splitext(fname)[0]
        vfx_id = _PREFIX_RE.sub('', stem)   # strip '0000 ' prefix if present
        mapping[vfx_id] = os.path.join(thumbdir, fname)
    return mapping


# ── Styles ────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'DocTitle', parent=base['Normal'],
            fontSize=16, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1a2535'),
            leading=20, spaceAfter=4,
        ),
        'subtitle': ParagraphStyle(
            'Subtitle', parent=base['Normal'],
            fontSize=9, fontName='Helvetica',
            textColor=colors.HexColor('#6a8090'),
            leading=13, spaceAfter=16,
        ),
        'card_header': ParagraphStyle(
            'CardHeader', parent=base['Normal'],
            fontSize=11, fontName='Helvetica-Bold',
            textColor=colors.white, leading=15,
        ),
        'counter': ParagraphStyle(
            'Counter', parent=base['Normal'],
            fontSize=9, fontName='Helvetica',
            textColor=colors.HexColor('#8ba3b8'), leading=15,
        ),
        'label': ParagraphStyle(
            'Label', parent=base['Normal'],
            fontSize=7, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#4a6070'), leading=10,
        ),
        'value': ParagraphStyle(
            'Value', parent=base['Normal'],
            fontSize=8, fontName='Helvetica',
            textColor=colors.HexColor('#1a2535'), leading=11,
        ),
        'no_thumb': ParagraphStyle(
            'NoThumb', parent=base['Normal'],
            fontSize=7, fontName='Helvetica',
            textColor=colors.HexColor('#aabbcc'),
            leading=10, alignment=1,
        ),
    }


# ── Field grid ────────────────────────────────────────────────────────────────

def _field_grid(row: dict, headers: list[str], styles: dict) -> Table:
    """Build a 3-column label/value grid for the fields of one shot."""
    pairs = [
        (col, row.get(col, '').strip())
        for col in headers
        if col not in SKIP_COLS
    ]

    # Group into rows of FIELDS_PER_ROW, padding the last row if needed
    cell_rows: list[list] = []
    for i in range(0, len(pairs), FIELDS_PER_ROW):
        chunk = pairs[i:i + FIELDS_PER_ROW]
        while len(chunk) < FIELDS_PER_ROW:
            chunk.append(('', ''))

        label_row = [Paragraph(lbl, styles['label']) for lbl, _ in chunk]
        value_row = [Paragraph(val or '—', styles['value']) for _, val in chunk]
        cell_rows.append(label_row)
        cell_rows.append(value_row)

    if not cell_rows:
        return Paragraph('', styles['value'])

    tbl = Table(cell_rows, colWidths=[CELL_W] * FIELDS_PER_ROW, hAlign='LEFT')

    ts = [
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]
    # Shade alternating value rows (indices 1, 3, 5, …)
    for r in range(1, len(cell_rows), 2):
        if (r // 2) % 2 == 0:
            ts.append(('BACKGROUND', (0, r), (-1, r), ROW_ALT))
    tbl.setStyle(TableStyle(ts))
    return tbl


# ── Card builder ──────────────────────────────────────────────────────────────

def build_card(row: dict, headers: list[str], thumb_path: str | None,
               styles: dict) -> Table:
    vfx_id  = row.get('Name', '').strip()
    counter = row.get('#', '').strip()

    # Header banner
    header_tbl = Table(
        [[Paragraph(vfx_id, styles['card_header']),
          Paragraph(f'# {counter}', styles['counter'])]],
        colWidths=[USABLE_W - 2.5 * cm, 2.5 * cm],
    )
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), HEADER_BG),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (0, -1),  10),
        ('RIGHTPADDING',  (-1, 0), (-1, -1), 10),
        ('ALIGN',         (1, 0), (1, -1),  'RIGHT'),
    ]))

    # Thumbnail (left)
    THUMB_MAX_W = THUMB_COL_W - 0.6 * cm
    THUMB_MAX_H = 3.2 * cm

    if thumb_path:
        thumb_cell = Image(thumb_path,
                           width=THUMB_MAX_W, height=THUMB_MAX_H,
                           kind='proportional')
    else:
        thumb_cell = Table(
            [[Paragraph('no thumbnail', styles['no_thumb'])]],
            colWidths=[THUMB_MAX_W], rowHeights=[THUMB_MAX_H],
        )
        thumb_cell.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NO_THUMB_BG),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ]))

    # Field grid (right)
    fields = _field_grid(row, headers, styles)

    content_tbl = Table(
        [[thumb_cell, fields]],
        colWidths=[THUMB_COL_W, FIELDS_COL_W],
    )
    content_tbl.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (0, -1),  6),
        ('RIGHTPADDING',  (0, 0), (0, -1),  8),
        ('LEFTPADDING',   (1, 0), (1, -1),  4),
    ]))

    card = Table([[header_tbl], [content_tbl]], colWidths=[USABLE_W])
    card.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('LINEBELOW',     (0, 0), (0, 0),   0.5, CARD_BORDER),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return card


# ── PDF generation ────────────────────────────────────────────────────────────

def _add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#9aabb8'))
    canvas.drawRightString(PAGE_W - MARGIN, 1.1 * cm, str(doc.page))
    canvas.restoreState()


def generate_pdf(tab_path: str, thumbdir: str | None, output_path: str):
    headers, rows = parse_tab(tab_path)
    if not rows:
        print("Error: no data rows found in TAB file.", file=sys.stderr)
        sys.exit(1)

    image_map = build_image_map(thumbdir) if thumbdir else {}
    styles = _styles()

    print(f"  Shots:      {len(rows)}")
    if thumbdir:
        matched = sum(1 for r in rows if r.get('Name', '') in image_map)
        print(f"  Thumbnails: {matched}/{len(rows)} matched")

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2 * cm, bottomMargin=1.8 * cm,
    )

    tab_stem = os.path.splitext(os.path.basename(tab_path))[0]
    story = [
        Paragraph(tab_stem, styles['title']),
        Paragraph(f'{len(rows)} shots', styles['subtitle']),
    ]

    for row in rows:
        vfx_id = row.get('Name', '').strip()
        if not vfx_id:
            continue
        thumb = image_map.get(vfx_id)
        card  = build_card(row, headers, thumb, styles)
        story.append(KeepTogether([card, Spacer(1, 0.35 * cm)]))

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    print(f"  PDF saved:  {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Export a VFX TAB spreadsheet to a PDF with thumbnails.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Thumbnail filenames: "0000 GDN_053_0010.jpg" or plain "GDN_053_0010.jpg"\n\n'
            'Example:\n'
            '  tab-to-pdf SCENA_53_TAB.txt -t ./thumbnails -o scena_53.pdf'
        ),
    )
    parser.add_argument('tab_file', help='TAB-delimited file (.txt)')
    parser.add_argument('-t', '--thumbnails', metavar='DIR',
                        help='Directory containing thumbnail images')
    parser.add_argument('-o', '--output', metavar='PDF',
                        help='Output PDF path (default: same stem as TAB file)')
    args = parser.parse_args()

    if not os.path.exists(args.tab_file):
        sys.exit(f"Error: file not found: {args.tab_file}")
    if args.thumbnails and not os.path.isdir(args.thumbnails):
        sys.exit(f"Error: thumbnails directory not found: {args.thumbnails}")

    output_path = args.output or os.path.splitext(args.tab_file)[0] + '.pdf'

    if os.path.exists(output_path):
        resp = input(f"Overwrite {os.path.basename(output_path)}? [y/N] ").strip().lower()
        if resp != 'y':
            print("Cancelled.")
            sys.exit(0)

    print(f"Generating PDF: {os.path.basename(args.tab_file)}")
    generate_pdf(args.tab_file, args.thumbnails, output_path)


if __name__ == '__main__':
    main()
