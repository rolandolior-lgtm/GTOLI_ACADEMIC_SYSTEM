#!/usr/bin/env python3
"""
GTOLI Code Factory

Petit generateur local pour transformer un tableau synoptique CSV et un ou
plusieurs referentiels Markdown/TXT/PDF en fichiers Markdown + script Bash.

Usage rapide:
  python3 gtoli_codegen.py \
    --tableau exemple_tableau_synoptique.csv \
    --referentiel exemple_referentiel_mst_p1.md \
    --dest sortie_gtoli \
    --bash-script creer_fichiers_gtoli.sh
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from string import Template
from typing import Iterable


APP_VERSION = "0.2.0"

DEFAULT_TEMPLATE = """---
gtoli_version: "$app_version"
niveau: "$niveau"
matiere: "$matiere"
champ: "$champ"
bloc: "$bloc"
type_document: "$document_type"
categorie_referentiel: "$categorie"
slug: "$slug"
source_ligne: "$source_line"
source_page: "$source_page"
generated_at: "$generated_at"
---

# $titre

## Intention pedagogique
$objectif

## Competence cible
$competence

## Ancrage referentiel
- Champ: $champ
- Bloc: $bloc
- Type: $categorie
- Page/source: $source_page

### Contenu d'apprentissage
$contenu_referentiel

### Attendu officiel
$attendu_referentiel

## Prerequis
$prerequis

## Activites proposees
$activites

## Evaluation
$evaluation

## Mots-cles
$mots_cles

## Contexte referentiel
$referentiel_context

## Notes de production
- Fichier genere depuis le tableau synoptique: `$tableau_source`.
- Complete ce document dans VS Code, puis versionne-le dans GitHub.
$extra_fields
"""

CANONICAL_FIELDS = {
    "niveau": ("niveau", "classe", "annee", "cycle"),
    "matiere": ("matiere", "discipline", "cours"),
    "champ": ("champ", "domaine", "axe", "unite", "uaa"),
    "bloc": ("bloc", "chapitre", "section", "axe_referentiel"),
    "categorie": ("categorie", "type_apprentissage", "savoir_savoir_faire_competence"),
    "contenu_referentiel": ("contenu_referentiel", "contenu", "contenus", "contenu_apprentissage"),
    "attendu_referentiel": ("attendu_referentiel", "attendu", "attendus", "attendu_officiel"),
    "source_page": ("source_page", "page", "pages", "reference", "source"),
    "competence": ("competence", "competence_cible", "intitule", "titre"),
    "document_type": ("type", "type_document", "document", "format_document"),
    "slug": ("slug", "id", "code", "identifiant"),
    "objectif": ("objectif", "objectifs", "intention", "intention_pedagogique"),
    "prerequis": ("prerequis", "pre_requis", "prealables"),
    "activites": ("activites", "activite", "taches", "demarches"),
    "evaluation": ("evaluation", "criteres", "criteres_evaluation"),
    "mots_cles": ("mots_cles", "tags", "keywords", "motscles"),
    "sortie": ("sortie", "chemin", "path", "fichier"),
}


def normalize_key(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def slugify(value: str, fallback: str = "item") -> str:
    value = normalize_key(value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or fallback


def safe_text(value: str | None, fallback: str = "- A completer.") -> str:
    value = (value or "").strip()
    return value if value else fallback


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Lecture PDF impossible: installe `pypdf` ou utilise un referentiel exporte en .txt/.md."
        ) from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"===== PAGE {index} =====\n\n{text.strip()}")
    return "\n\n".join(parts)


def read_text_source(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Tableau introuvable: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        delimiter_counts = {
            ";": first_line.count(";"),
            ",": first_line.count(","),
            "\t": first_line.count("\t"),
        }
        delimiter = max(delimiter_counts, key=delimiter_counts.get)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;	")
            if delimiter_counts[delimiter] > 0:
                dialect.delimiter = delimiter
        except csv.Error:
            class FallbackDialect(csv.excel):
                pass

            FallbackDialect.delimiter = delimiter if delimiter_counts[delimiter] > 0 else ","
            dialect = FallbackDialect
        reader = csv.DictReader(handle, dialect=dialect)
        rows = [dict(row) for row in reader]

    if not rows:
        raise ValueError("Le tableau synoptique ne contient aucune ligne.")
    return rows


def canonicalize_row(row: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    normalized = {normalize_key(k): (v or "").strip() for k, v in row.items() if k is not None}

    result: dict[str, str] = {}
    used_keys: set[str] = set()
    for canonical, aliases in CANONICAL_FIELDS.items():
        for alias in aliases:
            key = normalize_key(alias)
            if key in normalized and normalized[key]:
                result[canonical] = normalized[key]
                used_keys.add(key)
                break
        result.setdefault(canonical, "")

    extras = {k: v for k, v in normalized.items() if k not in used_keys and v}
    return result, extras


def split_context_chunks(text: str) -> list[str]:
    chunks = re.split(r"\n*===== PAGE \d+ =====\n*", text)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    return chunks or [text.strip()]


def select_context_excerpt(text: str, filters: list[str], max_chars: int) -> str:
    chunks = split_context_chunks(text)
    active_filters = [term.lower() for term in filters if term.strip()]
    selected: list[str] = []

    if active_filters:
        selected = [
            chunk for chunk in chunks if all(term in chunk.lower() for term in active_filters)
        ]
        if not selected:
            selected = [
                chunk for chunk in chunks if any(term in chunk.lower() for term in active_filters)
            ]
        selected.sort(key=lambda chunk: context_score(chunk, active_filters), reverse=True)

    if not selected:
        selected = chunks

    excerpt = "\n\n---\n\n".join(selected).strip()
    return excerpt if len(excerpt) <= max_chars else excerpt[:max_chars].rstrip() + "\n\n[Extrait tronque.]"


def context_score(chunk: str, filters: list[str]) -> int:
    score = 0
    lower_chunk = chunk.lower()
    lines = {line.strip().lower() for line in chunk.splitlines()}
    for term in filters:
        if term in lines:
            score += 10
        if re.search(rf"(?m)^\s*{re.escape(term)}\s*$", lower_chunk):
            score += 10
        score += lower_chunk.count(term)
    return score


def load_referentiel_context(paths: Iterable[Path], max_chars: int, filters: list[str]) -> str:
    sections: list[str] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Referentiel introuvable: {path}")
        text = read_text_source(path).strip()
        if not text:
            continue
        excerpt = select_context_excerpt(text, filters, max_chars)
        sections.append(f"### {path.name}\n\n{excerpt}")
    return "\n\n".join(sections) if sections else "- Aucun referentiel fourni."


def preferred_document_type(row: dict[str, str]) -> str:
    return row["document_type"] or row["categorie"] or "fiche"


def preferred_title_source(row: dict[str, str]) -> str:
    return (
        row["competence"]
        or row["attendu_referentiel"]
        or row["contenu_referentiel"]
        or row["bloc"]
        or "Competence a definir"
    )


def build_relative_path(row: dict[str, str], root_prefix: str, matiere_default: str) -> Path:
    if row["sortie"]:
        output = Path(row["sortie"])
        return output if output.suffix else output.with_suffix(".md")

    niveau = slugify(row["niveau"], "niveau")
    matiere = slugify(row["matiere"] or matiere_default, "matiere")
    champ = slugify(row["champ"], "champ")
    bloc = slugify(row["bloc"], "bloc")
    document_type = slugify(preferred_document_type(row), "fiche")
    competence = slugify(row["slug"] or preferred_title_source(row), "competence")
    filename = f"{document_type}_{competence}_{niveau}_GTOLI.md"
    base = Path(root_prefix) if root_prefix else Path()
    return base / matiere / niveau / champ / bloc / filename


def make_title(row: dict[str, str]) -> str:
    document_type = safe_text(preferred_document_type(row), "Fiche")
    competence = safe_text(preferred_title_source(row), "Competence a definir")
    niveau = safe_text(row["niveau"], "Niveau a definir")
    return f"{document_type} - {competence} ({niveau})"


def render_extra_fields(extras: dict[str, str]) -> str:
    if not extras:
        return "- Champs supplementaires: aucun."
    lines = ["- Champs supplementaires:"]
    for key in sorted(extras):
        lines.append(f"  - `{key}`: {extras[key]}")
    return "\n".join(lines)


def render_markdown(
    row: dict[str, str],
    extras: dict[str, str],
    template: Template,
    context: str,
    source_line: int,
    tableau_source: Path,
) -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    values = {
        "app_version": APP_VERSION,
        "niveau": safe_text(row["niveau"], ""),
        "matiere": safe_text(row["matiere"], ""),
        "champ": safe_text(row["champ"], ""),
        "bloc": safe_text(row["bloc"], ""),
        "categorie": safe_text(row["categorie"], ""),
        "document_type": safe_text(preferred_document_type(row), "Fiche"),
        "slug": slugify(row["slug"] or preferred_title_source(row), "competence"),
        "source_line": str(source_line),
        "source_page": safe_text(row["source_page"], ""),
        "generated_at": now,
        "titre": make_title(row),
        "objectif": safe_text(
            row["objectif"],
            "Transformer cet attendu du referentiel en sequence, activites et evaluation exploitables.",
        ),
        "competence": safe_text(preferred_title_source(row)),
        "contenu_referentiel": safe_text(row["contenu_referentiel"]),
        "attendu_referentiel": safe_text(row["attendu_referentiel"]),
        "prerequis": safe_text(row["prerequis"]),
        "activites": safe_text(row["activites"]),
        "evaluation": safe_text(row["evaluation"]),
        "mots_cles": safe_text(row["mots_cles"]),
        "referentiel_context": context,
        "tableau_source": str(tableau_source),
        "extra_fields": render_extra_fields(extras),
    }
    return template.safe_substitute(values).rstrip() + "\n"


def ensure_relative(path: Path) -> Path:
    if path.is_absolute():
        raise ValueError(f"Le chemin de sortie doit etre relatif: {path}")
    if ".." in path.parts:
        raise ValueError(f"Le chemin de sortie ne peut pas remonter de dossier: {path}")
    return path


def write_bash_script(path: Path, generated_files: list[tuple[Path, str]]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'DEST="${1:-generated_gtoli}"',
        'mkdir -p "$DEST"',
        "",
    ]

    for rel_path, content in generated_files:
        rel = str(rel_path)
        delimiter = "GTOLI_MD_EOF"
        while delimiter in content:
            delimiter += "_X"
        lines.append(f'mkdir -p "$(dirname "$DEST/{rel}")"')
        lines.append(f"cat > \"$DEST/{rel}\" <<'{delimiter}'")
        lines.append(content.rstrip())
        lines.append(delimiter)
        lines.append("")

    lines.append('echo "Generation terminee dans: $DEST"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o755)


def open_in_vscode(path: Path) -> None:
    try:
        subprocess.run(["code", str(path)], check=False)
    except FileNotFoundError:
        print("La commande `code` n'est pas disponible dans le PATH.", file=sys.stderr)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genere des fichiers Markdown GTOLI et un script Bash depuis un tableau synoptique CSV."
    )
    parser.add_argument("--tableau", required=True, type=Path, help="CSV du tableau synoptique.")
    parser.add_argument(
        "--referentiel",
        action="append",
        type=Path,
        default=[],
        help="Fichier referentiel Markdown/TXT/PDF. Peut etre repete.",
    )
    parser.add_argument("--dest", type=Path, default=Path("generated_gtoli"), help="Dossier de sortie Markdown.")
    parser.add_argument(
        "--bash-script",
        type=Path,
        default=Path("creer_fichiers_gtoli.sh"),
        help="Chemin du script Bash genere.",
    )
    parser.add_argument("--template", type=Path, help="Template Markdown optionnel avec variables $niveau, $competence...")
    parser.add_argument("--referentiel-max-chars", type=int, default=3000, help="Taille max de l'extrait referentiel.")
    parser.add_argument(
        "--context-filter",
        action="append",
        default=[],
        help="Terme utilise pour filtrer l'extrait du referentiel PDF/TXT. Peut etre repete.",
    )
    parser.add_argument(
        "--root-prefix",
        default="primaire",
        help="Prefixe de chemin utilise quand la colonne `sortie` est vide.",
    )
    parser.add_argument(
        "--matiere-default",
        default="MST",
        help="Matiere utilisee quand la colonne `matiere` est vide.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Affiche le manifest sans ecrire les fichiers.")
    parser.add_argument("--open-vscode", action="store_true", help="Ouvre le dossier de sortie avec `code` si disponible.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    rows = read_csv_rows(args.tableau)
    context = load_referentiel_context(args.referentiel, args.referentiel_max_chars, args.context_filter)
    template_text = args.template.read_text(encoding="utf-8") if args.template else DEFAULT_TEMPLATE
    template = Template(template_text)

    generated_files: list[tuple[Path, str]] = []
    manifest_entries: list[dict[str, str]] = []

    for index, raw_row in enumerate(rows, start=2):
        row, extras = canonicalize_row(raw_row)
        rel_path = ensure_relative(build_relative_path(row, args.root_prefix, args.matiere_default))
        content = render_markdown(row, extras, template, context, index, args.tableau)
        generated_files.append((rel_path, content))
        manifest_entries.append(
            {
                "source_line": str(index),
                "path": str(rel_path),
                "niveau": row["niveau"],
                "matiere": row["matiere"],
                "champ": row["champ"],
                "bloc": row["bloc"],
                "categorie": row["categorie"],
                "contenu_referentiel": row["contenu_referentiel"],
                "attendu_referentiel": row["attendu_referentiel"],
                "source_page": row["source_page"],
                "competence": preferred_title_source(row),
                "document_type": preferred_document_type(row),
            }
        )

    manifest = {
        "app": "GTOLI Code Factory",
        "version": APP_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "tableau": str(args.tableau),
        "referentiels": [str(path) for path in args.referentiel],
        "context_filters": args.context_filter,
        "destination": str(args.dest),
        "bash_script": str(args.bash_script),
        "files": manifest_entries,
    }

    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    args.dest.mkdir(parents=True, exist_ok=True)
    for rel_path, content in generated_files:
        output_path = args.dest / rel_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    write_bash_script(args.bash_script, generated_files)
    (args.dest / "manifest_gtoli.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(generated_files)} fichier(s) Markdown generes dans {args.dest}")
    print(f"Script Bash genere: {args.bash_script}")
    if args.open_vscode:
        open_in_vscode(args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
