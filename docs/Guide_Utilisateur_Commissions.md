# Guide Utilisateur - Module Commissions

## Vue d'ensemble

Ce module vous permet de consulter vos commissions gagnées sur les ventes et de soumettre des demandes de paiement. Vos commissions sont automatiquement calculées lorsque les factures de vos ventes sont payées.

---

## 1. Consulter vos commissions

### Tableau de bord

Accédez au **Tableau de bord** via le menu **Commissions → Tableau de bord** pour voir :

- **Total des commissions** : Montant total gagné (payées, en attente, réclamables)
- **Commissions du mois** : Montant gagné ce mois-ci
- **Graphique de tendance** : Évolution de vos commissions sur 6 mois
- **Répartition par statut** : Visualisation des commissions selon leur état (En attente, Approuvée, Payée, etc.)

### Liste "Mes Commissions"

Menu **Commissions → Mes Commissions → Aperçu**

Consultez toutes vos commissions avec :
- **Référence** : Numéro unique de la commission
- **Date** : Date de génération
- **Vendeur** : Votre nom
- **Rôle** : Votre fonction (Commercial, Chef d'équipe, etc.)
- **Type** :
  - *Vente directe* : Commission sur vos propres ventes
  - *Commission de supervision* : Commission sur les ventes de vos subordonnés
- **Montant** : Valeur de la commission
- **Statut** : Non payée, Réclamée, Approuvée, En cours, Payée

**Filtres disponibles** :
- Par statut (Non payée, Réclamée, Approuvée, Payée)
- Par type de commission
- Par période

### Commissions de l'équipe (pour superviseurs)

Si vous supervisez une équipe, accédez à **Commissions → Mes Commissions → Commissions d'équipe** pour voir toutes les commissions de vos subordonnés.

---

## 2. Réclamer vos commissions

### Comment créer une réclamation

1. **Accédez à vos commissions non payées**
   - Menu : **Commissions → Mes Commissions → Aperçu**
   - Filtrez par statut : **Non payée**

2. **Sélectionnez les commissions à réclamer**
   - Cochez les commissions que vous souhaitez réclamer
   - Cliquez sur **Action → Réclamer le paiement**

3. **Ajoutez les déductions optionnelles** (si nécessaire)
   - Dans l'assistant de réclamation, vous pouvez sélectionner des déductions optionnelles :
     - Frais de services
     - Formation
     - Matériaux
     - Autres
   - Les déductions obligatoires sont automatiquement appliquées

4. **Vérifiez le montant net**
   - **Total commissions** : Somme des commissions sélectionnées
   - **Total déductions** : Déductions obligatoires + optionnelles
   - **Montant net** : Ce que vous recevrez réellement

5. **Soumettez votre réclamation**
   - Cliquez sur **Soumettre pour approbation**
   - Votre demande passe à l'état **En attente d'approbation**

### Suivi de vos réclamations

Menu **Commissions → Mes Commissions → Mes réclamations**

Consultez l'historique de toutes vos réclamations :
- **Brouillon** : Réclamation non encore soumise (modifiable)
- **En attente** : Soumise, en attente de validation du manager
- **Approuvée** : Validée par le manager, bon de commande créé
- **Rejetée** : Refusée par le manager (commissions retournent à "Non payée")

**Note importante** : Une fois qu'une réclamation est approuvée, un bon de commande (Purchase Order) est automatiquement créé pour traiter votre paiement.

---

## 3. Comprendre les déductions

### Types de déductions

#### Déductions obligatoires
Ces déductions sont **automatiquement appliquées** à toutes vos réclamations :
- Acomptes déjà versés
- Frais de service obligatoires
- Formations obligatoires

#### Déductions optionnelles
Vous pouvez **choisir** d'ajouter ces déductions lors de la création de votre réclamation :
- Génération de leads
- Matériaux commandés
- Autres achats ou services

### Visualisation des déductions

Dans le formulaire de réclamation, vous verrez :
```
Commissions sélectionnées :        1 500,00 €
Déductions obligatoires :            -200,00 €
Déductions optionnelles :            -100,00 €
─────────────────────────────────────────────
Montant net à payer :              1 200,00 €
```

**Astuce** : Les déductions sont déduites de votre paiement, mais elles restent traçables dans votre réclamation.

---

## 4. Questions fréquentes

**Q : Quand mes commissions sont-elles générées ?**
R : Automatiquement lorsque la facture liée à votre vente est **entièrement payée** par le client.

**Q : Je ne vois pas mes commissions récentes ?**
R : Vérifiez que :
- La facture a été payée (pas seulement confirmée)
- Vous êtes assigné à un plan de commissions actif
- Votre rôle a un pourcentage de commission configuré

**Q : Puis-je modifier une réclamation soumise ?**
R : Non. Une fois soumise, seul un manager peut l'approuver ou la rejeter. Si vous devez modifier, contactez votre responsable.

**Q : Combien de temps prend l'approbation ?**
R : Cela dépend de votre manager. Une fois approuvée, le bon de commande est créé immédiatement et le paiement suit le processus d'achat habituel.

**Q : Pourquoi mon montant est différent de prévu ?**
R : Vérifiez :
- Les déductions obligatoires appliquées
- Votre pourcentage de commission selon votre rôle
- Le type de commission (vente directe vs supervision)

**Q : Puis-je réclamer une seule commission à la fois ?**
R : Oui, mais il est plus efficace de regrouper plusieurs commissions non payées dans une seule réclamation.

---

## Conseils pratiques

✓ **Consultez régulièrement** votre tableau de bord pour suivre vos performances
✓ **Réclamez rapidement** vos commissions non payées pour accélérer le paiement
✓ **Vérifiez les déductions** avant de soumettre une réclamation
✓ **Groupez vos réclamations** pour simplifier le traitement
✓ **Contactez votre manager** en cas de questions sur une commission ou une réclamation rejetée

---

**Support** : Pour toute question ou problème technique, contactez votre responsable ou l'équipe IT.
