# Zotero export

Now you can already start to export Zotero records! The mapping of the Zotero fields to Wikibase properties (which still may have to be created or completed) is done when running the export tool.

* In the previous step, you have specified a tag you will use for marking Zotero items to be exported, such as `wikibase-export`. Mark some items with that tag (and sync with Zotero web, in case you work on a local Zotero instance.)
* Run the Zotero export function
  * The tool first checks what Zotero item types you want to export, and will create a Wikibase Item representing each item type, in case it does not exist. For this, it imports the corresponding item from Wikidata, as defined in `[profile]/zotero_types_wd.json`.
  * The tool asks you then whether you want to check the mapping of the fields of these item types. As long as you are not sure all fields you want to export are mapped to a property, you should do this.
    * You can specify existing properties to use, or create new properties along the process. You are able to map fields differently according to the item type. For example, you may want to have titles of books mapped to a different property than titles of television broadcasts.
    * You can also choose to provisionally or permanently ignore certain Zotero fields, depending on the item type. It is recommended to ignore the `abstract` field for all BibItem types, since that regularly contains more than the amount of characters allowed for a Wikibase string property.
  * The script asks you then whether you want to do the same with the creator types present in the ingested dataset.
  * When that is done, the script transforms the Zotero API output, and uploads it to your Wikibase.
    * The Zotero API will deliver you chunks of 100 items. That is, if you tag more than 100 with your export tag, only one hundred of these will be processed in one run. Those that are not processed in one run will stay with the export tag.
    * Zotero items are patched the following way:
      * The Wikibase URI is written to the EXTRA field
      * The Wikibase URI is attached as URI link attachment
      * The tag used for marking Zotero items to be exported will be replaced with the tag you have specified in the previous step for successfully exported items, such as `on-wikibase`.