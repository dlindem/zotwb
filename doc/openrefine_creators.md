# Deduplicating and Reconciling person names in OpenRefine

This function will produce a CSV sheet to be imported into OpenRefine, containing all unreconciled (i.e., literal only) creator statements (including all creator role properties). The CSV file will be saved in your [`profiles/{profile}/data/creators_unreconciled`](profiles/{profile}/data/creators_unreconciled) folder.

## Deduplication (optional)

Deduplication using the [Clustering function](https://openrefine.org/docs/manual/cellediting#cluster-and-edit)

1. Starting point is the column `fullName_clusters`.
    
3.  Clustering algorithms can be accessed with `Edit cells > Cluster and edit`.
    
4. Perform all clustering algorithms in the recommended order and manually validate the found name clusters. Different algorithms may detect different degrees and types of string similarity.
	* key collision - fingerprint
	* key collision - ngram fingerprint
	* key collision - metaphone3
	* key collision - cologne-phonetic
	* key collision - Daitch-Mokotoff
	* key collision - Beider-Morse
	* nearest neighbor - Levenshtein
	* nearest neighbor - ppm
    
	Validation of name clusters includes selecting one of the names as the normalized name variant. 
	
	Within the column `fullName_clusters`, this preferred name variant will replace the various name forms previously found in the data. All rows in the resulting CSV having the same value in the `fullName_clusters` column will be treated as one when re-feeding the results to Wikibase. That is, in case that the corresponding person is found neither on Wikidata nor on your Wikibase, only one entity is created for the whole cluster. 
    
	If the Wikibase item representing that person has to be created new, or if it still has no labels and no statements for `preferred given name` and `preferred family name`, those will be created using `givenName` and `lastName` values from the first row in the cluster; change the row order if necessary. 
	
	In any case, the name variants of each row are written to the person item as alias labels (using the values in `fullName`, `givenName` and `lastName`).
    
## Reconciliation

**Reconciliation** will be based on the column `fullName_clusters`.
    
1. Person names may already be included in your Wikibase. If not, they might be found in Wikidata. In both cases, the [Reconciliation function](https://openrefine.org/docs/manual/reconciling) searches for matches in the specified dataset.

	For each reconciliation process (Wikidata and/or Wikibase), create a separate column based on `fullName_clusters` (or `fullName`) column using `edit column > Add column based on this column > value`.

	REQUIRED COLUMN NAMES:
	fullName_recon_Wikidata
	fullName_recon_Wikibase
    
2. For the recon column(s), invoke the reconciliation process using `Reconcile > Start reconciling`. From the list of reconciliation services, pick the appropriate one, leading to your Wikibase or to Wikidata. If not already selected, select an entity type such as `human` (Q5) to restrict possible reconciliation targets. Be careful with the function `automatically match candidates with high confidence`; that is risky, since it is not at all unlikely that there exist several persons with the same or similar name on Wikidata, and only one (or none) of these is the one you want to link to.
    
3. Validate reconciliation candidates. Approved reconciled person names are now linked to their corresponding person item in Wikibase/Wikidata. 
4. Now create a new column containing the person item identifier from Wikibase/Wikidata using `Reconcile > Add entity identifiers column`
    
    These columns will contain the Q-identifiers of the linked items. Specify the new column names as REQUIRED: 
     * `Wikidata_Qid`
     * `Wikibase_Qid`
   
5. Export as comma seperated value (csv) to your `data/creators_reconciled` folder (inside your profile folder) using `Export > comma separated values`
