# VEX

Ce dossier est reserve aux declarations VEX revues par l'equipe.

Le workflow SBOM cherche automatiquement un document OpenVEX a cet emplacement:

```text
security/vex.openvex.json
```

Si ce fichier existe, Grype l'utilise pendant le scan de vulnerabilites pour
filtrer ou enrichir les resultats. S'il n'existe pas, le scan continue sans VEX.

Le script `scripts/generate-sbom.ps1 -AnalyzeVulnerabilities` genere aussi un
brouillon OpenVEX dans `sbom/station-de-recharge.openvex.json` quand Grype trouve
des vulnerabilites. Ce brouillon marque les constats comme `under_investigation`;
il doit etre relu avant de devenir une declaration VEX officielle.

Pour une image Docker, le brouillon identifie le produit avec un PURL OCI base
sur l'image id `sha256`, afin de rattacher la declaration a l'image analysee et
pas seulement a un tag mutable.

Rappels pour une declaration VEX:

- `not_affected` exige une `justification` ou un `impact_statement`.
- `affected` exige un `action_statement`.
- `fixed` signale que la version analysee contient deja le correctif.
- `under_investigation` documente une analyse en cours et ne supprime pas le
  finding dans Grype.
