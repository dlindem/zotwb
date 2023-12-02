# This is parts of the old version of the LexBib Wikibase bot, using single api calls for every action through mwclient

import mwclient
import json
import time
import re
from bots import botconfig

# load active profile
with open(f"profiles.json", 'r', encoding='utf-8') as file:
    profile = json.load(file)['last_profile']
with open(f"profiles/{profile}/config_private.json", 'r', encoding="utf-8") as jsonfile:
	config_private = json.load(jsonfile)
config = botconfig.load_mapping('config')

card1props = [config['mapping']['prop_wikidata_entity']['wikibase']]

# LexBib wikibase OAuth for mwclient

site = mwclient.Site(config['mapping']['wikibase_site'])
# site = mwclient.Site(re.sub(r'https?://','',config['mapping']['wikibase_url']))
def get_token():
	global site

	# lwb login via mwclient
	while True:
		try:
			login = site.login(username=config_private['wb_bot_user'], password=config_private['wb_bot_pwd'])
			break
		except Exception as ex:
			print('Wikibase login via mwclient raised error (will try again in 20 seconds...): \n'+str(ex))
			time.sleep(20)
	# get token
	csrfquery = site.api('query', meta='tokens')
	token = csrfquery['query']['tokens']['csrftoken']
	print(f"Got fresh CSRF token for {config['mapping']['wikibase_name']}.")
	return token
token = ""

claimcache = {"item": None, "claims": None}
#get claims from qid
def getclaims(s, p):
	global claimcache
	# returns subject and response to wbgetclaim api query, example:
	# https://lexbib.elex.is/wiki/Special:ApiSandbox#action=wbgetclaims&format=json&entity=Q14680

	if claimcache['item'] != s: # if claims of that item have not just been retrieved before

		# get claims and put in claimcache
		done = False
		count = 0
		while count < 4 and done == False:
			count += 1
			print('Getting existing claims for '+s+'...')
			try:
				request = site.get('wbgetclaims', entity=s)

				if "claims" in request:
					done = True
					#print('Getclaims will return: '+s, request['claims'])
					claimcache['item'] = s
					claimcache['claims'] = request['claims']
			except Exception as ex:
				# if 'unresolved-redirect' in str(ex):
				#
				# 	#get redirect target
				# 	url = "https://lexbib.elex.is/query/sparql?format=json&query=PREFIX%20lwb%3A%20%3Chttp%3A%2F%2Flexbib.elex.is%2Fentity%2F%3E%0APREFIX%20ldp%3A%20%3Chttp%3A%2F%2Flexbib.elex.is%2Fprop%2Fdirect%2F%3E%0APREFIX%20lp%3A%20%3Chttp%3A%2F%2Flexbib.elex.is%2Fprop%2F%3E%0APREFIX%20lps%3A%20%3Chttp%3A%2F%2Flexbib.elex.is%2Fprop%2Fstatement%2F%3E%0APREFIX%20lpq%3A%20%3Chttp%3A%2F%2Flexbib.elex.is%2Fprop%2Fqualifier%2F%3E%0A%0Aselect%20%28strafter%28str%28%3Fredirect%29%2C%22http%3A%2F%2Flexbib.elex.is%2Fentity%2F%22%29%20as%20%3Frqid%29%20where%0A%7Blwb%3A"+s+"%20owl%3AsameAs%20%3Fredirect.%7D%0A%20%20%0A"
				# 	subdone = False
				# 	while (not subdone):
				# 		try:
				# 			r = requests.get(url)
				# 			bindings = r.json()['results']['bindings']
				# 		except Exception as ex:
				# 			print('Error: SPARQL request for redirects failed: '+str(ex))
				# 			time.sleep(2)
				# 			continue
				# 		subdone = True
				#
				# 	if 'rqid' in bindings[0]:
				# 		print('Found redirect target '+bindings[0]['rqid']['value']+', will use that instead.')
				# 		s = bindings[0]['rqid']['value']
				# 		continue
				print('Getclaims operation for',s,p,' failed, will try again...\n'+str(ex))
				time.sleep(4)
		if not done:
			print('Getclaims operation failed. Item may not exist.')
			return False
	if p == True: # return all claims
		print('Will return all claims.')
		return (s, claimcache['claims'])
	if p in claimcache['claims']:
		return (s, {p: claimcache['claims'][p]})
	return (s, {})

# set a Qualifier
def setqualifier(qid=None, prop=None, claimid=None, qualiprop=None, qualio=None, dtype=None, replace=True):
	global token
	# global card1props
	if token == "":
		token = get_token()
	guidfix = re.compile(r'^(Q\d+)\-')
	claimid = re.sub(guidfix, r'\1$', claimid)
	if dtype == "string" or dtype == "url" or dtype == "externalid":
		qualivalue = '"'+qualio.replace('"', '\\"')+'"'
	elif dtype == "item" or dtype =="wikibase-entityid":
		qualivalue = json.dumps({"entity-type":"item","numeric-id":int(qualio.replace("Q",""))})
	elif dtype == "time":
		qualivalue = json.dumps({
		"entity-type":"time",
		"time": qualio['time'],
	    "timezone": 0,
	    "before": 0,
	    "after": 0,
	    "precision": qualio['precision'],
	    "calendarmodel": "http://www.wikidata.org/entity/Q1985727"})
	elif dtype == "monolingualtext":
		qualivalue = json.dumps(qualio)
	if replace:
		print('Will replace any existing qualifier with that property ID.')
		existingclaims = getclaims(qid,prop)
		#print(str(existingclaims))
		qid = existingclaims[0] # this resolves merged item redirect problem
		existingclaims = existingclaims[1]
		if prop in existingclaims:
			for claim in existingclaims[prop]:
				if claim['id'] != claimid:
					continue # skip other claims
				if "qualifiers" in claim:
					if qualiprop in claim['qualifiers']:
						existingqualihashes = {}
						for quali in claim['qualifiers'][qualiprop]:
							existingqualihash = quali['hash']
							existingqualivalue = quali['datavalue']['value']
							if isinstance(existingqualivalue, dict):
								if "time" in existingqualivalue:
									existingqualivalue = {"time":existingqualivalue['time'],"precision":existingqualivalue['precision']}
								if "text" in existingqualivalue and "language" in existingqualivalue:
									existingqualivalue = json.dumps(existingqualivalue)
							existingqualihashes[existingqualihash] = existingqualivalue
						#print('Found an existing '+qualiprop+' type card1 qualifier: '+str(list(existingqualihashes.values())[0]))
						allhashes = list(existingqualihashes.keys())
						done = False
						while (not done):
							if len(existingqualihashes) > 1:
								print('Found several qualis, but cardinality is 1; will delete all but the newest.')
								for delqualihash in allhashes:
									if delqualihash == allhashes[len(allhashes)-1]: # leave the last one intact
										print('Will leave intact this quali: '+existingqualihashes[delqualihash])
										existingqualihash = existingqualihashes[delqualihash]
									else:
										removequali(claimid,delqualihash)
										del existingqualihashes[delqualihash]
							elif len(existingqualihashes) == 1:
								done = True

						if str(list(existingqualihashes.values())[0]) in qualivalue:
							print('Found duplicate value for card1 quali. Skipped.')
							return True
						if dtype == "time":
							if list(existingqualihashes.values())[0]['time'] == qualio['time'] and list(existingqualihashes.values())[0]['precision'] == qualio['precision']:
								#print('Found duplicate value for '+qualiprop+' type time card1 quali. Skipped.')
								return True

						print('New value to be written to existing card1 quali.')
						try:
							while True:
								setqualifier = site.post('wbsetqualifier', token=token, claim=claimid, snakhash=existingqualihash, property=qualiprop, snaktype="value", value=qualivalue, bot=1)
								# always set!!
								if setqualifier['success'] == 1:
									print('Qualifier set ('+qualiprop+') '+qualivalue+': success.')
									return True
								print('Qualifier set failed, will try again...')
								time.sleep(2)

						except Exception as ex:
							if 'The statement has already a qualifier' in str(ex):
								print('The statement already has that object as ('+qualiprop+') qualifier: skipped writing duplicate qualifier')
								return False
	# not a max1quali >> write new quali in case value is different to existing value
	try:
		while True:
			setqualifier = site.post('wbsetqualifier', token=token, claim=claimid, property=qualiprop, snaktype="value", value=qualivalue, bot=1)
			# always set!!
			if setqualifier['success'] == 1:
				print('Qualifier set ('+qualiprop+') '+qualivalue+': success.')
				return True
			print('Qualifier set failed, will try again...')
			time.sleep(2)

	except Exception as ex:
		if 'The statement has already a qualifier' in str(ex):
			print('The statement already has a ('+qualiprop+') '+qualivalue+': skipped writing duplicate qualifier')
			return False
		else:
			print('Error: '+str(ex))
			time.sleep(5)

print('xwb wikibase bot functions imported.')