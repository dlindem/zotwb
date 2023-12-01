# Importing reconciliation results to your Wikibase

You have saved your reconciliation result CSV file in the `profiles/{profile}/data/creators_reconciled` or `profiles/{profile}/data/strings_reconciled` folder.

* Run the function you need (for creators, or for literal string values of any string-like property (`String`, `ExternalID`)

## Importing reconciled values (creators and others)
* For creators: The tool will ingest the newest CSV file in the folder, and ask you to confirm that it is the file you want to process. For reconciled string values: The tool will present you a list of the files in the folder, for you to choose which file to process.
* For creators:
   * For lines containing a Wikibase identifier, it will use the indicated item, and, in case the line also contains a Wikidata identifier, attach that to the item.
   * For lines containing a Wikidata identifier, but no Wikibase identifier, it will check if an item aligned to that Wikidata entity already exists, and if not, create it on your Wikibase.
   * The `unknown value` statement the ID of which is listed in the row will be replaced by a `custom value` statement pointing to the Wikibase item describing the creator.
   * It will then process the name literals found in the CSV line:
     * Rows with identical values in column `fullName_clusters` will be treated as cluster, i.e., the corresponding statements will be pointing to the same creator item.
     * The preferred full name variant (column `fullName_preferred`) will be written to `label`, in the languages you have specified in the configuration step.
     * Other name variants found in the row will be written to `alias`.
     * Creator first and last names are additionally written to the item in the following ways:
        * In the form [Lastname], [Firstname] to `alias`.
        * Creator first and last names will be written as string statements to the properties defined to that in the configuration step, replacing any other value possibly present for these properties.
* For strings:
   * The tool will add a qualifier to the source literal statement, pointing to the reconciled Wikidata item.
