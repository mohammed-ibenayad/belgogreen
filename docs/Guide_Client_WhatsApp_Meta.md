# Guide Client — Préparer WhatsApp Business (côté Meta) pour Odoo

> **À qui s'adresse ce guide ?** À l'administrateur BelGoGreen chargé de créer les comptes
> Meta / WhatsApp. Aucune compétence technique n'est requise : suivez les étapes dans
> l'ordre, cochez au fur et à mesure, puis transmettez-nous les 5 valeurs de l'étape 6
> et publiez la politique de confidentialité de l'étape 7.
> **Nous prenons ensuite le relais dans Odoo** (connexion, webhooks, modèle de message,
> tests et mise en production).

## Objectif

Envoyer automatiquement un **message de bienvenue WhatsApp** à chaque nouveau client dès
la confirmation de sa commande, en complément de l'appel de bienvenue téléphonique déjà
planifié dans Odoo (tâche « Welcom call », échéance à J+2).

L'intégration utilise la **WhatsApp Business Platform (API Cloud)** de Meta. Elle est
différente de l'application mobile *WhatsApp Business* : les comptes WhatsApp personnels
ou l'app mobile Business ne sont **pas** compatibles.

> 📚 **Références générales** :
> [Documentation Odoo — WhatsApp](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html) ·
> [Meta — Différences entre WhatsApp Business Platform et WhatsApp Business App](https://www.facebook.com/business/help/338665938087159)

---

## Avant de commencer — ce qu'il faut préparer

| ✔ | Élément | Détail |
|---|---|---|
| ☐ | Un **compte Facebook personnel** | Créé depuis **plus d'une heure** (sinon Meta bloque la création du compte business) |
| ☐ | Une **adresse e-mail professionnelle** | Utilisée pour le compte Meta Business |
| ☐ | Un **numéro de téléphone dédié** | Il recevra les messages WhatsApp des clients. ⚠️ Ce numéro ne doit **pas** être déjà enregistré sur WhatsApp (app personnelle ou Business App). S'il l'est, il faudra d'abord supprimer le compte WhatsApp existant ou migrer le numéro |
| ☐ | Une **carte de crédit d'entreprise** | Meta exige un moyen de paiement pour activer un numéro réel (anti-fraude) — les messages « utilitaires » vers vos clients sont ensuite facturés par Meta à la conversation |
| ☐ | Les **documents officiels de l'entreprise** | Numéro BCE/TVA, adresse, site web — nécessaires si Meta demande la vérification de l'entreprise |
| ☐ | Une **page « Politique de confidentialité »** sur [belgogreen.be](https://belgogreen.be/) | Meta l'exige pour la mise en production (voir étape 7). Si elle n'existe pas encore, prévoyez de la publier — nous pouvons fournir un modèle de texte |

---

## Étape 1 — Créer le compte Meta Business

1. Ouvrez [business.facebook.com/overview](https://business.facebook.com/overview).
2. Cliquez sur **Créer un compte** et renseignez : nom de l'entreprise (`BelGoGreen`),
   nom de l'administrateur, e-mail professionnel.
3. Cliquez sur **Suivant**, confirmez l'adresse e-mail via la fenêtre qui s'affiche,
   puis **Terminé**.
4. Ouvrez l'e-mail envoyé par Facebook et confirmez la création du compte.

> 💡 Si vous jonglez entre votre compte personnel et le compte business : sur
> [developers.facebook.com](https://developers.facebook.com), cliquez sur votre nom en
> haut à droite puis, sous **Business Accounts**, sélectionnez `BelGoGreen`.

> 📚 **Références** :
> [Doc Odoo — Créer un compte business Meta](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-meta-business-account) ·
> [Meta — Créer un compte Meta Business](https://www.facebook.com/business/help/1710077379203657?id=180505742745347)

## Étape 2 — Créer l'application dans la console développeur

1. Ouvrez [developers.facebook.com](https://developers.facebook.com) et connectez-vous
   avec le compte Facebook (cela crée automatiquement un compte *développeur* Meta).
2. Cliquez sur **My Apps** (en haut à droite) → **Create App**.
3. **App details** : nom de l'application = `Odoo`, e-mail de contact = votre e-mail.
   > ⚠️ N'écrivez **jamais** « WhatsApp », « Facebook » ou « Meta » dans le nom de
   > l'application : Meta rejette ces noms automatiquement.
4. **Use cases** : filtrez par **Others** → sélectionnez **Others** → **Next**.
5. **App type** : sélectionnez **Business** → **Next**.
6. **Business portfolio** : sélectionnez le compte business `BelGoGreen` créé à
   l'étape 1, acceptez les conditions, cliquez sur **Create app** et confirmez avec
   votre mot de passe Facebook.

> 📚 **Références** :
> [Doc Odoo — Créer une app développeur Meta pour Odoo](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-meta-developer-app) ·
> [Meta — Formation « Set up the WhatsApp Business Platform »](https://www.facebookblueprint.com/student/collection/409587/path/360218)

## Étape 3 — Activer le produit WhatsApp et tester

1. Depuis le tableau de bord de l'application `Odoo`
   ([developers.facebook.com/apps](https://developers.facebook.com/apps)), section
   **Add products to your app** : repérez **WhatsApp** et cliquez sur **Set up**.
2. Sélectionnez le compte business `BelGoGreen` → **Continue**.
3. Meta fournit un **numéro de test** gratuit. Dans **API Setup → Send and receive
   messages**, champ **To** → **Manage phone number list** : ajoutez jusqu'à 5 numéros
   (les vôtres) et validez-les avec le code reçu sur WhatsApp.
4. Cliquez sur **Send Message** : chaque numéro doit recevoir le message de test
   *Hello World* sur WhatsApp. ✅ Si c'est le cas, l'API fonctionne.

> 📚 **Références** :
> [Doc Odoo — Ajouter le produit WhatsApp à l'app](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-add-product) ·
> [Doc Odoo — Configuration de l'API (quickstart)](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-api-setup) ·
> [Meta — WhatsApp Cloud API : premiers pas](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started#add-recipient-number)

## Étape 4 — Ajouter le numéro de téléphone réel

1. Toujours dans **WhatsApp → API Setup**, descendez à **Step 5 : Add a phone number**
   et cliquez sur **Add phone number**.
2. Renseignez : nom de l'entreprise, site web (`https://belgogreen.be/`), pays
   (`Belgique`).
3. Complétez le **profil WhatsApp Business** : nom affiché (`BelGoGreen`), fuseau
   horaire, catégorie, description (optionnelle).
4. Saisissez le numéro dédié, choisissez la vérification par **SMS** ou **appel**,
   puis entrez le code reçu.
5. Ajoutez le **moyen de paiement** dans Meta Business Suite lorsque Meta le demande
   (obligatoire pour activer le numéro).

> 🛠️ **Numéro bloqué en « Pending » ?** Dans **WhatsApp → API Setup**, cliquez sur
> **Generate access token** → **Edit previous settings** → cochez *Opt in to all
> current and future WhatsApp accounts* → **Continue** → **Save**. Le statut passe
> alors à *Connected*.

> 📚 **Références** :
> [Doc Odoo — Ajouter un numéro de téléphone](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-add-phone-number) ·
> [Meta — Connecter votre numéro à WhatsApp Business](https://www.facebook.com/business/help/456220311516626?id=2129163877102343) ·
> [Meta — Ajouter un moyen de paiement](https://www.facebook.com/business/help/915454841921082?id=180505742745347) ·
> [Meta — Migrer un numéro WhatsApp existant](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/migrate-existing-whatsapp-number-to-a-business-account)

## Étape 5 — Créer le jeton d'accès permanent

Le jeton temporaire expire après 24 h ; sans jeton permanent, l'intégration s'arrête
(erreur « Session has expired »).

1. Ouvrez [business.facebook.com](https://business.facebook.com) →
   **Business settings → Users → System users**.
2. Cliquez sur **Add** et créez un utilisateur système avec le rôle **Admin**
   (un rôle *Employee* provoque une erreur côté Odoo).
3. Sur cet utilisateur système : **Add assets** → type **Apps** → sélectionnez `Odoo`
   → activez **Full control** → **Save changes**.
4. Cliquez sur **Generate new token** → application `Odoo` → expiration **Never**.
5. Cochez les autorisations suivantes :
   - `business_management`
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
   - `whatsapp_business_manage_events`
6. Cliquez sur **Generate token** et **copiez immédiatement** le jeton (il ne sera
   plus jamais réaffiché).

> 🛠️ `business_management` absent de la liste ? Le compte utilisé n'a pas assez de
> droits : utilisez un compte avec le rôle *Product Manager* ou supérieur dans le
> compte business, ou recréez l'application en type **Business**.

> 📚 **Références** :
> [Doc Odoo — Créer un jeton permanent](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-token) ·
> [Meta — Jetons d'accès des utilisateurs système](https://developers.facebook.com/docs/whatsapp/business-management-api/get-started#system-user-access-tokens)

## Étape 6 — Nous transmettre les valeurs (passage de relais)

Récupérez ces **5 valeurs** et transmettez-les-nous :

| # | Valeur | Où la trouver dans la console Meta |
|---|---|---|
| 1 | **App ID** | Tableau de bord de l'app `Odoo` (visible en haut) ou **App settings → Basic** |
| 2 | **App Secret** | **App settings → Basic** → bouton **Show** (mot de passe demandé) |
| 3 | **Jeton d'accès permanent** | Généré à l'étape 5 (utilisateur système) |
| 4 | **Phone Number ID** | **WhatsApp → API Setup**, sous le numéro de téléphone |
| 5 | **WhatsApp Business Account ID** (WABA ID) | **WhatsApp → API Setup**, sous *Step 1 : Select phone numbers* |

> 🔐 **Sécurité** : l'App Secret et le jeton donnent le contrôle de votre canal
> WhatsApp. Transmettez-les via un canal sécurisé (gestionnaire de mots de passe
> partagé, lien à usage unique type onetimesecret) — **jamais par simple e-mail**.

Gardez aussi sous la main un accès à la console Meta : deux allers-retours rapides
resteront nécessaires avec nous (validation du webhook, passage de l'app en mode
**Live**).

> 📚 **Référence** :
> [Doc Odoo — Configuration WhatsApp dans Odoo (où vont ces 5 valeurs)](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-odoo-configuration)

## Étape 7 — Publier la politique de confidentialité

> ⚠️ **À votre charge, indispensable avant la mise en production.** Meta refuse de passer
> l'application en mode **Live** tant qu'aucune URL publique de politique de
> confidentialité n'est renseignée. Sans mode Live, seuls les 5 numéros de test peuvent
> recevoir des messages — vos vrais clients, non.

Cette étape peut être menée **en parallèle** des étapes 1 à 6.

1. Publiez (ou vérifiez) une page « Politique de confidentialité » sur votre site,
   par exemple `https://belgogreen.be/politique-de-confidentialite`.
2. La page doit être **accessible publiquement** (sans connexion) et couvrir, dans
   l'esprit du RGPD :
   - **qui traite les données** : BelGoGreen (responsable du traitement) et ses
     coordonnées de contact ;
   - **quelles données clients** sont traitées : nom, numéro de téléphone, e-mail,
     adresse, informations liées à la commande et à l'installation ;
   - **pourquoi** : suivi du dossier client et envoi de messages de service, dont les
     **messages WhatsApp** (message de bienvenue, suivi d'installation), avec la base
     légale (exécution du contrat / intérêt légitime) ;
   - le fait que **WhatsApp / Meta** intervient comme sous-traitant technique pour
     l'acheminement des messages ;
   - la **durée de conservation** des données ;
   - les **droits des clients** (accès, rectification, effacement, opposition) et
     comment les exercer, y compris comment ne plus recevoir de messages WhatsApp.
3. Faites valider le texte par votre conseil habituel si nécessaire — **nous pouvons
   vous fournir un modèle de texte** à adapter.
4. Envoyez-nous l'**URL de la page** en même temps que les 5 valeurs de l'étape 6 :
   nous l'enregistrerons dans Meta (**App settings → Basic → Privacy Policy URL**) au
   moment du passage en mode Live.

> 📚 **Références** :
> [Meta — Exigences de lancement d'une app (dont Privacy Policy URL)](https://developers.facebook.com/docs/development/release) ·
> [Autorité de protection des données (Belgique)](https://www.autoriteprotectiondonnees.be/)

---

## Ce que nous faisons ensuite dans Odoo

1. Connexion du compte WhatsApp Business dans Odoo (App ID, App Secret, jeton,
   Phone Number ID, WABA ID) + **Test Connection**.
2. Configuration du **webhook** dans Meta (Callback URL + Verify Token générés par
   Odoo) pour recevoir les réponses de vos clients dans Discuss.
3. Création du **modèle de message de bienvenue** (`belgogreen_welcome_call`),
   soumission à Meta pour approbation, puis synchronisation.
4. Activation de l'envoi automatique : à chaque commande confirmée, la tâche
   « Welcom call » déclenche le message WhatsApp de bienvenue au client.
5. Tests de bout en bout avec les numéros de test, puis passage de l'app en mode
   **Live** avec vous, en enregistrant dans Meta l'URL de la politique de
   confidentialité préparée à l'étape 7.

> 📚 **Références** (notre partie, pour information) :
> [Doc Odoo — Configurer les webhooks](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-webhooks) ·
> [Doc Odoo — Modèles WhatsApp](https://www.odoo.com/documentation/19.0/fr/applications/productivity/whatsapp.html#productivity-whatsapp-templates) ·
> [Meta — Configurer les webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks) ·
> [Meta — Modèles de message](https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/)

## Questions fréquentes

**Combien coûte l'envoi des messages ?** Meta facture par conversation de 24 h,
selon la catégorie du message (le message de bienvenue est un message « utilitaire »).
Les messages vers les numéros de test sont gratuits. Détail des tarifs :
[Meta — Pricing WhatsApp Business Platform](https://developers.facebook.com/docs/whatsapp/pricing).

**Peut-on répondre aux clients ?** Oui : si un client répond dans les 15 jours, une
fenêtre de discussion s'ouvre dans Odoo (application Discuss) pour vos opérateurs.

**Meta demande une « vérification de l'entreprise » ?** C'est normal pour obtenir un
accès complet : préparez les documents officiels (BCE/TVA, adresse, site web) et suivez
l'assistant dans Business Suite → Security Center. Prévenez-nous, nous suivons le
dossier avec vous. Référence :
[Meta — Business verification](https://developers.facebook.com/docs/development/release/business-verification).

**Le message de test ne part pas ?** Vérifiez que le numéro destinataire figure bien
dans la liste des 5 numéros de test validés (étape 3) et que l'app est encore en mode
*Development* — dans ce mode, seuls les numéros de test peuvent être contactés.
