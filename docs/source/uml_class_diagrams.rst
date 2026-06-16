Diagrammes de classes UML
=========================

Cette page complète la référence du schéma relationnel avec une lecture plus
orientée objet. Les diagrammes de classes UML ne remplacent pas le MCD complet :
ils servent à présenter les grands blocs fonctionnels du modèle sans surcharger
une seule image.

Les classes sont issues du fichier DBML utilisé par la page :doc:`database_mcd`.
Les diagrammes sont décrits avec PlantUML afin de garder une source textuelle
standard, relisible et versionnée. Les champs marqués ``PK`` représentent les
identifiants principaux et les champs marqués ``FK`` les références vers
d'autres classes.

Régénération des diagrammes
---------------------------

Les sources PlantUML peuvent être régénérées depuis la racine du projet avec :

.. code-block:: powershell

   .\.venv\Scripts\python.exe scripts\generate_plantuml_class_diagrams.py

Si PlantUML est disponible, la même commande régénère aussi les images PNG.
Sinon, il faut indiquer le chemin du jar PlantUML :

.. code-block:: powershell

   $env:PLANTUML_JAR="C:\outils\plantuml.jar"
   .\.venv\Scripts\python.exe scripts\generate_plantuml_class_diagrams.py

Identités et accès
------------------

Ce diagramme regroupe les comptes, profils, rôles, consentements, journaux de
sécurité et moyens d'authentification.

Source PlantUML : :download:`uml_identites_acces.puml <_static/uml/uml_identites_acces.puml>`.

.. image:: _static/uml/uml_identites_acces.png
   :alt: Diagramme de classes UML - identités et accès
   :align: center
   :width: 100%

Infrastructure, réservation et supervision
------------------------------------------

Ce diagramme montre la chaîne principale du projet : station, borne,
emplacement, ESP32, capteurs, réservation, session de charge, télémétrie,
commandes MQTT et alertes.

Source PlantUML : :download:`uml_infrastructure_charge.puml <_static/uml/uml_infrastructure_charge.puml>`.

.. image:: _static/uml/uml_infrastructure_charge.png
   :alt: Diagramme de classes UML - infrastructure, réservation et supervision
   :align: center
   :width: 100%

Maintenance et exploitation
---------------------------

Ce diagramme isole le périmètre technicien : rattachement à un compte,
affectation aux stations, interventions de maintenance et prise en charge des
alertes.

Source PlantUML : :download:`uml_maintenance_exploitation.puml <_static/uml/uml_maintenance_exploitation.puml>`.

.. image:: _static/uml/uml_maintenance_exploitation.png
   :alt: Diagramme de classes UML - maintenance et exploitation
   :align: center
   :width: 100%
