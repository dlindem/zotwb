# Reconciling other literal values

This function allows you to specify any Wikibase property with datatype `String` mapped to a Zotero field, the values of which you want to reconcile against entities on Wikidata and/or your own Wikibase.

Together with the `String` property, you define a property of datatype `WikibaseItem`, which will be later used for pointing to the reconciled entity. The tool allows you to do that in three ways:
* A property that already exists on your Wikibase
* A property that is newly created for this purpose
* A property that is imported from Wikidata for this purpose

Zotero literals may contain concatenated literal values that should be interpreted as multiple values. For example, the field `publication place` may contain a string like "Berlin; Amsterdam". You can specify what characters should be interpreted as separator of concatenated values in the source literals (in the example, a semicolon). The tool will than split values that contain such characters, and produce separate lines in the file to be sent to OpenRefine.

The tool produces a CSV file in your [`data/unreconciled_others`](data/unreconciled_others) folder, which you import into OpenRefine.

You run the reconciliation (see chapter about reconciling creator names) on the column named according to the property you chose, and when done, produce a new column with the REQUIRED name `Wikidata_Qid`, and/or `Wikibase_Qid`, respectively, which will contain the reconciled Q-identifiers, and then export the project sheet as comma separated value (CSV) to your [`data/reconciled_others`](data/reconciled_others) folder.
 