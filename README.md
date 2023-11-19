# ZotWb
 **A python app for LODifying bibliographical data, involving Zotero, Wikibase, and Wikidata**

This tool exports records in a Zotero group library to a custom Wikibase, prepares datasets to be sent to OpenRefine, and feeds OpenRefine reconciliaton results back to the Wikibase. Wikidata is envolved in the entity reconciliation.

The following are represented by default using 'item statements' (object properties), so that further steps for LOD-ification are not needed:
* Bibliographical item type
* Publication language

Creator names, or any 'string' (literal string value) property you specify are prepared for entity reconciliation using OpenRefine. Reconciliation results from Wikidata and/or from your own Wikibase (that makes sense if the entities you want to find already exist on your Wikibase) are accepted for re-feeding your Wikibase.

Identifiers (the Zotero Item ID, ISBN, ISSN, OCLC, and what you specify that my occur in the EXTRA field) are normalized and linked using 'external-id' properties.

A detailed documentation is given in the chapters in the [doc folder](doc), and also [on SSHOC Marketplace](https://marketplace.sshopencloud.eu/workflow/P0siWJ).