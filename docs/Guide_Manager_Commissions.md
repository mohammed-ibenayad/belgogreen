# Guide Manager - Module Commissions

## Vue d'ensemble

En tant que **Manager de Commissions**, vous avez accès à toutes les fonctionnalités utilisateur ainsi qu'à des outils de gestion avancés pour :
- Approuver ou rejeter les réclamations de commissions
- Créer des commissions manuelles
- Gérer les déductions obligatoires et optionnelles
- Configurer les plans de commissions et les hiérarchies
- Administrer les rôles et pourcentages

---

## 1. Gestion des réclamations

### Consulter les réclamations en attente

**Menu : Commissions → Gestion → Suivi → Réclamations**

Vous verrez toutes les réclamations de votre équipe avec :
- **Référence** : Numéro de la réclamation
- **Utilisateur** : Nom du commercial
- **Date de réclamation**
- **Total commissions** : Montant brut des commissions réclamées
- **Total déductions** : Déductions appliquées
- **Montant net** : Montant final à payer
- **État** : Brouillon, En attente, Approuvée, Rejetée

**Filtres utiles** :
- Par état : "En attente" pour voir les réclamations à traiter
- Par utilisateur : Pour voir toutes les réclamations d'un commercial spécifique
- Par date : Période de réclamation

### Approuver une réclamation

1. **Ouvrez la réclamation** en cliquant sur la ligne
2. **Vérifiez les détails** :
   - Liste des commissions incluses
   - Déductions obligatoires (automatiquement appliquées)
   - Déductions optionnelles (sélectionnées par l'utilisateur)
   - Montant net calculé
3. **Cliquez sur "Approuver"**
   - Un **bon de commande (Purchase Order)** est automatiquement créé
   - Le bon contient :
     - Une ligne pour le montant total des commissions (positif)
     - Des lignes pour chaque déduction (négatif)
   - Les commissions passent à l'état **"Approuvée"**
4. **Traitez le bon de commande** selon votre processus d'achat habituel

**Note** : Une fois approuvée, la réclamation ne peut plus être modifiée. Le paiement suit le flux standard des bons de commande.

### Rejeter une réclamation

1. **Ouvrez la réclamation**
2. **Cliquez sur "Rejeter"**
3. **Ajoutez un motif** (optionnel mais recommandé) pour informer l'utilisateur
4. Les commissions retournent à l'état **"Non payée"** et l'utilisateur peut créer une nouvelle réclamation

### Approbation en lot

Pour traiter plusieurs réclamations d'un même utilisateur :
1. **Sélectionnez plusieurs réclamations** (cases à cocher)
2. **Action → Approuver en lot**
3. Un bon de commande sera créé pour chaque réclamation

---

## 2. Paiement direct (sans réclamation)

### Créer un bon de commande directement

En tant que manager, vous pouvez **bypasser le processus de réclamation** et payer directement des commissions :

1. **Accédez aux commissions non payées**
   - Menu : **Commissions → Gestion → Statistiques → Commissions non payées**
2. **Ouvrez une commission** spécifique
3. **Cliquez sur "Créer bon de commande"**
   - Les déductions obligatoires sont automatiquement appliquées
   - La commission passe à l'état **"En cours"**
   - Un bon de commande est créé immédiatement

**Cas d'usage** : Utile pour les paiements urgents ou les situations spéciales où vous ne voulez pas attendre que l'utilisateur fasse une réclamation.

---

## 3. Création de commissions manuelles

### Quand créer une commission manuelle ?

- Commissions exceptionnelles (primes, bonus)
- Corrections d'erreurs de calcul
- Commissions pour activités hors vente standard
- Ajustements de commissions

### Procédure

**Menu : Commissions → Gestion → Suivi → Créer Commission**

1. **Lancez l'assistant "Créer Commission"**
2. **Remplissez les champs** :
   - **Bénéficiaire** : Sélectionnez l'utilisateur qui recevra la commission
   - **Commandes de vente** : Liez une ou plusieurs commandes (optionnel)
   - **Type de commission** :
     - *Vente directe* : Commission sur une vente propre
     - *Commission de supervision* : Commission sur vente d'un subordonné
   - **Montant de base** : Montant sur lequel calculer la commission
   - **Pourcentage** : Taux de commission à appliquer (renseigné automatiquement selon le rôle)
   - **Motif** : Raison de création (obligatoire pour traçabilité)
3. **Option "Créer bon de commande immédiatement"** :
   - ☑ Coché : La commission est créée et un bon de commande est généré directement
   - ☐ Décoché : La commission est créée à l'état "Non payée" et l'utilisateur peut la réclamer plus tard
4. **Confirmez** : La commission est créée avec le statut approprié

**Astuce** : Pour les ajustements exceptionnels, ajoutez un motif détaillé pour faciliter l'audit.

---

## 4. Gestion des déductions

### Accéder aux déductions

**Menu : Commissions → Gestion → Suivi → Déductions**

Vous pouvez créer, modifier et annuler des déductions pour tous les utilisateurs.

### Créer une déduction

1. **Cliquez sur "Créer"**
2. **Remplissez les informations** :
   - **Utilisateur cible** : La personne concernée par la déduction
   - **Type** :
     - **Obligatoire** : Appliquée automatiquement à toutes les futures réclamations
     - **Optionnelle** : L'utilisateur peut choisir de l'ajouter ou non
   - **Catégorie** :
     - Acompte
     - Frais de service
     - Formation
     - Génération de leads
     - Matériaux
     - Autres
   - **Montant** : Valeur de la déduction (en devise)
   - **Motif** : Description claire (ex: "Acompte versé le 15/12/2025")
3. **Enregistrez** : La déduction est à l'état **"En attente"**

### États des déductions

- **En attente** : Déduction créée, pas encore utilisée
- **Appliquée** : Déduction utilisée dans une réclamation approuvée
- **Annulée** : Déduction annulée (non utilisable)
- **Annulée avec motif** : Déduction dispensée (waived) avec justification

### Annuler une déduction (Waive)

Si vous souhaitez annuler une déduction obligatoire pour un utilisateur :
1. **Ouvrez la déduction**
2. **Cliquez sur "Dispenser" (Waive)**
3. **Ajoutez un motif** : Raison de l'annulation (ex: "Performance exceptionnelle")
4. La déduction passe à l'état **"Annulée"** et ne sera plus appliquée

**Important** : Seules les déductions "En attente" peuvent être annulées. Une fois appliquée, une déduction ne peut plus être modifiée.

---

## 5. Configuration des plans de commissions

### Structure hiérarchique

Le module utilise une structure hiérarchique où :
- Un **commercial** fait une vente → gagne une commission directe
- Son **chef d'équipe** → gagne une commission de supervision
- Le **directeur** au-dessus → gagne aussi une commission de supervision

Chaque niveau gagne un pourcentage différent défini dans le plan.

### Créer ou modifier un plan

**Menu : Commissions → Configuration → Plans → Plans de commissions**

1. **Créez un nouveau plan** ou ouvrez un plan existant
2. **Onglet "Informations générales"** :
   - **Nom du plan** : Ex: "Plan Commercial 2026"
   - **Type** : Sélectionnez **"Hiérarchique"**
   - **Facturation payée requise** :
     - ☑ Les commissions sont générées uniquement quand la facture est payée (recommandé)
     - ☐ Les commissions sont générées dès la confirmation de la commande
   - **État** : Brouillon → Approuvé (seuls les plans approuvés sont actifs)

### Onglet "Pourcentages des rôles"

Définissez les pourcentages de commission pour chaque rôle :

| Rôle              | Vente directe (%) | Commission supervision (%) |
|-------------------|-------------------|----------------------------|
| Commercial        | 5%                | 0%                         |
| Chef d'équipe     | 5%                | 2%                         |
| Directeur         | 5%                | 1%                         |

**Explications** :
- **Vente directe %** : Pourcentage gagné quand l'utilisateur fait sa propre vente
- **Commission supervision %** : Pourcentage gagné quand un subordonné fait une vente

**Exemple concret** :
```
Vente de 10 000 € par le commercial "Jean"

Jean (Commercial) :
  - Commission directe : 10 000 € × 5% = 500 €

Chef d'équipe de Jean (Marie) :
  - Commission supervision : 10 000 € × 2% = 200 €

Directeur (Pierre, au-dessus de Marie) :
  - Commission supervision : 10 000 € × 1% = 100 €

Total commissions générées : 800 €
```

### Onglet "Utilisateurs et hiérarchie"

Construisez votre structure d'équipe :

1. **Ajoutez des utilisateurs au plan** :
   - **Utilisateur** : Sélectionnez un collaborateur
   - **Rôle** : Attribuez un rôle (Commercial, Chef d'équipe, Directeur)
   - **Manager** : Sélectionnez le responsable direct (doit avoir un rôle de niveau supérieur)
   - **Dates de début/fin** : Période d'activité dans ce plan (optionnel)

2. **Validations automatiques** :
   - Le manager doit avoir un niveau hiérarchique supérieur
   - Pas d'auto-gestion (un utilisateur ne peut pas être son propre manager)
   - Pas de références circulaires
   - Le manager doit être dans le même plan

3. **Visualisation hiérarchique** :
   - Une vue arborescente montre automatiquement la structure de votre équipe
   - Les pourcentages calculés sont affichés pour chaque utilisateur

**Astuce** : Utilisez les dates de début/fin pour gérer les changements d'organisation (promotions, mutations, saisonnalité).

### Approuver le plan

Une fois configuré :
1. **Vérifiez tous les paramètres**
2. **Cliquez sur "Approuver"**
3. Le plan devient actif et les commissions seront calculées selon ces règles

**Important** : Un plan approuvé peut encore être modifié, mais soyez prudent car cela affecte les futures commissions.

---

## 6. Gestion des rôles

### Accéder aux rôles

**Menu : Commissions → Configuration → Plans → Gestion des rôles**

Les rôles définissent les niveaux hiérarchiques et les capacités de gestion.

### Créer un rôle

1. **Cliquez sur "Créer"**
2. **Remplissez les informations** :
   - **Nom** : Ex: "Chef d'équipe", "Directeur Régional"
   - **Code** : Code unique (ex: "TEAM_LEADER", "DIRECTOR")
   - **Niveau hiérarchique (Séquence)** :
     - Plus le nombre est élevé, plus le niveau est élevé
     - Ex: Commercial = 10, Chef d'équipe = 20, Directeur = 30
   - **Rôle de base** : ☑ Si c'est le rôle par défaut pour les nouveaux utilisateurs
   - **Peut gérer des subordonnés** : ☑ Si ce rôle peut avoir des personnes sous sa supervision
3. **Enregistrez**

### Indicateurs du rôle

Chaque rôle affiche :
- **Nombre d'utilisateurs** : Combien de personnes ont ce rôle
- **Nombre de commissions** : Total des commissions générées pour ce rôle

**Astuce** : Utilisez les séquences par intervalles de 10 (10, 20, 30) pour pouvoir insérer facilement de nouveaux niveaux intermédiaires plus tard.

---

## 7. Statistiques et rapports

### Consulter toutes les commissions

**Menu : Commissions → Gestion → Statistiques → Toutes les commissions**

Vue globale de toutes les commissions de l'entreprise avec :
- Vues liste, kanban, tableau croisé, graphique
- Groupement par période, utilisateur, rôle, type, statut
- Filtres avancés

**Cas d'usage** :
- Analyser les performances par équipe
- Identifier les commissions bloquées
- Générer des rapports de paie

### Commissions non payées

**Menu : Commissions → Gestion → Statistiques → Commissions non payées**

Filtre automatique sur les commissions à l'état "Non payée" :
- Utile pour relancer les utilisateurs à créer leurs réclamations
- Paiement direct possible depuis cette vue

### Tableau de bord global

**Menu : Commissions → Tableau de bord**

En tant que manager, vous voyez :
- KPI de toute l'équipe (pas seulement vos subordonnés directs)
- Tendances sur 6 mois
- Répartition des commissions par statut
- Métriques de gestion d'équipe

---

## 8. Bonnes pratiques

### Gestion des réclamations

✓ **Traitez rapidement** les réclamations en attente pour maintenir la satisfaction de l'équipe
✓ **Vérifiez systématiquement** les déductions avant d'approuver
✓ **Communiquez clairement** les raisons en cas de rejet
✓ **Approuvez en lot** quand possible pour gagner du temps

### Configuration des plans

✓ **Testez en mode "Brouillon"** avant d'approuver un nouveau plan
✓ **Documentez les changements** de pourcentages pour l'audit
✓ **Validez la hiérarchie** régulièrement (départs, arrivées, promotions)
✓ **Utilisez les dates** pour gérer les plans saisonniers ou temporaires

### Gestion des déductions

✓ **Soyez précis** dans les motifs pour faciliter la compréhension
✓ **Créez les déductions obligatoires** dès que possible (acomptes, etc.)
✓ **Révisez régulièrement** les déductions en attente pour annuler celles qui sont obsolètes
✓ **Communiquez** avec les utilisateurs sur les déductions importantes

### Commissions manuelles

✓ **Justifiez toujours** la création manuelle (motif détaillé)
✓ **Vérifiez le pourcentage** appliqué selon le rôle
✓ **Liez une commande** quand c'est pertinent pour la traçabilité
✓ **Utilisez cette fonction avec parcimonie** pour maintenir l'intégrité du système automatique

### Sécurité et audit

✓ **Contrôlez l'accès** au rôle "Manager de Commissions" (droits étendus)
✓ **Auditez périodiquement** les commissions manuelles créées
✓ **Conservez l'historique** des réclamations approuvées/rejetées
✓ **Documentez les dispenses** de déductions (waive) avec motif clair

---

## 9. Flux de travail complet (récapitulatif)

### Scénario standard

```
1. Vente effectuée
   ├─→ Commande créée et confirmée
   └─→ Facture générée et envoyée

2. Client paie la facture
   └─→ Commissions auto-générées pour :
       ├─→ Commercial (vente directe)
       ├─→ Chef d'équipe (supervision)
       └─→ Directeur (supervision)

3. Commercial crée une réclamation
   ├─→ Sélectionne commissions non payées
   ├─→ Ajoute déductions optionnelles (si besoin)
   └─→ Soumet pour approbation

4. Manager approuve la réclamation
   └─→ Bon de commande créé automatiquement
       ├─→ Ligne commission (+)
       └─→ Lignes déductions (-)

5. Service achats traite le bon de commande
   ├─→ Confirme le bon
   ├─→ Génère la facture fournisseur
   └─→ Effectue le paiement

6. Commission marquée "Payée"
   └─→ Cycle terminé
```

### Scénario avec paiement direct (manager)

```
1-2. [Mêmes étapes : vente et paiement client]

3. Manager crée bon de commande directement
   ├─→ Depuis la commission non payée
   ├─→ Déductions obligatoires auto-appliquées
   └─→ Commission → "En cours"

4. [Suite identique au scénario standard]
```

---

## Support et assistance

**Pour toute question** :
- Consultez la documentation Odoo : Configuration → Aide
- Contactez l'équipe IT pour problèmes techniques
- Formez régulièrement votre équipe sur les processus de réclamation

**Ressources utiles** :
- Guide Utilisateur (à partager avec votre équipe commerciale)
- Ce guide Manager (pour les responsables de commissions)
- Historique des modifications dans les logs Odoo

---

**Version du document** : 1.0 | **Date** : Janvier 2026
