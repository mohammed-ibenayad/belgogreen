# Guide Utilisateur - Module Simulation Photovoltaïque

## Vue d'ensemble

Ce module vous permet de générer une simulation photovoltaïque complète à partir d'un devis client, puis de produire un rapport PDF professionnel à remettre au client. La simulation calcule la production estimée, la consommation, le bilan énergétique et le bilan financier sur une base annuelle.

---

## 1. Prérequis avant de créer une simulation

Avant de lancer une simulation, vérifiez que le devis contient bien :

- **Au moins un panneau solaire**
  - Produit dans la catégorie `All / Saleable / Panneaux`
  - Champ **Puissance unitaire (Wc)** renseigné sur la fiche produit
- **Au moins une batterie**
  - Produit dans la catégorie `All / Saleable / Batteries`
  - Champ **Capacité batterie (kWh)** renseigné sur la fiche produit
  - Le **Rendement batterie (%)** est par défaut à 100 %, ajustable sur la fiche produit
- **Une adresse client complète** (rue, code postal, ville, pays)
  - Sert à récupérer automatiquement les coordonnées GPS via Google

Si l'une de ces informations manque, l'assistant de création affichera un avertissement et la génération sera bloquée.

---

## 2. Créer une nouvelle simulation

### Étape 1 — Ouvrir l'assistant depuis le devis

1. Ouvrez le devis concerné
2. Cliquez sur le bouton **Simulations PV** en haut à droite (icône panneau solaire)
3. Si aucune simulation n'existe pour ce devis, l'assistant de création s'ouvre automatiquement

### Étape 2 — Remplir l'assistant

L'assistant vous demande les informations suivantes :

- **Coordonnées GPS**
  - Cliquez sur **Récupérer les coordonnées GPS** pour les récupérer automatiquement à partir de l'adresse client
  - Vous pouvez ensuite vérifier l'emplacement avec le bouton **Google Maps**
  - Les coordonnées peuvent être corrigées manuellement si nécessaire
- **Inclinaison (°)** : angle des panneaux (par défaut 35°)
- **Orientation (°)** : 0 = Sud, +45 = Sud-Ouest, −45 = Sud-Est, etc. (un guide est affiché dans l'assistant)
- **Consommation annuelle (kWh)** : consommation totale annuelle du client
- **Ratio jour / nuit (%)** : part de la consommation journalière (par défaut 60 % jour / 40 % nuit)

### Étape 3 — Générer

Cliquez sur **Créer et Générer**. Un écran de chargement s'affiche pendant que le système :

1. Récupère les données solaires via Google Solar API
2. Calcule la production mensuelle via PVGIS (pertes système de 14 %)
3. Répartit la consommation annuelle sur les 12 mois
4. Calcule le bilan énergétique et financier mensuel
5. Génère les graphiques

La simulation est nommée automatiquement au format `SIM-<référence devis>-v01` (par exemple `SIM-S00010-v01`).

---

## 3. Naviguer dans la simulation

La simulation est organisée en onglets. Chaque onglet correspond à une page du rapport PDF final et permet de modifier son titre.

### Onglet « Système PV »

Affiche les caractéristiques techniques de l'installation (puissance totale, nombre de panneaux, capacité batterie, orientation, inclinaison). Les valeurs sont calculées automatiquement à partir du devis.

### Onglet « Couverture (Page 1) »

- Photo de couverture du rapport
- Titres principaux
- Nom de société affiché dans le pied de page

### Onglet « Bilan Énergétique (Page 2) »

Vue d'ensemble annuelle :
- **Production totale** (kWh)
- **Consommation** jour / nuit / totale
- **Autoconsommation** : énergie produite et utilisée directement
- **Économies** : panneaux, batterie, revente
- **Coût d'achat réseau**

Toutes ces valeurs sont calculées automatiquement à partir des résultats mensuels.

### Onglet « Bilan Annuel (Page 3) »

Contient deux graphiques de synthèse annuels :
- **Production vs Consommation** : comparaison mois par mois
- **Répartition énergétique** : graphique en anneau montrant Production / Autoconso / Vente / Achat / Consommation en kWh

### Onglet « Localisation (Page 4) »

- Adresse d'installation (pré-remplie depuis la fiche client)
- Coordonnées GPS (modifiables)
- Surface de toiture en m²
- Image satellite de l'emplacement

### Onglet « Production (Page 5) »

- Image du système (photo des panneaux ou schéma)
- Profil de production (répartition mensuelle en %)
- Aperçu du graphique de production mensuelle

### Onglet « Consommation (Page 6) »

C'est ici que vous pouvez **ajuster la consommation** mois par mois :

- **Consommation mensuelle par défaut** : saisissez une valeur puis cliquez sur **Appliquer la consommation par défaut** pour la répliquer sur tous les mois
- **Ratio jour / nuit** : ajustez puis cliquez sur **Appliquer le ratio jour/nuit** pour recalculer les consommations jour/nuit de chaque mois
- **Tableau mensuel** : les champs en bleu clair (`Conso.`, `Conso jour`, `Conso nuit`) sont modifiables manuellement si le client a des valeurs précises (facture, historique)

### Onglet « Bilan Financier (Page 7) »

- Sélection du **profil tarifaire** (pré-rempli avec le premier profil disponible à la création de la simulation)
- **Prix d'achat** (€/kWh), **Tarif de revente** (€/kWh), **Coût batterie** (€/kWh) — modifiables par simulation
- Tableau mensuel : économies panneaux, économies batterie, vente, achat et bilan net

**Astuce** : les prix sont copiés sur la simulation au moment de la sélection du profil. Vous pouvez les ajuster sans modifier le profil partagé.

---

## 4. Champs modifiables et champs calculés

Dans la simulation, repérez facilement ce que vous pouvez modifier :

- **Champs en bleu clair** : modifiables par l'utilisateur (consommation, prix, titres de sections, photos…)
- **Champs en gris / désactivés** : calculés automatiquement (production, bilan, graphiques…)

---

## 5. Régénérer la simulation

Si vous modifiez des données qui impactent la simulation (coordonnées GPS, orientation, inclinaison, production annuelle, profil tarifaire…), un bandeau d'avertissement apparaît en haut de la simulation vous invitant à régénérer.

Cliquez sur le bouton **Régénérer la simulation** en haut du formulaire pour :

1. Récupérer les données solaires à jour
2. Recalculer les résultats mensuels
3. Recomposer le bilan énergétique et financier
4. Régénérer les graphiques

À chaque régénération, le numéro de version s'incrémente :
- Création → `SIM-S00010-v01`
- 1ʳᵉ régénération → `SIM-S00010-v02`
- 2ᵉ régénération → `SIM-S00010-v03`

Cela vous permet de garder une trace des itérations faites avec le client.

---

## 6. Générer le rapport PDF

Une fois la simulation prête :

1. Cliquez sur **Rapport PDF** en haut du formulaire
2. Le document est généré et téléchargé automatiquement
3. Le fichier est nommé `Rapport_PV_<référence simulation>.pdf`

### Structure du rapport

| Page | Contenu |
|---|---|
| 1 | Couverture (photo, titres, référence devis, date) |
| 2 | Bilan Énergétique (production, consommation, autoconso, économies) |
| 3 | Bilan Annuel (graphiques Production vs Consommation + Répartition) |
| 4 | Localisation (adresse, GPS, image satellite, surface toiture) |
| 5 | Production (graphique mensuel + caractéristiques système) |
| 6 | Données de consommation (tableaux mensuels et quotidiens) |
| 7 | Bilan financier mensuel |

---

## 7. Créer plusieurs simulations pour un même devis

Si le client souhaite comparer plusieurs scénarios (plus/moins de panneaux, batterie différente, orientation alternative…) :

1. Depuis le devis, cliquez sur **Simulations PV**
2. Dans la liste qui s'affiche, cliquez sur **Nouvelle simulation**
3. Remplissez l'assistant avec les paramètres du nouveau scénario

Chaque simulation garde sa propre numérotation et son propre historique de régénérations.

---

## 8. Questions fréquentes

**Q : L'assistant affiche "Aucune batterie trouvée" alors que j'ai bien une batterie sur le devis.**
R : Vérifiez que le produit batterie appartient à la catégorie `All / Saleable / Batteries` et que le champ **Battery Capacity (kWh)** est renseigné sur la fiche produit.

**Q : La production annuelle affichée ne correspond pas à ce que le client attendait.**
R : La production est calculée par PVGIS en fonction des coordonnées GPS, de l'orientation, de l'inclinaison et de la puissance installée. Vérifiez ces quatre paramètres avant de régénérer. Vous pouvez aussi corriger manuellement la valeur **Production annuelle (PVGIS)** dans l'onglet Système PV.

**Q : Le client m'a donné une consommation annuelle totale ; je ne veux pas saisir 12 valeurs mensuelles.**
R : Saisissez la consommation annuelle dans l'assistant de création, ou utilisez le champ **Consommation mensuelle par défaut** dans l'onglet Consommation puis cliquez sur **Appliquer la consommation par défaut**. Les 12 mois seront remplis automatiquement et le total sera exact.

**Q : Je régénère la simulation et mes valeurs de consommation mensuelles saisies manuellement sont conservées ?**
R : Oui. Les valeurs mensuelles saisies à la main sont préservées à chaque régénération ; seules les valeurs calculées (production, bilan, graphiques) sont recalculées.

**Q : Puis-je modifier les titres qui apparaissent dans le rapport ?**
R : Oui. Chaque onglet correspondant à une page du rapport contient un champ **Titre de section** (et parfois des sous-titres) que vous pouvez personnaliser par simulation.

**Q : Comment changer la photo de couverture ou l'image du système pour une simulation ?**
R : Dans les onglets **Couverture (Page 1)** et **Production (Page 5)** respectivement. Si vous laissez le champ vide, l'image par défaut (Configuration → Report Defaults) est utilisée.

**Q : Que signifie la version `v02`, `v03` dans le nom de la simulation ?**
R : C'est le numéro de génération. Il s'incrémente à chaque fois que vous cliquez sur **Régénérer la simulation**, ce qui permet de suivre combien d'itérations ont été faites.

---

## Conseils pratiques

✓ **Vérifiez toujours le devis** (panneaux + batterie + adresse client) avant de lancer la création
✓ **Récupérez les coordonnées GPS** automatiquement plutôt que de les saisir à la main
✓ **Sélectionnez un profil tarifaire** à jour avant de générer le rapport final
✓ **Ajustez les consommations mensuelles** si le client dispose de ses factures
✓ **Régénérez la simulation** après toute modification importante avant de générer le PDF
✓ **Utilisez l'aperçu des graphiques** dans les onglets pour vérifier visuellement le résultat avant d'envoyer le rapport
✓ **Personnalisez les titres de sections** pour adapter le rapport au contexte commercial

---

**Support** : Pour toute question ou problème technique, contactez votre responsable ou l'équipe IT.
