import traceback, time, re, os, requests, json
from wikibaseintegrator import wbi_login, WikibaseIntegrator
from wikibaseintegrator.datatypes.string import String
from wikibaseintegrator.datatypes.externalid import ExternalID
from wikibaseintegrator.datatypes.item import Item
from wikibaseintegrator.datatypes.lexeme import Lexeme
from wikibaseintegrator.datatypes.monolingualtext import MonolingualText
from wikibaseintegrator.datatypes.time import Time
from wikibaseintegrator.datatypes.globecoordinate import GlobeCoordinate
from wikibaseintegrator.datatypes.url import URL
from wikibaseintegrator.models import Reference, References, Form, Sense
from wikibaseintegrator.models.qualifiers import Qualifiers
from wikibaseintegrator.models.claims import Claims
from wikibaseintegrator import wbi_helpers
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseSnakType
from bots import botconfig
from wikibaseintegrator.wbi_config import config as wbi_config

# from wikibaseintegrator.models.claims import Claims

# load active profile
with open(f"profiles.json", 'r', encoding='utf-8') as file:
	profile = json.load(file)['last_profile']
	if profile == "":
		profile = "profile.template"
with open(f"profiles/{profile}/config_private.json", 'r', encoding="utf-8") as jsonfile:
	config_private = json.load(jsonfile)
config = botconfig.load_mapping('config')
print(f"Will load profile {profile} for Wikibase {config['mapping']['wikibase_api_url']}...")
try:
	wbi_config['BACKOFF_MAX_TRIES'] = 5
	wbi_config['BACKOFF_MAX_VALUE'] = 3600
	wbi_config['USER_AGENT'] = config['mapping']['wikibase_name']+' user'
	wbi_config['PROPERTY_CONSTRAINT_PID'] = None # 'P2302'
	wbi_config['DISTINCT_VALUES_CONSTRAINT_QID'] = None # 'Q21502410'
	wbi_config['COORDINATE_GLOBE_QID'] = 'http://www.wikidata.org/entity/Q2'
	wbi_config['CALENDAR_MODEL_QID'] = 'http://www.wikidata.org/entity/Q1985727'
	wbi_config['MEDIAWIKI_API_URL'] = config['mapping']['wikibase_api_url']
	wbi_config['MEDIAWIKI_INDEX_URL'] = config['mapping']['wikibase_index_url']
	wbi_config['MEDIAWIKI_REST_URL'] = config['mapping']['wikibase_rest_url']
	wbi_config['SPARQL_ENDPOINT_URL'] = config['mapping']['wikibase_sparql_endpoint']
	wbi_config['WIKIBASE_URL'] = config['mapping']['wikibase_url']
	wbi_config['DEFAULT_LANGUAGE'] = 'en' # config['mapping']['wikibase_default_language']
	wbi_config['DEFAULT_LEXEME_LANGUAGE'] = "Q207" # This is for Lexemes. Value None raises error.
	wd_user_agent = config['mapping']['wikibase_site'] + ", User " + config_private['wb_bot_user']
except Exception as ex:
	if profile == "profile.template":
		print("Profile configuration not completed. Cannot configure wikibase bot.")
	else:
		print(f"{profile}: Profile configuration could not be done due to missing values in config.json file in profile folder.")
		print(str(ex))

def wbi_do_login():
	if config_private['wb_bot_user'] and config_private['wb_bot_pwd']:
		try:
			login_instance = wbi_login.Login(user=config_private['wb_bot_user'], password=config_private['wb_bot_pwd'])
			wbi = WikibaseIntegrator(login=login_instance)
			print('**** Wikibase bot username and password accepted, xwbi can be loaded. ****')
			return wbi
		except Exception as ex:
			if 'Incorrect username or password entered' in str(ex):
				print('**** Wikibase bot username or password not accepted, xwbi cannot be loaded. ****')
			else:
				raise
	else:
		print('Wikibase bot is not configured, cannot be loaded.')
wbi = wbi_do_login()


# functions for interaction with wbi
def packstatements(statements, wbitem=None, qualifiers=False, references=False):
	packed_statements = []
	for statement in statements:
		packed_statement = None
		if "qualifiers" in statement:
			packed_qualifiers = packstatements(statement['qualifiers'], qualifiers=True)
		else:
			packed_qualifiers = []
		if "references" in statement:
			packed_references = packstatements(statement['references'], references=True)
		else:
			packed_references = []
		snaktype = WikibaseSnakType.KNOWN_VALUE
		if 'value' in statement:
			if statement['value'] == False: # unknown value statement
				statement['value'] == None
				snaktype = WikibaseSnakType.UNKNOWN_VALUE

		actions = {
		'append': ActionIfExists.APPEND_OR_REPLACE,
		'replace': ActionIfExists.REPLACE_ALL,
		'force': ActionIfExists.FORCE_APPEND,
		'keep': ActionIfExists.KEEP
		}
		if 'action' in statement:
			action = actions[statement['action']]
		else:
			action = ActionIfExists.APPEND_OR_REPLACE
		if statement['type'].lower() == "string":
			packed_statement = String(value=statement['value'].strip(),prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
		elif statement['type'].lower() == "item" or statement['type'].lower() == "wikibaseitem":
			packed_statement = Item(value=statement['value'], prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
		elif statement['type'].lower() == "externalid":
			packed_statement = ExternalID(value=statement['value'],prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
		elif statement['type'].lower() == "lexeme":
			packed_statement = Lexeme(value=statement['value'],prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
		elif statement['type'].lower() == "time":
			if 'value' not in statement:
				statement['value'] = statement['time']
			packed_statement = Time(time=statement['value'], precision=statement['precision'], prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
			#print('Time statement: '+str(packed_statement))
		elif statement['type'].lower() == "monolingualtext":
			if 'value' not in statement:
				statement['value'] = statement['text']
			packed_statement = MonolingualText(text=statement['value'], language=statement['lang'], prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
		elif statement['type'].lower() == "url":
			packed_statement = URL(value=statement['value'], prop_nr=statement['prop_nr'],qualifiers=packed_qualifiers,references=packed_references)
		if not packed_statement:
			print('***ERROR: Unknown datatype in '+str(statement))
		# print(str(packed_statement))
		if qualifiers or references:
			packed_statements.append(packed_statement)
		else:
			packed_statement.mainsnak.snaktype = snaktype
			wbitem.claims.add([packed_statement], action_if_exists=action)
	if qualifiers or references:
		return packed_statements
	return wbitem

def itemwrite(itemdata, clear=False, entitytype='Item', datatype=None):
	global wbi
	if itemdata['qid'] == False:
		if entitytype == "Item":
			xwbitem = wbi.item.new()
			print('Will write to new Q-item', end="")
		elif entitytype == "Property":
			xwbitem = wbi.property.new(datatype=datatype)
			print('Will write to new P-item', end="")
	elif itemdata['qid'].startswith('Q'):
		xwbitem = wbi.item.get(entity_id=itemdata['qid'])
		print('Will write to existing item '+itemdata['qid'], end="")
	elif itemdata['qid'].startswith('P'):
		xwbitem = wbi.property.get(entity_id=itemdata['qid'])
		print('Will write to existing property '+itemdata['qid'], end="")
	else:
		print('No Entity ID given.')
		return False
	if clear:
		xwbitem.claims = Claims()

	# labels
	if 'labels' in itemdata:
		langstrings = itemdata['labels']
		for langstring in langstrings:
			lang = langstring['lang']
			stringval = langstring['value']
			xwbitem.labels.set(lang,stringval)
	# altlabels
	if 'aliases' in itemdata:
		langstrings = itemdata['aliases']
		for langstring in langstrings:
			lang = langstring['lang']
			stringval = langstring['value']
			xwbitem.aliases.set(lang,stringval)
	# descriptions
	if 'descriptions' in itemdata:
		langstrings = itemdata['descriptions']
		for langstring in langstrings:
			lang = langstring['lang']
			stringval = langstring['value']
			#print('Found wikidata description: ',lang,stringval)
			xwbitem.descriptions.set(lang,stringval)

	# statements
	for statement in itemdata['statements']:
		xwbitem = packstatements([statement], wbitem=xwbitem)

	d = False
	while d == False:
		try:
			print(f"...now writing to {config['mapping']['wikibase_name']}...", end="")
			r = xwbitem.write(clear=clear)
			d = True
			print('successfully written to entity: '+xwbitem.id)
		except Exception:
			ex = traceback.format_exc()
			print(ex)
			if "wikibase-validator-label-with-description-conflict" in str(ex):
				print('\nFound an ambiguous item label: same description conflict.')
			elif "already has label" in str(ex):
				regex = re.search(r'(Q[0-9]+)\]\] already has label', str(ex))
				if regex:
					qid = regex.group(1)
					input(f"Error: Item {qid} has the same label and the same description... On ENTER we use that in order to avoid duplicate creation.")
					return qid
			elif "Invalid CSRF token." in str(ex):
				print("TRY TO GET NEW TOKEN and re-do the operation with the new login instance")
				wbi = wbi_do_login()
				return itemwrite(itemdata, clear=clear, entitytype=entitytype, datatype=datatype)
			else:
				print("Unexpected error while writing to wikibase. Item data was:")
				print(str(xwbitem.get_json()))
			presskey = input('Enter 0 for skipping and continue without writing statements, else retry writing.')
			if presskey == "0":
				print("Item write operation skipped.")
				return False
	return xwbitem.id

def importitem(wdqid, wbqid=False, process_claims=True, classqid=None):
	languages_to_consider = config['mapping']['wikibase_label_languages']
	
	print('Will get ' + wdqid + ' from wikidata...')
	
	apiurl = 'https://www.wikidata.org/w/api.php?action=wbgetentities&ids=' + wdqid + '&format=json'
	# print(apiurl)
	wdjsonsource = requests.get(url=apiurl)
	if wdqid in wdjsonsource.json()['entities']:
		importitemjson = wdjsonsource.json()['entities'][wdqid]
	else:
		print('Error: Recieved no valid item JSON from Wikidata.')
		return False

	wbitemjson = {'labels': [], 'aliases': [], 'descriptions': [],
				  'statements': [{'prop_nr': config['mapping']['prop_wikidata_entity']['wikibase'], 'type': 'externalid', 'value': wdqid}]}

	# ontology class
	if classqid:
		wbitemjson['statements'].append({'prop_nr': config['mapping']['prop_instanceof']['wikibase'], 'type': 'Item', 'value': classqid})

	# process labels
	for lang in importitemjson['labels']:
		if lang in languages_to_consider:
			wbitemjson['labels'].append({'lang': lang, 'value': importitemjson['labels'][lang]['value']})
	# process aliases
	for lang in importitemjson['aliases']:
		if lang in languages_to_consider:
			for entry in importitemjson['aliases'][lang]:
				# print('Alias entry: '+str(entry))
				wbitemjson['aliases'].append({'lang': lang, 'value': entry['value']})
	# process descriptions
	for lang in importitemjson['descriptions']:
		if lang in languages_to_consider:
			if {'lang': lang, 'value': importitemjson['descriptions'][lang]['value']} not in wbitemjson['labels']:
				wbitemjson['descriptions'].append(
					{'lang': lang, 'value': importitemjson['descriptions'][lang]['value']})

	# process claims
	if process_claims:
		for claimprop in importitemjson['claims']:
			if claimprop in props_wd_wb:  # aligned prop
				wbprop = props_wd_wb[claimprop]
				for claim in importitemjson['claims'][claimprop]:
					claimval = claim['mainsnak']['datavalue']['value']
					claimtype = claim['mainsnak']['datavalue']['type']
					# if propwbdatatype[wbprop] == "WikibaseItem":
					# 	if claimval['id'] not in itemwd2wb:
					# 		print(
					# 			'Will create a new item for ' + claimprop + ' (' + wbprop + ') object property value: ' +
					# 			claimval['id'])
					# 		targetqid = importitem(claimval['id'], process_claims=False)
					# 	else:
					# 		targetqid = itemwd2wb[claimval['id']]
					# 		print('Will re-use existing item as property value: wd:' + claimval[
					# 			'id'] + ' > eusterm:' + targetqid)
					# 	statement = {'prop_nr': wbprop, 'type': 'Item', 'value': targetqid}
					# else:
					statement = {'prop_nr': wbprop, 'type': claimtype, 'value': claimval,'action': 'keep'}
					statement['references'] = [{'prop_nr': 'P2', 'type': 'externalid', 'value': wdqid}]
				wbitemjson['statements'].append(statement)
	# process sitelinks
	if 'sitelinks' in importitemjson:
		for site in importitemjson['sitelinks']:
			if site.replace('wiki', '') in languages_to_consider:
				wpurl = "https://"+site.replace('wiki', '')+".wikipedia.org/wiki/"+importitemjson['sitelinks'][site]['title'].replace(' ','_')
				print(wpurl)
				wbitemjson['statements'].append({'prop_nr':config['mapping']['prop_wikidata_sitelinks']['wikibase'],'type':'url','value':wpurl})

	wbitemjson['qid'] = wbqid  # if False, then create new item. If wbqid given, prop-values are transferred to that item using action 'keep' [existing values]
	result_qid = itemwrite(wbitemjson)
	print('Wikidata item import successful.')
	return result_qid





print('xwbi wikibase bot function load finished.')
