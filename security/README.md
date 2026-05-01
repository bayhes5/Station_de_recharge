# VEX

Ce dossier est réservé aux déclarations VEX revues par l'équipe.

Le workflow SBOM cherche automatiquement un document OpenVEX à cet emplacement:

```text
security/vex.openvex.json
```

Si ce fichier existe, Grype l'utilise pendant le scan de vulnérabilités pour
filtrer ou enrichir les résultats. S'il n'existe pas, le scan continue sans VEX.

Le script `scripts/generate-sbom.ps1 -AnalyzeVulnerabilities` génère aussi un
brouillon OpenVEX dans `sbom/station-de-recharge.openvex.json` quand Grype trouve
des vulnérabilités. Ce brouillon marque les constats comme `under_investigation`;
il doit être relu avant de devenir une déclaration VEX officielle.

Après une évolution liée à la sécurité applicative, comme la gestion
administrateur des badges RFID, la révocation des QR codes ou codes temporaires,
ou la journalisation d'actions sensibles, il faut régénérer les SBOM et rapports
de vulnérabilités afin que les artefacts de release décrivent le nouvel état du
produit.

Pour une image Docker, le brouillon identifie le produit avec un PURL OCI basé
sur l'image id `sha256`, afin de rattacher la déclaration à l'image analysée et
pas seulement à un tag mutable.

Rappels pour une déclaration VEX:

- `not_affected` exige une `justification` ou un `impact_statement`.
- `affected` exige un `action_statement`.
- `fixed` signale que la version analysée contient déjà le correctif.
- `under_investigation` documente une analyse en cours et ne supprime pas le
  finding dans Grype.
