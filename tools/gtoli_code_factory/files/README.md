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
