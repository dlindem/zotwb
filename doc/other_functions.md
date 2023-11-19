# ZotWb: Helper functions

ZotWb includes the following functions for editing your Zotero group and your Wikibase

## Functions for your Zotero Group

### Batch edit Zotero fields

Specify a Zotero tag for max. 100 items to batch edit and fetch these items.
You can batch edit any field, except creators. 
What you enter as a value below and submit will be written to all datafields with that name in the records with that tag.

### Remove tags from Zotero items

Specify a Zotero tag to remove from max. 100 items.

## Functions for your Wikibase

### DOI Wikidata lookup

For items with a DOI but not linked to any Wikidata item, this function tries to find the item on Wikidata using its DOI.

### ISSN Wikidata lookup

For items with a ISSN statement not qualified with any Wikidata item representing the journal, this function tries to find the journal on Wikidata using its ISSN.

### Link chapters to their containers

Try to link book chapters and conference papers with a ISBN statement to their container item (a book); that works if the container item appears with the same ISBN as the chapter.


### Import entities from Wikidata to your Wikibase

This function enables you to import entities (items, properties) from Wikidata to your Wikibase in a few clicks.
* You can choose the languages you want labels, aliases, and descriptions to be imported
* You can import import statements describing the entity, as long the Wikidata property is aligned to your local equivalent property.
  * We encourage you not to massively import statements, and make use of [federated queries](https://www.mediawiki.org/wiki/Wikibase/Federation) instead.
  * Statements pointing to items (properties of datatype `WikibaseItem`) are excluded from this function in the current version.

