# Deduplicating and Reconciling person names in OpenRefine

This function will produce a CSV sheet to be imported into OpenRefine, containing all unreconciled (i.e., literal only) creator statements (including all creator role properties). The CSV file will be saved in your [`profiles/{profile}/data/creators_unreconciled`](profiles/{profile}/data/creators_unreconciled) folder.

## Deduplication (optional)

Deduplication using the [Clustering function](https://openrefine.org/docs/manual/cellediting#cluster-and-edit)

1. Starting point is the column containing the full name of persons.

2. To perform **clustering** without losing original column content, select the column menu:

	* `Edit column > Add column based on this column > value`.
    
	* Choose a column name, e.g. `fullName_clusters`.
    
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
    
	Validation of name clusters includes selecting one of the names as the normalized name variant. Within the column `fullName_clusters`, this preferred name variant will replace the various name forms previously found in the data.
    
5. To perform **merging of duplicates** for normalized person names in `fullName_clusters`, once again select the column menu: `edit column > Add column based on this column > value`. REQUIRED COLUMN NAME: `fullName_preferred`.
    
6. Before duplicates can be eliminated, sort alphabetically and re-order permanently:

	`Sort > a-z`
	`Sort > re-order rows permanently`
	`Edit cells > Blank down`

	These steps result in a list of preferred person names that appear only once in the column. Preferred full names are thus connected to preferred given names and last names.
    
## Reconciliation

**Reconciliation** will be based on the column `fullName_clusters`. If no clustering was performed, Reconciliation will be based on the raw person data in the column `fullName`.
    
1. Person names may already be included in your Wikibase. If not, they might be found in Wikidata. In both cases, the [Reconciliation function](https://openrefine.org/docs/manual/reconciling) searches for matches in the specified dataset.

	For each reconciliation process, create a separate column based on `fullName_clusters` (or `fullName`) column using `edit column > Add column based on this column > value`.

	REQUIRED COLUMN NAMES:
	fullName_recon_Wikidata
	fullName_recon_Wikibase
    
2. For each recon column, invoke the reconciliation process using `Reconcile > Start reconciling`. From the list of reconciliation services, pick the appropriate one, leading to your Wikibase or to Wikidata. If not already selected, select an entity type such as `human` (Q5) to restrict possible reconciliation targets. Be careful with the function `automatically match candidates with high confidence`; that is risky, since it is not at all unlikely that there exist several persons with the same or similar name on Wikidata, and only one (or none) of these is the one you want to link to.
    
3. Validate reconciliation candidates. Approved reconciled person names are now linked to their corresponding person item in Wikibase/Wikidata. 
4. Now create a new column containing the person item identifier from Wikibase/Wikidata using `Reconcile > Add entity identifiers column`
    
    Specify the new column's name as REQUIRED: 
     * `Wikidata_Qid`
     * `Wikibase_Qid`
5. Export as comma seperated value (csv) to your `data/creators_reconciled` folder using `Export > comma separated values`
