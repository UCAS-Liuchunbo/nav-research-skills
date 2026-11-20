#!/usr/bin/env python3
"""Inspect a .pptx file to extract exact slide geometry, image slots, fonts, accent colors, and text.

Usage:
    python inspect_pptx_layout.py /path/to/deck.pptx [--slide 1] [--extract-media /path/to/out_dir]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

EMU_PER_CM = 914400.0 / 2.54
NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def inspect_pptx(pptx_path: Path, slide_num: int | None = None, extract_dir: Path | None = None) -> None:
    with zipfile.ZipFile(pptx_path) as z:
        pres = ET.fromstring(z.read('ppt/presentation.xml'))
        sld_sz = pres.find('.//p:sldSz', NS)
        cx, cy = int(sld_sz.attrib['cx']), int(sld_sz.attrib['cy'])
        print(f'File: {pptx_path}')
        print(f'Slide Size: {cx / EMU_PER_CM:.2f} cm x {cy / EMU_PER_CM:.2f} cm (ratio {cx / cy:.4f})')

        slides = sorted(
            [n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')],
            key=lambda s: int(os.path.basename(s).replace('slide', '').replace('.xml', '')),
        )
        print(f'Total Slides: {len(slides)}\n')

        for idx, slide_xml in enumerate(slides, start=1):
            if slide_num is not None and idx != slide_num:
                continue
            print(f'=== Slide {idx} ({os.path.basename(slide_xml)}) ===')
            rels_path = f'ppt/slides/_rels/{os.path.basename(slide_xml)}.rels'
            rel_map = {}
            if rels_path in z.namelist():
                rels = ET.fromstring(z.read(rels_path))
                rel_map = {r.attrib['Id']: r.attrib['Target'] for r in rels}

            root = ET.fromstring(z.read(slide_xml))
            fonts, colors, texts = set(), set(), []
            for el in root.iter():
                if el.tag.endswith('ea') or el.tag.endswith('latin'):
                    tf = el.attrib.get('typeface')
                    if tf:
                        fonts.add(tf)
                elif el.tag.endswith('srgbClr'):
                    val = el.attrib.get('val')
                    if val:
                        colors.add(f'#{val}')
                elif el.tag == f'{{{NS["a"]}}}t' and el.text and el.text.strip():
                    texts.append(el.text.strip())

            print('Fonts:', ', '.join(sorted(fonts)) or '(theme default)')
            print('Explicit RGB Colors:', ', '.join(sorted(colors)) or '(theme colors)')
            print('Text Summary:', ' | '.join(texts)[:300])

            pics = root.findall('.//p:pic', NS)
            print(f'Pictures ({len(pics)}):')
            for pic in pics:
                nv = pic.find('.//p:cNvPr', NS)
                blip = pic.find('.//a:blip', NS)
                xfrm = pic.find('.//p:spPr/a:xfrm', NS)
                if xfrm is None or blip is None:
                    continue
                off = xfrm.find('a:off', NS)
                ext = xfrm.find('a:ext', NS)
                if off is None or ext is None:
                    continue
                rid = blip.attrib.get(f'{{{NS["r"]}}}embed')
                target = rel_map.get(rid, '')
                x, y = int(off.attrib['x']), int(off.attrib['y'])
                w, h = int(ext.attrib['cx']), int(ext.attrib['cy'])
                name = nv.attrib.get('name', 'Picture') if nv is not None else 'Picture'
                print(
                    f'  - {name} -> {target} | '
                    f'x={x / EMU_PER_CM:.2f} cm, y={y / EMU_PER_CM:.2f} cm, '
                    f'w={w / EMU_PER_CM:.2f} cm, h={h / EMU_PER_CM:.2f} cm '
                    f'(ratio {w / h:.3f})'
                )
                if extract_dir is not None and target:
                    media_member = os.path.normpath(os.path.join('ppt/slides', target)).replace('\\', '/')
                    if media_member in z.namelist():
                        extract_dir.mkdir(parents=True, exist_ok=True)
                        out_file = extract_dir / os.path.basename(media_member)
                        out_file.write_bytes(z.read(media_member))
                        print(f'    extracted -> {out_file}')
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pptx', type=Path, help='Path to target .pptx file')
    parser.add_argument('--slide', type=int, default=None, help='Inspect only this 1-based slide index')
    parser.add_argument('--extract-media', type=Path, default=None, help='Optional folder to extract slide images')
    args = parser.parse_args()
    inspect_pptx(args.pptx, slide_num=args.slide, extract_dir=args.extract_media)


if __name__ == '__main__':
    main()
