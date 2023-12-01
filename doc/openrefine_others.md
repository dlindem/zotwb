# Reconciling other literal values

This function allows you to specify any Wikibase property with datatype `String` or `ExternalId` (mapped to a Zotero field or not), the values of which you want to reconcile against entities on Wikidata and/or your own Wikibase.

The reconciliation result will be attached to the string statement as qualifier (using the property you specify in the basic configuration for referenced Wikidata entities).

Zotero literals may contain concatenated literal values that should be interpreted as multiple values. For example, the field `publication place` may contain a string like "Berlin; Amsterdam". You can specify what characters should be interpreted as separator of concatenated values in the source literals (in the example, a semicolon). The tool will than split values that contain such characters, and produce separate lines in the file to be sent to OpenRefine. As result, the string statement will be annotated with several qualifiers pointing to Wikidata items, one for each reconciled value (in the example, on for Berlin, and one for Amsterdam).

The tool produces a CSV file in your `data/strings_unreconciled` folder, which you import into OpenRefine.

You run the reconciliation (see chapter about reconciling creator names) on the column named according to the property you chose (e.g. `P15`), and when done, produce a new column with the a name ending in `_wikidata`, e.g. `P15_wikidata`, which will contain the reconciled Q-identifiers, and then export the project sheet as comma separated value (CSV) to your `data/strings_reconciled` folder.
 