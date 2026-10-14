# Veille gratuite – projets environnementaux de l'Hérault

**Statut : kit à tester, non activé.** Source surveillée : jeu de données `projets-environnement-diffusion` de projets-environnement.gouv.fr. **Ce n'est pas** un relevé exhaustif du portail `evaluation-environnementale.ecologie.gouv.fr`.

## Installation sur GitHub
1. Créer un dépôt **public** GitHub et y déposer `monitor.py`, `.github/workflows/veille.yml` (préserver le chemin) et ce README.
2. Dans **Actions**, lancer manuellement « Veille Hérault » via **Run workflow**. Vérifier que l'exécution est verte et que `state.json` et `docs/herault.xml` sont produits. Si échec, consulter les logs (schéma API, erreurs réseau ou pagination).
3. Dans **Settings → Pages**, choisir **Deploy from a branch**, branche `main`, dossier `/docs` et sauvegarder. Le flux sera `https://IDENTIFIANT.github.io/NOM-DEPOT/herault.xml`.
4. S'abonner à cette adresse avec un lecteur RSS. Les prochains dossiers détectés seront ajoutés au flux. Attention : la première exécution initialise l'historique sans alerte par e-mail.
5. Pour les e-mails (facultatif), ajouter les secrets du dépôt **Settings → Secrets and variables → Actions** : `SMTP_HOST`, `SMTP_PORT` (par défaut 465), `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_TO`. Il faut un service SMTP autorisant cet usage ; ne pas insérer de mots de passe en clair dans les fichiers.

## Fonctionnement et limites
- Exécution programmée à 10 h heure de Paris par GitHub Actions, avec sélection été/hiver. GitHub peut retarder ou omettre une exécution cron : **ce n'est pas une garantie de passage à la minute**.
- Une fiche est considérée comme nouvelle si son identifiant est inédit par rapport à l'historique. Les modifications de dossiers existants ne déclenchent actuellement pas d'alerte.
- Filtrage strict des champs de département mentionnant `34` ou `Hérault`. Un projet mal renseigné peut être manqué.
- Une erreur API ou une liste vide provoque l'échec de l'exécution, et non un faux « aucune nouveauté ».
- La base source peut être incomplète ou publiée avec retard ; pour une veille journalistique exhaustive, compléter avec la DREAL et le portail des avis.
- Le code doit être testé sur une exécution réelle car l'API de production n'était pas accessible dans l'environnement de préparation.
- GitHub Actions et Pages sont gratuits dans les limites de leur offre. Un dépôt public et un flux Pages rendent les titres diffusés publics, jamais les secrets SMTP.
