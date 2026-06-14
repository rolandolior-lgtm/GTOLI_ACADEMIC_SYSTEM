#!/usr/bin/env python3
"""
Genere un CSV de depart depuis le PDF du referentiel de mathematiques.

Le but n'est pas de deviner parfaitement tous les tableaux du PDF, mais de
produire une base propre niveau/champ/bloc que l'on peut ensuite completer
dans VS Code avant de lancer gtoli_codegen.py.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from gtoli_codegen import slugify


FIELDNAMES = [
    "niveau",
    "matiere",
    "champ",
    "bloc",
    "categorie",
    "type_document",
    "competence",
    "contenu_referentiel",
    "attendu_referentiel",
    "objectif",
    "prerequis",
    "activites",
    "evaluation",
    "mots_cles",
    "source_page",
    "sortie",
]


def clean_line(value: str) -> str:
    value = " ".join(value.replace("\u00a0", " ").split())
    replacements = {
        "RELA TION": "RELATION",
        "V ARIABLES": "VARIABLES",
        "ORGANISA TION": "ORGANISATION",
        "ST A TISTIQUE": "STATISTIQUE",
        "T racer": "Tracer",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value.strip()


def champ_folder_name(champ: str) -> str:
    match = re.search(r"CHAMP\s+([1-4])", champ)
    if not match:
        return slugify(champ, "champ")
    return {
        "1": "champ_1_espace_geometrie",
        "2": "champ_2_grandeurs_relations",
        "3": "champ_3_arithmetique_algebre",
        "4": "champ_4_donnees_statistique",
    }[match.group(1)]


def read_pdf_pages(path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise RuntimeError("Installe `pypdf` pour extraire un PDF: python3 -m pip install pypdf") from exc

    reader = PdfReader(str(path))
    return [(index, page.extract_text() or "") for index, page in enumerate(reader.pages, start=1)]


def extract_rows(pdf: Path, levels: set[str], matiere: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    current_level = ""
    current_champ = ""

    for page_number, text in read_pdf_pages(pdf):
        for raw_line in text.splitlines():
            line = clean_line(raw_line)
            if not line:
                continue

            if re.fullmatch(r"P[1-6]", line):
                current_level = line
                continue

            if line.startswith("CHAMP "):
                current_champ = line
                continue

            block_match = re.match(r"^([1-4]\.[1-9])\.\s+(.+)$", line)
            if not block_match or not current_level or not current_champ:
                continue

            if levels and current_level not in levels:
                continue

            block_code = block_match.group(1)
            block_title = block_match.group(2)
            key = (current_level, current_champ, block_code)
            if key in seen:
                continue
            seen.add(key)

            champ_slug = champ_folder_name(current_champ)
            bloc_slug = slugify(f"{block_code}_{block_title}", "bloc")
            output_path = (
                Path("primaire")
                / matiere
                / current_level
                / champ_slug
                / bloc_slug
                / f"fiche_bloc_{bloc_slug}_{current_level}_GTOLI.md"
            )

            rows.append(
                {
                    "niveau": current_level,
                    "matiere": matiere,
                    "champ": current_champ,
                    "bloc": f"{block_code}. {block_title}",
                    "categorie": "bloc",
                    "type_document": "fiche_referentiel",
                    "competence": block_title,
                    "contenu_referentiel": f"{current_champ} / {block_code}. {block_title}",
                    "attendu_referentiel": "",
                    "objectif": "Transformer ce bloc du referentiel en fiches, activites et evaluations.",
                    "prerequis": "",
                    "activites": "",
                    "evaluation": "",
                    "mots_cles": f"{current_level}, mathematiques, {block_code}",
                    "source_page": str(page_number),
                    "sortie": str(output_path),
                }
            )

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cree un CSV GTOLI de depart depuis un referentiel PDF.")
    parser.add_argument("--pdf", required=True, type=Path, help="PDF du referentiel.")
    parser.add_argument("--out", required=True, type=Path, help="CSV de sortie.")
    parser.add_argument("--level", action="append", default=[], help="Niveau a extraire: P1, P2... Peut etre repete.")
    parser.add_argument("--matiere", default="MST", help="Matiere a inscrire dans le CSV.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    levels = {level.upper() for level in args.level}
    rows = extract_rows(args.pdf, levels, args.matiere)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} ligne(s) ecrites dans {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
