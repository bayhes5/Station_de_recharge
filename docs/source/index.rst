Station de recharge
====================

Cette documentation rassemble les notes techniques du backend Django, de l'API
REST, du frontend Vite et des composants embarqués de la solution.

La version publiée sur GitHub Pages est disponible à l'adresse :
https://bayhes5.github.io/Station_de_recharge/

.. toctree::
   :maxdepth: 2
   :caption: Guide

   architecture
   user_scenarios
   implementation_guide
   raspberry_kiosk
   raspberry_esp32_contract
   esp32_firmware
   database_mcd
   uml_class_diagrams
   data_model
   requirements_traceability
   station_supervision
   semantic_web_sparql
   operations_runbook
   debian_production_deployment
   testing_strategy
   test_plan_table
   git_github_workflow
   technical_choices
   api_openapi
   development
   backend_reference

Objectifs documentaires
-----------------------

* garder une documentation versionnée avec le code ;
* justifier les choix techniques importants du projet ;
* publier une documentation API interactive avec drf-spectacular ;
* documenter progressivement les modules Django avec Sphinx autodoc ;
* fournir des commandes simples pour régénérer la documentation.
