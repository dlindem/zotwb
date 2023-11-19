# Importing reconciliation results to your Wikibase

You have saved your reconciliation result CSV file in the `profiles/{profile}/data/creators_reconciled` or `profiles/{profile}/data/reconciled_others` folder.

* Run the function you need (for creators or others)

## Importing reconciled creators
* The tool will ingest the newest CSV file in the folder, and ask you to confirm that it is the file you want to process.
* For lines containing a Wikibase identifier, it will use the indicated item, and, in case the line also contains a Wikidata identifier, attach that to the item.
* For lines containing a Wikidata identifier, but no Wikibase identifier, it will check if an item aligned to that Wikidata entity already exists, and if not, create it on your Wikibase.
* The `unknown value` statement the ID of which is listed in the row will be replaced by a `custom value` statement pointing to the Wikibase item describing the creator.
* It will then process the name literals found in the CSV line:
  * The preferred full name variant (column `fullName_preferred`) will be written to `label`, in the languages you have specified in the configuration step.
  * Other name variants found in the row will be written to `alias`.
  * If the row `fullName_preferred` is not empty, creator first and last names are additionally written to the item in the following ways:
    * In the form [Lastname], [Firstname] to `alias`.
    * Creator first and last names will be written as string statements to the properties defined to that in the configuration step, replacing any other value possibly present for these properties.

## Importing other reconciled values
* The tool will ingest the newest CSV file in the folder, and ask you to confirm that it is the file you want to process.
* For lines containing a Wikibase identifier, it will use the indicated item, and, in case the line also contains a Wikidata identifier, attach that to the item.
* For lines containing a Wikidata identifier, but no Wikibase identifier, it will check if an item aligned to that Wikidata entity already exists, and if not, create it on your Wikibase.
* All values are attached to the correspondent Wikibase item (first column) using the property of datatype `WikibaseItem` you specified.