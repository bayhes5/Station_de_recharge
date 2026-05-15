Scénarios fonctionnels complets
===============================

Cette page décrit les parcours utilisateur et terrain de bout en bout. Elle sert
de référence commune pour distinguer les moyens d'accès, le rôle du téléphone,
le rôle du kiosque Raspberry et le rôle des ESP32.

Principes à retenir
-------------------

La réservation reste la source métier de l'accès. Le backend Django décide si
une charge peut démarrer. Le Raspberry exécute localement une décision validée :
il lit le badge, affiche l'interface, relaie les appels terminal et publie les
commandes MQTT vers l'ESP32.

Deux QR codes différents existent :

.. list-table::
   :header-rows: 1
   :widths: 22 38 40

   * - QR
     - Moment de création
     - Rôle
   * - QR de réservation
     - Dès la création d'une réservation en mode QR.
     - Identifie une réservation précise. L'utilisateur l'affiche sur son
       téléphone et une borne équipée d'un lecteur QR le scanne.
   * - QR de session mobile
     - Quand l'utilisateur clique sur ``Téléphone`` au kiosque.
     - Lie temporairement le téléphone à cette borne. L'utilisateur scanne ce QR,
       se connecte à la PWA, choisit une réservation et autorise la borne.

Le code SMS temporaire est lui aussi lié à la réservation. Le secret est généré
techniquement dès la réservation afin d'être synchronisable côté station, mais il
est envoyé à l'utilisateur plus tard, par exemple peu avant le créneau ou via le
bouton ``Recevoir le code SMS``.

Scénario 1 : réservation avec QR de réservation
-----------------------------------------------

Objectif
   L'utilisateur réserve un créneau et choisit le mode ``QR``.

Préconditions
   L'utilisateur est connecté à la PWA. Une station possède au moins une borne
   active avec un emplacement libre sur le créneau choisi.

Déroulement
   1. L'utilisateur ouvre la page de réservation.
   2. Il choisit une station et un créneau.
   3. Il choisit le mode d'accès ``QR``.
   4. Le backend attribue un emplacement disponible.
   5. Le backend crée la réservation, génère le secret QR et stocke uniquement son
      hash.
   6. Le QR devient consultable dans le dashboard ou la page des réservations.

Résultat attendu
   La réservation est confirmée. Le QR est affichable immédiatement, mais il n'est
   accepté à la borne que sur la bonne station, dans la fenêtre de réservation et
   tant qu'il n'a pas été révoqué.

Cas d'erreur
   Si aucun emplacement n'est disponible, la réservation est refusée. Si le QR est
   révoqué ou expiré, le terminal refuse l'accès.

Scénario 2 : accès avec QR de réservation scanné par la borne
-------------------------------------------------------------

Objectif
   Démarrer une charge avec le QR lié à une réservation.

Préconditions
   La borne possède un lecteur QR physique. La réservation est en mode ``QR`` et
   son créneau est actif ou proche du début.

Déroulement
   1. L'utilisateur affiche le QR de réservation sur son téléphone.
   2. Sur le kiosque, il choisit ``Scanner QR`` ou présente le QR au lecteur.
   3. Le Raspberry reçoit le contenu scanné.
   4. Le Raspberry appelle ``POST /api/terminal/authenticate/`` avec le mode
      ``qr``.
   5. Django vérifie le token, la réservation, la station, la borne,
      l'emplacement, la révocation et l'expiration.
   6. Django crée ou retrouve la session de charge.
   7. Le Raspberry publie ``START`` sur ``station/<slot_id>/cmd``.
   8. L'ESP32 acquitte la commande et démarre l'état local de charge.

Résultat attendu
   Le kiosque affiche une confirmation. L'ESP32 passe en état réservé ou charge
   selon sa logique locale.

Cas d'erreur
   Un QR d'une autre station ou d'une autre borne, un QR expiré, un QR révoqué ou
   un QR dont le mode ne correspond pas à la réservation est refusé.

Scénario 3 : accès avec bouton Téléphone et QR de session mobile
----------------------------------------------------------------

Objectif
   Autoriser la borne avec le téléphone sans lecteur QR physique sur la borne.

Préconditions
   La borne est connectée au backend. Le téléphone peut joindre la PWA depuis
   l'adresse locale ou publique configurée dans ``FRONTEND_BASE_URL``.

Déroulement
   1. L'utilisateur clique sur ``Téléphone`` au kiosque.
   2. Le Raspberry appelle ``POST /api/terminal/mobile-sessions/`` via son proxy
      local.
   3. Le backend crée une session mobile temporaire et renvoie une URL PWA.
   4. Le kiosque affiche un QR contenant cette URL.
   5. L'utilisateur scanne le QR avec son téléphone.
   6. La PWA ouvre ``mobile-session.html?token=<token>``.
   7. Si l'utilisateur n'est pas connecté, la PWA l'envoie vers
      ``login.html?next=/mobile-session.html?token=<token>``.
   8. Après connexion, la PWA revient sur la session mobile.
   9. La PWA liste les réservations actives ou proches du début pour ce compte.
   10. L'utilisateur choisit une réservation compatible avec la station et la
       borne devant laquelle il se trouve.
   11. La PWA appelle ``POST /api/mobile-sessions/<token>/authorize/``.
   12. Le kiosque interroge périodiquement le statut de la session.
   13. Quand le statut devient ``authorized``, le kiosque consomme l'autorisation,
       crée ou retrouve la session de charge, puis publie ``START`` vers l'ESP32.

Résultat attendu
   Le téléphone affiche que l'autorisation a été envoyée. Le kiosque affiche le
   démarrage ou la réussite de la charge.

Cas d'erreur
   Si le token expire, il faut rescanner un nouveau QR du kiosque. Si aucune
   réservation compatible n'existe, la PWA affiche une liste vide. Si la
   réservation appartient à une autre station ou une autre borne, l'autorisation
   est refusée.

Important
   Le QR affiché par le kiosque dans ce scénario n'est pas le QR de réservation.
   Il ne contient pas la réservation. Il contient seulement une session temporaire
   de borne.

Scénario 4 : accès avec code SMS temporaire
-------------------------------------------

Objectif
   Démarrer une charge sans badge et sans QR, avec un code court reçu par SMS.

Préconditions
   La réservation est créée en mode ``code``. L'utilisateur possède un numéro de
   téléphone renseigné. Le code SMS a été envoyé avant le passage ou à la demande.

Déroulement
   1. L'utilisateur choisit ``Code SMS`` sur le kiosque.
   2. Il saisit le code de réservation.
   3. Il saisit le code SMS temporaire.
   4. Il valide les codes.
   5. Le Raspberry appelle ``POST /api/terminal/authenticate/`` avec le mode
      ``code``.
   6. Django vérifie la réservation, le hash du code SMS, la station, la borne et
      la fenêtre temporelle.
   7. Si la validation réussit, le Raspberry publie ``START`` vers l'ESP32.

Résultat attendu
   La charge démarre uniquement après validation serveur. Le bouton ou la touche
   de validation du clavier ne doit pas être présenté comme un démarrage direct :
   il valide l'authentification.

Cas d'erreur
   Une réservation en mode ``code`` est refusée si le profil n'a pas de téléphone.
   Un code SMS expiré, révoqué ou mal saisi est refusé. Un code associé à une
   autre station ou une autre borne est refusé.

Scénario 5 : accès direct avec badge RFID
-----------------------------------------

Objectif
   Démarrer une charge par présentation du badge RFID.

Préconditions
   Le badge RFID est associé au compte. La réservation active ou proche du début
   est en mode ``RFID`` et utilise ce badge.

Déroulement
   1. L'utilisateur présente son badge ACR122U au lecteur de la borne.
   2. Le Raspberry lit l'UID et le transmet au frontend kiosque.
   3. Le kiosque appelle ``POST /api/terminal/authenticate/`` avec le mode
      ``rfid``.
   4. Django retrouve le moyen d'accès RFID, l'utilisateur et la réservation
      active compatible.
   5. Django vérifie la station, la borne, le créneau, l'état de la réservation
      et la révocation du badge.
   6. Django crée ou retrouve la session de charge.
   7. Le Raspberry publie ``START`` vers l'ESP32.

Résultat attendu
   L'utilisateur n'a normalement rien à saisir sur la borne. Le badge est le
   parcours le plus rapide.

Cas d'erreur
   Un badge inconnu est refusé. Un badge révoqué est refusé. Si plusieurs
   réservations actives correspondent au même badge, le backend refuse
   l'authentification directe pour éviter une ambiguïté ; l'utilisateur doit
   utiliser le téléphone, le QR ou le code.

Scénario 6 : association d'un badge RFID
----------------------------------------

Objectif
   Associer un badge physique au compte utilisateur.

Préconditions
   L'utilisateur est connecté à la PWA et se trouve devant une borne avec lecteur
   RFID.

Déroulement
   1. Dans son profil, l'utilisateur demande un code d'association RFID.
   2. Le backend génère un code court temporaire.
   3. Sur le kiosque, l'utilisateur choisit ``Associer un badge``.
   4. Il saisit le code court.
   5. Il présente le badge au lecteur.
   6. Le Raspberry appelle ``POST /api/terminal/link-rfid/`` avec le code et
      l'UID lu.
   7. Django vérifie le code, vérifie que le badge n'est pas déjà utilisé et
      rattache le badge au compte.

Résultat attendu
   Le badge devient utilisable pour les futures réservations en mode ``RFID``.

Cas d'erreur
   Un code expiré ou déjà consommé est refusé. Un UID déjà associé à un autre
   compte est refusé. L'UID ne vient jamais de la PWA : il vient uniquement du
   lecteur RFID de la borne.

Scénario 7 : mauvaise station, mauvaise borne ou mauvais emplacement
--------------------------------------------------------------------

Objectif
   Éviter qu'un utilisateur démarre une charge sur une station, une borne ou un
   emplacement non assigné.

Déroulement
   1. L'utilisateur tente de s'authentifier sur une borne.
   2. Le kiosque transmet la station et la borne locales avec la demande
      terminal.
   3. Django compare la station, la borne et l'emplacement avec ceux de la
      réservation.

Résultat attendu
   Si la réservation appartient à une autre station ou à une autre borne,
   l'accès est refusé. Le kiosque doit expliquer que la réservation est prévue
   ailleurs lorsque l'information est disponible.

Scénario 8 : backend indisponible et mode dégradé
-------------------------------------------------

Objectif
   Maintenir une continuité limitée si le backend tombe après synchronisation des
   autorisations.

Préconditions
   Le Raspberry a synchronisé le cache offline avant la panne. La réservation et
   le secret correspondant sont déjà connus du système.

Déroulement
   1. L'utilisateur présente un badge RFID ou saisit/scanne un accès QR/code.
   2. Le kiosque tente l'appel nominal au backend.
   3. Si l'API est indisponible, le kiosque appelle le cache local
      ``/offline/authenticate``.
   4. Le cache vérifie la station, la borne, le créneau, le mode d'accès et le
      hash du secret.
   5. Si le cache valide l'accès, le Raspberry enregistre un événement offline et
      publie ``START`` vers l'ESP32.
   6. Quand le backend revient, le Raspberry resynchronise les événements offline.

Résultat attendu
   Seules les autorisations déjà synchronisées peuvent fonctionner. Le cache ne
   crée jamais une nouvelle réservation, un nouveau badge ou un nouveau secret.

Cas d'erreur
   Si le cache est vide, expiré, ambigu ou associé à une autre station ou une
   autre borne, l'accès est refusé. La session mobile par téléphone n'est pas un
   bon candidat au mode dégradé complet, car elle nécessite une interaction
   backend pour associer le téléphone, l'utilisateur et la réservation.

Scénario 9 : commande ESP32 et télémétrie
-----------------------------------------

Objectif
   Démarrer l'emplacement physique après validation métier.

Déroulement
   1. Le kiosque reçoit une validation d'accès du backend ou du cache offline.
   2. Il extrait la borne et l'emplacement, puis construit ``slot<numero>`` pour
      router la commande vers l'ESP32 concerné.
   3. Il publie une commande sur ``station/<slot_id>/cmd``.
   4. L'ESP32 reçoit ``START``.
   5. L'ESP32 répond sur ``station/<slot_id>/ack`` avec le même ``command_id``.
   6. L'ESP32 publie ensuite sa télémétrie sur
      ``station/<slot_id>/telemetry``.
   7. Le bridge MQTT backend ingère les mesures en base.
   8. Grafana affiche température, humidité, courant, tension, énergie et état de
      l'emplacement.

Résultat attendu
   En développement, ``MQTT_ACK_REQUIRED=False`` permet de tester sans ESP32
   physique. En borne réelle, ``MQTT_ACK_REQUIRED=True`` doit être activé afin de
   ne confirmer le démarrage que si l'emplacement répond.

Scénario 10 : interruption ou incident pendant la charge
--------------------------------------------------------

Objectif
   Protéger l'utilisateur et l'équipement pendant la charge.

Déroulement
   1. L'ESP32 surveille ses capteurs locaux : DHT22, INA219, porte, câble et
      relais.
   2. Il publie régulièrement la télémétrie.
   3. Si une condition dangereuse apparaît, par exemple surchauffe, boîtier
      ouvert, câble retiré ou courant anormal, l'ESP32 doit couper localement la
      charge.
   4. Il publie un statut ou une alerte MQTT.
   5. Le backend et Grafana affichent l'incident.

Résultat attendu
   La sécurité locale ne dépend pas d'un aller-retour backend. L'ESP32 reste un
   exécutant local, mais il garde la responsabilité de couper la charge en cas de
   danger matériel.

Scénario 11 : choix du moyen d'accès à la réservation
-----------------------------------------------------

Objectif
   Créer une réservation avec le bon moyen d'accès selon le profil utilisateur.

Déroulement
   1. L'utilisateur choisit une station et un créneau.
   2. Le backend calcule les bornes et emplacements disponibles, puis attribue
      un emplacement.
   3. L'utilisateur choisit le moyen d'accès.
   4. Le backend crée la réservation et prépare les secrets nécessaires.

Cas ``RFID``
   L'utilisateur doit avoir un badge actif associé à son compte. La réservation
   est liée au compte et au mode RFID. À la borne, le badge permet de retrouver
   l'utilisateur, puis sa réservation compatible.

Cas ``QR``
   Le backend génère un QR de réservation dès la création. Le QR est consultable
   dans la PWA et peut être scanné par une borne équipée d'un lecteur QR.

Cas ``code SMS``
   L'utilisateur doit avoir un numéro de téléphone renseigné. Le secret est créé
   dès la réservation, stocké sans clair et envoyé plus tard par SMS. Si aucun
   téléphone n'est disponible, ce mode doit être bloqué avant la confirmation.

Cas d'erreur
   Si aucun emplacement n'est libre, la réservation est refusée. Si le moyen
   choisi n'est pas compatible avec le compte, l'interface doit proposer un autre
   mode plutôt que créer une réservation inutilisable.

Scénario 12 : session mobile avec zéro, une ou plusieurs réservations
---------------------------------------------------------------------

Objectif
   Décrire le comportement de la PWA après scan du QR de session mobile.

Préconditions
   Le QR affiché sur le kiosque est un QR de session mobile valide. L'utilisateur
   ouvre l'URL depuis son téléphone et se connecte à son compte.

Cas aucune réservation compatible
   La PWA affiche qu'aucune réservation ne peut être utilisée sur cette borne.
   Elle peut proposer de créer une réservation ou de vérifier la station prévue.
   Le kiosque reste en attente jusqu'à expiration de la session.

Cas une réservation compatible
   La PWA affiche la réservation avec la station, la borne, l'emplacement et le
   créneau.
   L'utilisateur confirme. Le backend marque la session de borne comme
   ``authorized`` et le kiosque peut démarrer le parcours physique.

Cas plusieurs réservations compatibles
   La PWA liste les réservations utilisables. L'utilisateur en choisit une. Le
   backend associe uniquement cette réservation à la session de borne. Le kiosque
   ne doit jamais choisir seul en cas d'ambiguïté.

Cas session expirée
   La PWA affiche que la session est absente ou expirée. L'utilisateur doit
   revenir au kiosque et demander un nouveau QR de session.

Scénario 13 : annulation, révocation et support
-----------------------------------------------

Objectif
   Gérer les cas où un accès ne doit plus fonctionner.

Annulation utilisateur
   Si l'utilisateur annule la réservation avant le créneau, la réservation passe
   dans un état non utilisable. Les accès QR, SMS ou RFID associés à ce créneau
   doivent être refusés au terminal.

Révocation admin
   L'administration peut révoquer un QR, un code SMS temporaire ou un badge RFID.
   La révocation ne supprime pas la trace : elle désactive le moyen d'accès et
   alimente le journal de sécurité.

Support terrain
   Le code de réservation reste l'identifiant de support principal. Il permet de
   retrouver la réservation, la station prévue, la borne prévue, le mode choisi,
   l'état de l'authentification et les éventuelles erreurs terminal.

Synchronisation offline
   Une révocation récente doit être propagée au cache Raspberry. Tant que le
   backend est indisponible, le cache ne doit accepter que les droits encore
   valides dans sa dernière synchronisation et refuser les droits expirés.

Tableau de décision rapide
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 28 28 20

   * - Situation
     - Action utilisateur
     - Décision système
     - Résultat
   * - Badge connu, une réservation RFID active
     - Présenter le badge
     - Backend retrouve la réservation
     - Démarrage possible
   * - Badge connu, plusieurs réservations actives
     - Présenter le badge
     - Backend refuse l'ambiguïté
     - Utiliser téléphone, QR ou code
   * - Session mobile, une réservation compatible
     - Scanner le QR de borne et confirmer sur le téléphone
     - Backend autorise la session de borne
     - Démarrage possible
   * - Session mobile, aucune réservation compatible
     - Scanner le QR de borne
     - Backend ne trouve aucun droit utilisable
     - Refus ou création d'une réservation
   * - Session mobile, plusieurs réservations compatibles
     - Choisir sur le téléphone
     - Backend lie la réservation choisie à la session
     - Démarrage possible
   * - Borne avec lecteur QR
     - Montrer le QR de réservation à la borne
     - Backend valide le token
     - Démarrage possible
   * - Borne sans lecteur QR
     - Scanner le QR de session affiché par la borne
     - Téléphone choisit la réservation
     - Borne autorisée
   * - Téléphone indisponible
     - Saisir code réservation et code SMS
     - Backend valide le secret temporaire
     - Démarrage possible
   * - Mode SMS demandé sans téléphone
     - Choisir code SMS à la réservation
     - Backend bloque la création ou l'envoi
     - Choisir RFID ou QR
   * - Backend indisponible
     - Badge, QR ou code déjà synchronisé
     - Cache local vérifie le hash
     - Démarrage possible si cache valide
   * - Backend indisponible, cache absent
     - N'importe quel moyen d'accès
     - Aucun droit local fiable
     - Refus
   * - Réservation sur autre station
     - N'importe quel moyen d'accès
     - Station locale incompatible
     - Refus
   * - Réservation sur autre borne
     - N'importe quel moyen d'accès
     - Borne locale incompatible
     - Refus
   * - Secret révoqué ou expiré
     - N'importe quel moyen d'accès
     - Authentification inactive
     - Refus
