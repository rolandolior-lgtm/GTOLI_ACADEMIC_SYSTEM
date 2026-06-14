# PACK COMPLET - GTOLI Code Factory

Tous les fichiers utiles sont repris ci-dessous, l'un a la suite de l'autre.

Pour utiliser le pack comme vrais fichiers, prends les fichiers separes dans le dossier `files/`.


---

## README.md

```markdown
# GTOLI Code Factory

Petit générateur local pour accélérer la création de fichiers `.md` et de scripts Bash à partir d'un tableau synoptique, avec prise en charge des référentiels PDF.

## Ce que ça fait

- Lit un tableau synoptique au format CSV.
- Injecte un extrait de référentiel `.md`, `.txt` ou `.pdf` dans chaque fiche.
- Reconnaît les champs du référentiel de math primaire: `champ`, `bloc`, `categorie`, `contenu_referentiel`, `attendu_referentiel`, `source_page`.
- Génère les fichiers Markdown directement dans une arborescence compatible avec VS Code.
- Génère aussi un script Bash équivalent, pratique si tu veux recréer la structure dans un autre dépôt.
- Produit un `manifest_gtoli.json` pour garder la trace des fichiers créés.

## Utilisation rapide dans VS Code

Ouvre ce dossier dans VS Code, puis lance dans le terminal:

```bash
python3 gtoli_codegen.py \
  --tableau exemple_tableau_synoptique.csv \
  --referentiel exemple_referentiel_mst_p1.md \
  --dest sortie_gtoli \
  --bash-script creer_fichiers_gtoli.sh
```

Les fichiers seront créés dans `sortie_gtoli`.

## Utilisation avec le vrai référentiel PDF

Exemple avec les deux PDF fournis:

```bash
python3 gtoli_codegen.py \
  --tableau exemple_tableau_officiel_math_p1.csv \
  --referentiel /Users/olivierroland/Downloads/GTO_ACADEMIC_PRIMAIRE/referentiel_math_primaire.pdf.pdf \
  --context-filter P1 \
  --context-filter "CHAMP 3" \
  --dest sortie_math_p1 \
  --bash-script creer_math_p1.sh
```

`--context-filter` sert à éviter d'injecter tout le PDF dans chaque fiche. Tu peux filtrer par niveau (`P1`, `P2`...) et par champ ou mot-clé.

Si ton Python local indique que `pypdf` est absent:

```bash
python3 -m pip install pypdf
```

## Créer un CSV de départ depuis le PDF

Le PDF du référentiel est très riche, mais ses tableaux ne sont pas un CSV propre. L'utilitaire suivant fabrique une première base niveau/champ/bloc que tu peux corriger ou compléter dans VS Code:

```bash
python3 gtoli_pdf_seed.py \
  --pdf /Users/olivierroland/Downloads/GTO_ACADEMIC_PRIMAIRE/referentiel_math_primaire.pdf.pdf \
  --level P1 \
  --out seed_math_p1.csv
```

Puis:

```bash
python3 gtoli_codegen.py \
  --tableau seed_math_p1.csv \
  --referentiel /Users/olivierroland/Downloads/GTO_ACADEMIC_PRIMAIRE/referentiel_math_primaire.pdf.pdf \
  --context-filter P1 \
  --dest sortie_seed_math_p1 \
  --bash-script creer_seed_math_p1.sh
```

Pour ouvrir ensuite le dossier généré dans VS Code:

```bash
code sortie_gtoli
```

Si la commande `code` n'est pas installée, ouvre VS Code puis fais `File > Open Folder`.

## Générer seulement le script Bash

La commande principale crée toujours le script Bash:

```bash
./creer_fichiers_gtoli.sh autre_dossier
```

Cela recrée les mêmes fichiers Markdown dans `autre_dossier`.

## Colonnes reconnues dans le CSV

Le générateur reconnaît ces colonnes, avec quelques variantes:

- `niveau`
- `matiere`
- `champ`
- `bloc`
- `categorie`
- `contenu_referentiel`
- `attendu_referentiel`
- `source_page`
- `competence`
- `type_document`
- `objectif`
- `prerequis`
- `activites`
- `evaluation`
- `mots_cles`
- `sortie`

La colonne la plus importante pour contrôler l'insertion dans ton projet est `sortie`: elle donne le chemin exact du fichier Markdown à créer.

## Adapter à ton vrai projet

1. Remplace `exemple_tableau_synoptique.csv` par ton tableau synoptique exporté en CSV.
2. Remplace `exemple_referentiel_mst_p1.md` par ton référentiel, ou donne directement le PDF.
3. Lance la commande avec `--dest` pointant vers le dossier de ton dépôt.
4. Vérifie les fichiers dans VS Code.
5. Commit les changements dans GitHub.

## Vérification avant écriture

Pour voir ce qui serait généré sans créer les fichiers:

```bash
python3 gtoli_codegen.py \
  --tableau exemple_tableau_synoptique.csv \
  --referentiel exemple_referentiel_mst_p1.md \
  --dry-run
```

## Note

Ce prototype ne remplace pas encore une lecture humaine du tableau synoptique PDF: il structure, extrait, prépare les fichiers et limite les copier-coller. La prochaine étape serait d'ajouter des templates spécialisés par type de document: compétence, banque de questions, évaluation, remédiation et pipeline pédagogique.
```


---

## gtoli_codegen.py

```python
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
```


---

## gtoli_pdf_seed.py

```python
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
```


---

## exemple_tableau_synoptique.csv

```csv
niveau;matiere;champ;competence;type_document;objectif;prerequis;activites;evaluation;mots_cles;sortie
P1;MST;champ_3_arithmetique_algebre;Lire et écrire les nombres jusqu'à 20;competence;Structurer une fiche compétence exploitable en classe et en suivi IA.;Reconnaître les chiffres de 0 à 9.;Lecture orale, manipulation de collections, dictée de nombres.;L'élève lit, écrit et associe quantité et symbole.;nombres, lecture, écriture;primaire/MST/P1/champ_3_arithmetique_algebre/competence_lecture_nombres_P1_GTOLI.md
P1;MST;champ_3_arithmetique_algebre;Additionner deux petites quantités;banque_questions;Créer une base de questions pour entraînement rapide et différenciation.;Dénombrer une collection simple.;Questions flash, cartes à points, problèmes courts.;Réponse correcte, stratégie verbalisée, temps raisonnable.;addition, calcul mental, P1;primaire/MST/P1/banques_questions/banque_questions_additions_simples_P1_GTOLI.md
P1;MST;champ_1_espace_geometrie;Reconnaître les formes géométriques simples;evaluation;Préparer une évaluation diagnostique courte.;Identifier cercle, carré, triangle dans l'environnement.;Tri d'images, coloriage ciblé, justification orale.;Identification correcte et vocabulaire géométrique minimal.;formes, géométrie, diagnostic;primaire/MST/P1/evaluations/evaluation_formes_geometriques_P1_GTOLI.md
```


---

## exemple_tableau_officiel_math_p1.csv

```csv
niveau;matiere;champ;bloc;categorie;type_document;competence;contenu_referentiel;attendu_referentiel;objectif;prerequis;activites;evaluation;mots_cles;source_page;sortie
P1;MST;CHAMP 1 : DES OBJETS DE L’ESPACE À LA GÉOMÉTRIE;1.1. (Se) repérer et communiquer des positionnements ou des déplacements;Savoir-faire;fiche_competence;Situer, placer un objet ou soi-même;Situer, placer un objet ou soi-même.;Situer un objet ou soi-même avec le vocabulaire adéquat dans l’espace 3D.;Créer une fiche compétence alignée sur le référentiel.;Vocabulaire spatial de base.;Manipulations en espace vécu, miniaturisé et verbalisation.;Observation de consignes suivies et verbalisation précise.;P1, espace, positionnement;26;primaire/MST/P1/champ_1_espace_geometrie/bloc_1_1_reperage/fiche_situer_placer_objet_P1_GTOLI.md
P1;MST;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES;2.1. Concevoir des grandeurs;Compétence;fiche_competence;Choisir une démarche de comparaison de longueurs;Choisir, en situations significatives, des démarches pertinentes de comparaisons de grandeurs d’objets.;Choisir une action concrète pertinente pour comparer des longueurs, verbaliser son action et expliquer son choix.;Créer une fiche activité + évaluation courte.;Comparer deux objets selon une grandeur.;Juxtaposer, regarder, aligner, verbaliser le choix.;L’élève choisit une action pertinente et explique son choix.;P1, grandeurs, longueurs;28;primaire/MST/P1/champ_2_grandeurs_relations/bloc_2_1_grandeurs/fiche_comparer_longueurs_P1_GTOLI.md
P1;MST;CHAMP 3 : DE L’ARITHMÉTIQUE À L’ALGÈBRE;3.1. Appréhender le nombre puis la lettre dans tous leurs aspects;Savoir-faire;fiche_competence;Dire, lire, écrire et représenter les nombres;Dire, lire, écrire et représenter les nombres dans la numération décimale.;Dire, lire les nombres jusqu’à 20 et les écrire en chiffres.;Produire une fiche compétence et une base d’exercices rapides.;Connaître la comptine numérique orale.;Lecture orale, dictée de nombres, représentation en dizaines et unités.;Lecture, écriture et représentation correcte des nombres jusqu’à 20.;P1, nombres, numération;32;primaire/MST/P1/champ_3_arithmetique_algebre/bloc_3_1_nombres/fiche_lire_ecrire_nombres_P1_GTOLI.md
```


---

## seed_math_p1.csv

```csv
niveau;matiere;champ;bloc;categorie;type_document;competence;contenu_referentiel;attendu_referentiel;objectif;prerequis;activites;evaluation;mots_cles;source_page;sortie
P1;MST;CHAMP 1 : DES OBJETS DE L’ESPACE À LA GÉOMÉTRIE;1.1. (Se) repérer et communiquer des positionnements ou des déplacements;bloc;fiche_referentiel;(Se) repérer et communiquer des positionnements ou des déplacements;CHAMP 1 : DES OBJETS DE L’ESPACE À LA GÉOMÉTRIE / 1.1. (Se) repérer et communiquer des positionnements ou des déplacements;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 1.1;25;primaire/MST/P1/champ_1_espace_geometrie/1_1_se_reperer_et_communiquer_des_positionnements_ou_des_deplacements/fiche_bloc_1_1_se_reperer_et_communiquer_des_positionnements_ou_des_deplacements_P1_GTOLI.md
P1;MST;CHAMP 1 : DES OBJETS DE L’ESPACE À LA GÉOMÉTRIE;1.2. Appréhender et représenter des objets de l’espace;bloc;fiche_referentiel;Appréhender et représenter des objets de l’espace;CHAMP 1 : DES OBJETS DE L’ESPACE À LA GÉOMÉTRIE / 1.2. Appréhender et représenter des objets de l’espace;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 1.2;27;primaire/MST/P1/champ_1_espace_geometrie/1_2_apprehender_et_representer_des_objets_de_lespace/fiche_bloc_1_2_apprehender_et_representer_des_objets_de_lespace_P1_GTOLI.md
P1;MST;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES;2.1. Concevoir des grandeurs;bloc;fiche_referentiel;Concevoir des grandeurs;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES / 2.1. Concevoir des grandeurs;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 2.1;28;primaire/MST/P1/champ_2_grandeurs_relations/2_1_concevoir_des_grandeurs/fiche_bloc_2_1_concevoir_des_grandeurs_P1_GTOLI.md
P1;MST;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES;2.2. Agir sur des grandeurs;bloc;fiche_referentiel;Agir sur des grandeurs;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES / 2.2. Agir sur des grandeurs;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 2.2;29;primaire/MST/P1/champ_2_grandeurs_relations/2_2_agir_sur_des_grandeurs/fiche_bloc_2_2_agir_sur_des_grandeurs_P1_GTOLI.md
P1;MST;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES;2.3. Opérer sur des grandeurs – périmètres, aires et volumes;bloc;fiche_referentiel;Opérer sur des grandeurs – périmètres, aires et volumes;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES / 2.3. Opérer sur des grandeurs – périmètres, aires et volumes;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 2.3;29;primaire/MST/P1/champ_2_grandeurs_relations/2_3_operer_sur_des_grandeurs_perimetres_aires_et_volumes/fiche_bloc_2_3_operer_sur_des_grandeurs_perimetres_aires_et_volumes_P1_GTOLI.md
P1;MST;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES;2.4. Agir puis opérer sur des grandeurs – fractions;bloc;fiche_referentiel;Agir puis opérer sur des grandeurs – fractions;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES / 2.4. Agir puis opérer sur des grandeurs – fractions;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 2.4;30;primaire/MST/P1/champ_2_grandeurs_relations/2_4_agir_puis_operer_sur_des_grandeurs_fractions/fiche_bloc_2_4_agir_puis_operer_sur_des_grandeurs_fractions_P1_GTOLI.md
P1;MST;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES;2.5. Mettre en relation des grandeurs;bloc;fiche_referentiel;Mettre en relation des grandeurs;CHAMP 2 : DES GRANDEURS À LA RELATION ENTRE VARIABLES / 2.5. Mettre en relation des grandeurs;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 2.5;30;primaire/MST/P1/champ_2_grandeurs_relations/2_5_mettre_en_relation_des_grandeurs/fiche_bloc_2_5_mettre_en_relation_des_grandeurs_P1_GTOLI.md
P1;MST;CHAMP 3 : DE L’ARITHMÉTIQUE À L’ALGÈBRE;3.1. Appréhender le nombre puis la lettre dans tous leurs aspects;bloc;fiche_referentiel;Appréhender le nombre puis la lettre dans tous leurs aspects;CHAMP 3 : DE L’ARITHMÉTIQUE À L’ALGÈBRE / 3.1. Appréhender le nombre puis la lettre dans tous leurs aspects;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 3.1;31;primaire/MST/P1/champ_3_arithmetique_algebre/3_1_apprehender_le_nombre_puis_la_lettre_dans_tous_leurs_aspects/fiche_bloc_3_1_apprehender_le_nombre_puis_la_lettre_dans_tous_leurs_aspects_P1_GTOLI.md
P1;MST;CHAMP 3 : DE L’ARITHMÉTIQUE À L’ALGÈBRE;3.2. Opérer sur des nombres et sur des expressions algébriques;bloc;fiche_referentiel;Opérer sur des nombres et sur des expressions algébriques;CHAMP 3 : DE L’ARITHMÉTIQUE À L’ALGÈBRE / 3.2. Opérer sur des nombres et sur des expressions algébriques;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 3.2;33;primaire/MST/P1/champ_3_arithmetique_algebre/3_2_operer_sur_des_nombres_et_sur_des_expressions_algebriques/fiche_bloc_3_2_operer_sur_des_nombres_et_sur_des_expressions_algebriques_P1_GTOLI.md
P1;MST;CHAMP 4 : DE L’ORGANISATION DES DONNÉES À LA STATISTIQUE;4.1. Collecter, organiser, représenter et interpréter des données;bloc;fiche_referentiel;Collecter, organiser, représenter et interpréter des données;CHAMP 4 : DE L’ORGANISATION DES DONNÉES À LA STATISTIQUE / 4.1. Collecter, organiser, représenter et interpréter des données;;Transformer ce bloc du referentiel en fiches, activites et evaluations.;;;;P1, mathematiques, 4.1;34;primaire/MST/P1/champ_4_donnees_statistique/4_1_collecter_organiser_representer_et_interpreter_des_donnees/fiche_bloc_4_1_collecter_organiser_representer_et_interpreter_des_donnees_P1_GTOLI.md
```


---

## exemple_referentiel_mst_p1.md

```markdown
# Référentiel MST P1 - extrait de travail

## Domaines

- Espace et géométrie: repérage, positions, formes simples.
- Grandeurs: comparaison, longueur, temps vécu.
- Arithmétique et algèbre: dénombrement, lecture/écriture des nombres, additions et soustractions simples.
- Données: tri, classement, lecture de tableaux simples.

## Principes GTOLI

- Chaque compétence doit pouvoir être reliée à un objectif observable.
- Chaque fiche doit prévoir des prérequis, des activités, des erreurs typiques et une modalité d'évaluation.
- Les contenus doivent être structurés pour pouvoir alimenter plus tard une base IA ou un pipeline pédagogique.

## Format conseillé

1. Intention pédagogique.
2. Compétence cible.
3. Prérequis.
4. Activités proposées.
5. Évaluation.
6. Mots-clés et traces de suivi.
```


---

## .gitignore

```gitignore
__pycache__/
*.pyc
sortie_bash/
```
