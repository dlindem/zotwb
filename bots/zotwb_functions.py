from bots import botconfig
from bots import zoterobot
import requests, time, re, json, csv
import os, glob, sys, shutil
from pathlib import Path
import pandas, shutil
from bots import xwbi

def create_profile(name=""):
    print(f"Will proceed to create profile named '{name}'")
    if re.search(r'[^a-zA-Z0-9_]', name) or len(name) < 3 or len(name) > 10:
        return {'messages': ["Invalid input. The profile name may only contain a-z, A-Z letters, numbers and underscores, and be min 3 and max 10 characters long."],
                'msgcolor': 'background:orangered'}
    with open('profiles.json', 'r', encoding='utf-8') as file:
        profiles = json.load(file)
    if name in profiles['profiles_list']:
        return {'messages': ["Invalid input. The profile name already exists. Choose a different identifier for the new profile."],
                'msgcolor': 'background:orangered'}
    shutil.copytree('profiles/profile.template', f"profiles/{name}")
    profiles['profiles_list'].append(name)
    profiles['last_profile'] = name
    with open('profiles.json', 'w', encoding='utf-8') as file:
        json.dump(profiles, file, indent=2)
    return {'messages': [f"Successfully created and activated new profile <b>'{name}'</b>.", '<b>Now quit and restart the ZotWb app in the terminal.<b>'],
                'msgcolor': 'background:limegreen'}

def check_prop_id(propstring):
    if propstring == "False" or propstring == "X":
        return False
    if re.search(r'^P[0-9]+$',propstring):
        return propstring
    return None

def build_depconfig(configdata):
    wikibase_url = configdata['mapping']['wikibase_url']
    configdata['mapping']['wikibase_site'] = re.sub(r'https?://', '', wikibase_url)
    configdata['mapping']['wikibase_entity_ns'] = wikibase_url + "/entity/"
    configdata['mapping']['wikibase_api_url'] = wikibase_url + "/w/api.php"
    configdata['mapping']['wikibase_sparql_endpoint'] = wikibase_url + "/query/sparql"
    configdata['mapping']['wikibase_rest_url'] = wikibase_url + "/w/rest.php"
    configdata['mapping']['wikibase_index_url'] = wikibase_url + "/w/index.php"
    configdata['mapping']['wikibase_sparql_prefixes'] = ('\n').join([
        "PREFIX xwb: <" + wikibase_url + "/entity/>",
        "PREFIX xdp: <" + wikibase_url + "/prop/direct/>",
        "PREFIX xp: <" + wikibase_url + "/prop/>",
        "PREFIX xps: <" + wikibase_url + "/prop/statement/>",
        "PREFIX xpq: <" + wikibase_url + "/prop/qualifier/>",
        "PREFIX xpr: <" + wikibase_url + "/prop/reference/>",
        "PREFIX xno: <" + wikibase_url + "/prop/novalue/>"
    ])+'\n'
    return configdata

def rewrite_properties_mapping():
    properties = botconfig.load_mapping('properties')
    properties['mapping'] = {}
    config = botconfig.load_mapping('config')

    query = """select ?order ?prop ?propLabel ?datatype ?wikidata_prop ?formatter_url ?formatter_uri (group_concat(str(?equiv)) as ?equivs) 
    where {  ?prop rdf:type <http://wikiba.se/ontology#Property> ;
             wikibase:propertyType ?dtype .
             optional {?prop rdfs:label ?propLabel . filter (lang(?propLabel)="en")}
             bind (strafter(str(?dtype),"http://wikiba.se/ontology#") as ?datatype)
      OPTIONAL {?prop xdp:""" + config['mapping']['prop_wikidata_entity']['wikibase'] + """ ?wikidata_prop.} """
    if config['mapping']['prop_formatterurl']['wikibase']:
        query += " OPTIONAL {?prop xdp:" + config['mapping']['prop_formatterurl']['wikibase'] + " ?formatter_url.} "
    if config['mapping']['prop_formatterurirdf']['wikibase']:
        query += " OPTIONAL {?prop xdp:" + config['mapping']['prop_formatterurirdf']['wikibase'] + " ?formatter_uri.} "
    if config['mapping']['prop_equivalentprop']['wikibase']:
        query += " OPTIONAL {?prop xdp:" + config['mapping']['prop_equivalentprop']['wikibase'] + " ?equiv.} "
    query += ' BIND (xsd:integer(strafter(str(?prop), "'+config['mapping']['wikibase_entity_ns']+'P")) as ?order )'
    query += '} group by ?order ?prop ?propLabel ?datatype ?wikidata_prop ?formatter_url ?formatter_uri ?equivs order by ?order'

    print("Waiting for SPARQL...")
    bindings = xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'], endpoint=config['mapping']['wikibase_sparql_endpoint'])['results']['bindings']
    print('Found ' + str(len(bindings)) + ' results to process.\n')
    count = 0
    for item in bindings:
        prop_nr = item['prop']['value'].replace(config['mapping']['wikibase_entity_ns'], "")
        if 'propLabel' in item:
            enlabel = item['propLabel']['value']
        else:
            enlabel = prop_nr
        properties['mapping'][prop_nr] = {
            'enlabel': enlabel,
            'type': item['datatype']['value'],
            'wdprop': item['wikidata_prop']['value'] if 'wikidata_prop' in item else None
        }
        if 'formatter_url' in item:
            properties['mapping'][prop_nr]['formatter_url'] = item['formatter_url']['value']
        if 'formatter_uri' in item:
            properties['mapping'][prop_nr]['formatter_uri'] = item['formatter_uri']['value']
        if 'equivs' in item:
            properties['mapping'][prop_nr]['equivalents'] = item['equivs']['value'].split(' ')

    botconfig.dump_mapping(properties)

    print('\nSuccessfully stored properties mapping.')

def batchimport_wikidata(form, config={}, properties={}):
    imported_stubs = []
    print(f"Batch wikidata import started. Will get existing mappings (query for {config['mapping']['prop_wikidata_entity']['wikibase']})")
    query = """select ?wb_entity ?wd_entity where {?wb_entity xdp:"""+config['mapping']['prop_wikidata_entity']['wikibase']+""" ?wd_entity.  }"""
    print("Waiting for SPARQL...")
    bindings = \
    xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])['results'][
        'bindings']
    print('Found ' + str(len(bindings)) + ' Wikibase-Wikidata mappings.\n')
    wd_to_wb = {}
    for row in bindings:
        wd_to_wb[row['wd_entity']['value'].replace('http://www.wikidata.org/entity/','')] = row['wb_entity']['value'].replace(config['mapping']['wikibase_entity_ns'],'')
    import_entities = re.findall(r'[QP][0-9]+', form.get('qids'))
    if not import_entities:
        return {'messages':["No entities to import."], 'msgcolor': 'background:orangered'}
    extra_statement = None
    if 'statement_prop' in form and 'statement_value' in form:
        if form.get('statement_prop').strip().startswith('P') and form.get('statement_value').startswith('Q'):
            if form.get('statement_prop').strip() not in properties['mapping']:
                return {'messages': [f"Bad value for 'statement property': {form.get('statement_prop')}."], 'msgcolor': 'background:orangered'}
            elif properties['mapping'][form.get('statement_prop').strip()]['type'] != "WikibaseItem":
                return {'messages':[f"Property {form.get('statement_prop')} is not of datatype 'WikibaseItem'."], 'msgcolor': 'background:orangered'}
            elif not re.search('^Q[0-9]+$', form.get('statement_value').strip()):
                return {'messages':[f"Bad value for 'statement value': {form.get('statement_value')}."], 'msgcolor': 'background:orangered'}
            extra_statement = {'prop_nr': form.get('statement_prop').strip(), 'value':form.get('statement_value').strip()}
    classqid = None
    if 'instance_of_statement' in form:
        if form.get('instance_of_statement').strip().startswith('Q'):
            if not re.search('^Q[0-9]+$', form.get('instance_of_statement').strip()):
                return {'messages': [f"Bad value for 'instance-of-statement value': {form.get('instance_of_statement')}."],
                        'msgcolor': 'background:orangered'}
            classqid = form.get('instance_of_statement').strip()

    if 'labels_check' in form:
        process_labels = True
    else:
        process_labels = False
    if 'aliases_check' in form:
        process_aliases= True
    else:
        process_aliases = False
    if 'descriptions_check' in form:
        process_descriptions = True
    else:
        process_descriptions = False
    if 'sitelinks_check' in form:
        process_sitelinks = True
    else:
        process_sitelinks = False
    wbprops_to_import = []
    for key in form:
        if re.search(r'P[0-9]', key):
            wbprops_to_import.append(key)

    seen_wd_entities=[]
    messages = []
    for wd_entity in import_entities:
        if wd_entity in seen_wd_entities:
            print(f"Skipped importing wd:{wd_entity} - has been imported before in this run.")
            continue
        if wd_entity in wd_to_wb:
            wb_entity = wd_to_wb[wd_entity]  # existing entity
        else:
            wb_entity = False  # new wikibase entity to create
        import_action = import_wikidata_entity(wd_entity, wd_to_wb=wd_to_wb, wbid=wb_entity,
                                           process_labels=process_labels,
                                           process_aliases=process_aliases,
                                           process_descriptions=process_descriptions,
                                           process_sitelinks=process_sitelinks,
                                           wbprops_to_import=wbprops_to_import,
                                           classqid=classqid,
                                           config=config, properties=properties)
        seen_wd_entities.append(wd_entity)
        imported_stubs += import_action['imported_stubs']
        wb_entity = import_action['id']
        wd_to_wb = import_action['wd_to_wb']
        print(f"Successfully imported wd:{wd_entity} to wb:{wb_entity}.")
        if extra_statement:
            xwbi.itemwrite({'qid': wb_entity, 'statements':[{'prop_nr': extra_statement['prop_nr'], 'type':'WikibaseItem', 'value':extra_statement['value']}]})
        messages.append(f"Successfully created or updated <a href=\"{config['mapping']['wikibase_entity_ns']}{wb_entity}\" target=\"_blank\">wb:{wb_entity}</a> importing <a href=\"http://www.wikidata.org/entity/{wd_entity}\" target=\"_blank\">wd:{wd_entity}</a>.")
    return {'messages': messages, 'msgcolor': 'background:limegreen', 'imported_stubs':imported_stubs}



def import_wikidata_entity(wdid, wbid=False, wd_to_wb={}, process_labels=True, process_aliases=True, process_descriptions=True, process_sitelinks=False, wbprops_to_import=[], classqid=None, config=None, properties=None):
    if wdid in wd_to_wb:
        wbid=wd_to_wb[wdid]
    imported_stubs = []
    if not config:
        config = botconfig.load_mapping('config')
    if not properties:
        properties = botconfig.load_mapping('properties')
    languages_to_consider = config['mapping']['wikibase_label_languages']
    print('Will import ' + wdid + ' from wikidata... to existing wikibase entity: '+str(wbid))
    apiurl = 'https://www.wikidata.org/w/api.php?action=wbgetentities&ids=' + wdid + '&format=json'
    print(apiurl)
    wdjsonsource = requests.get(url=apiurl)
    if wdid in wdjsonsource.json()['entities']:
        importentityjson = wdjsonsource.json()['entities'][wdid]
        # print(str(importentityjson))
    else:
        print('Error: Received no valid item JSON from Wikidata.')
        return False

    wbentityjson = {'labels': [], 'aliases': [], 'descriptions': [],
                  'statements': [{'prop_nr': config['mapping']['prop_wikidata_entity']['wikibase'], 'type': 'ExternalId', 'value': wdid}]}
    if classqid:
        wbentityjson['statements'].append({'prop_nr': config['mapping']['prop_instanceof']['wikibase'], 'type': 'Item', 'value': classqid})

    if wbid and wbid.startswith('Q'):
        wb_existing_entity = xwbi.wbi.item.get(entity_id=wbid)
    elif wbid and wbid.startswith('P'):
        wb_existing_entity = xwbi.wbi.property.get(entity_id=wbid)

    # process labels
    existing_preflabel = None
    if process_labels:
        for lang in languages_to_consider:
            if wbid:
                existing_preflabel = str(wb_existing_entity.labels.get(lang))
            if lang in importentityjson['labels']:
                importlabel = importentityjson['labels'][lang]['value']
                if existing_preflabel and len(existing_preflabel) > 0:
                    if importlabel.lower() != existing_preflabel.lower():
                        wbentityjson['aliases'].append({'lang': lang, 'value': importlabel})
                        # wikidata label becomes wikibase alias if different to existing wikibase label
                else:
                    wbentityjson['labels'].append({'lang': lang, 'value': importlabel})
    # process aliases
    if process_aliases:
        for lang in languages_to_consider:
            existing_aliases = []
            if wbid:
                raw_aliases = wb_existing_entity.aliases.get(lang)
                if raw_aliases:
                    for alias in raw_aliases:
                        existing_aliases.append(alias.value.lower())
                        wbentityjson['aliases'].append({'lang': lang, 'value': alias.value})
            if lang in importentityjson['aliases']:
                for entry in importentityjson['aliases'][lang]:
                    if entry['value'].lower() not in existing_aliases and entry['value'].lower() != existing_preflabel:
                        wbentityjson['aliases'].append({'lang': lang, 'value': entry['value']})
    # process descriptions
    if process_descriptions:
        for lang in importentityjson['descriptions']:
            if lang in languages_to_consider:
                if {'lang': lang, 'value': importentityjson['descriptions'][lang]['value']} not in wbentityjson['labels']:
                    wbentityjson['descriptions'].append(
                        {'lang': lang, 'value': importentityjson['descriptions'][lang]['value']})
    # process claims
    for wbprop in wbprops_to_import:
        wdprop = properties['mapping'][wbprop]['wdprop']
        if wdprop in importentityjson['claims']:
            for claim in importentityjson['claims'][wdprop]:
                claimval = claim['mainsnak']['datavalue']['value']
                if properties['mapping'][wbprop]['type'] == "WikibaseItem":
                    if not claimval['id']:
                        continue
                    if claimval['id'] not in wd_to_wb:
                        print(
                            'Will create a new item for ' + wdprop + ' (' + wbprop + ') object property value: ' +
                            claimval['id'])
                        import_action = import_wikidata_entity(claimval['id'], wbid=False)  # property target object to be imported without statements
                        targetqid = import_action['id']
                        imported_stubs.append(claimval['id'])
                        wd_to_wb[claimval['id']] = targetqid
                    else:
                        targetqid = wd_to_wb[claimval['id']]
                        print(f"Will re-use existing item as property value: wd:{claimval['id']} > wb:{targetqid}")
                    statement = {'prop_nr': wbprop, 'type': 'WikibaseItem', 'value': targetqid}
                else:
                    statement = {'prop_nr': wbprop, 'type': properties['mapping'][wbprop]['type'], 'value': claimval,
                                 'action': 'keep'}
                statement['references'] = [{'prop_nr': config['mapping']['prop_wikidata_entity']['wikibase'], 'type': 'externalid', 'value': wdid}]
            wbentityjson['statements'].append(statement)
    # process sitelinks
    if process_sitelinks:
        if 'sitelinks' in importentityjson:
            for site in importentityjson['sitelinks']:
                if site.replace('wiki', '') in languages_to_consider:
                    wpurl = "https://" + site.replace('wiki', '') + ".wikipedia.org/wiki/" + \
                            importentityjson['sitelinks'][site]['title'].replace(" ", "_")
                    # print(wpurl)
                    wbentityjson['statements'].append({'prop_nr': config['mapping']['prop_wikidata_sitelinks']['wikibase'], 'type': 'url', 'value': wpurl,
                                                       'references':[{'prop_nr': config['mapping']['prop_wikidata_entity']['wikibase'], 'type': 'externalid', 'value': wdid}]})

    wbentityjson['qid'] = wbid  # if False, then create new item
    print(str(wbentityjson))
    if 'datatype' in importentityjson: # this is true for properties
        result = xwbi.itemwrite(wbentityjson, entitytype="Property", datatype=importentityjson['datatype'])
    else:
        result = xwbi.itemwrite(wbentityjson, entitytype="Item")
    wd_to_wb[wdid] = result
    return {'id':result, 'imported_stubs': imported_stubs, 'wd_to_wb':wd_to_wb}

def write_property(prop_object):
    while True:
        try:
            print('Writing to xwb wikibase...')
            r = prop_object.write(is_bot=1, clear=False)
            print('Successfully written data to item: ' + prop_object.id)
            return prop_object.id
        except Exception as ex:
            print(ex)
            print("Will retry to write to Wikibase...")
            time.sleep(2)

def propagate_mapping(zoteromapping={}, fieldtype="", fieldname="", wbprop=""):
    messages=[]
    for itemtype in zoteromapping:
        if fieldname in zoteromapping[itemtype][fieldtype]:
            if zoteromapping[itemtype][fieldtype][fieldname]['wbprop'] != wbprop:
                oldval = zoteromapping[itemtype][fieldtype][fieldname]['wbprop']
                zoteromapping[itemtype][fieldtype][fieldname]['wbprop'] = wbprop
                messages.append(f"Updated {itemtype}-{fieldname} to {wbprop}. Old value was {str(oldval)}.")
    return {'mapping': zoteromapping, 'messages':messages}

def check_config(configdata={}):
    print('Will perform zotero field and creator type mapping for the current zotero export dataset...')
    config_message = []
    status_ok = True
    for mapping in configdata:
        if type(configdata[mapping]) == str:
            if len(configdata[mapping]) == 0:
                status_ok = False
                config_message.append(f"Configuration for '{mapping}' is undefined, you have to fix that.")
        elif type(configdata[mapping]) == list:
            if len(configdata[mapping]) == 0:
                status_ok = False
                config_message.append(f"Configuration for '{mapping}' is undefined, you have to fix that.")
        elif mapping.startswith("prop_") or mapping.startswith("class_"):
            if not configdata[mapping]['wikibase']:
                status_ok = False
                config_message.append(f"Configuration for '{mapping}' is undefined, you have to fix that.")
    if status_ok:
        return {'message': ["Your basic configuration appears to be complete."], 'color': 'color:green'}
    else:
        return {'message': config_message, 'color': 'color:red'}

def check_export(zoterodata=[], zoteromapping={}):
    messages = []
    for item in zoterodata:
        itemtype = item['data']['itemType']
        missing_mapping_message = ' Fix this <a href="./zoterofields/' + itemtype + '" target="_blank">here</a> <small>(or <a href="./zoterofields/all_types">here</a> for all item types at once)</small>'
        # check item type Qid
        if not zoteromapping['mapping'][itemtype]['bibtypeqid']:
            newmsg = 'The "'+itemtype+'" item type has no Wikibase entity defined.'
            messages.append(newmsg+missing_mapping_message)
            print(newmsg)
        # check data fields
        seen_fields = []
        seen_creators = []
        fields_processed_before = ['itemType', 'creators', 'ISBN', 'extra']
        for fieldname in item['data']:
            if (item['data'][fieldname] != "") and (fieldname not in fields_processed_before) and (itemtype + fieldname not in seen_fields) and (fieldname in zoteromapping['mapping'][itemtype]['fields']):
                if zoteromapping['mapping'][itemtype]['fields'][fieldname]['wbprop'] == False:
                    print(f"Skipping {itemtype} > {fieldname} as marked for permanent omission.")
                elif zoteromapping['mapping'][itemtype]['fields'][fieldname]['wbprop']:
                    print(f"Found existing mapping: {fieldname} > {zoteromapping['mapping'][itemtype]['fields'][fieldname]['wbprop']}")
                else:
                    newmsg = f"<i>{itemtype}</i> '<b>{fieldname}</b>': No wikibase property defined."
                    messages.append(newmsg+missing_mapping_message)
                    print(newmsg)
            seen_fields.append(itemtype + fieldname)
        # check creator types
        if 'creators' not in item['data']:
            continue
        for creatordict in item['data']['creators']:
            creatortype = creatordict['creatorType']
            if itemtype + creatortype in seen_creators:
                continue
            if zoteromapping['mapping'][itemtype]['creatorTypes'][creatortype]['wbprop'] == False:
                print(f"Skipping {itemtype}>{creatortype} as marked for permanent omission.")
                seen_creators.append(itemtype + creatortype)
                continue
            if zoteromapping['mapping'][itemtype]['creatorTypes'][creatortype]['wbprop']:
                print(f"Will use existing mapping: {creatortype} > {zoteromapping['mapping'][itemtype]['creatorTypes'][creatortype]['wbprop']}")
                seen_creators.append(itemtype + creatortype)
            else:
                newmsg = f"<i>{itemtype}</i> creator type '<b>{creatortype}</b>': No mapping defined."
                messages.append(newmsg+missing_mapping_message)
                print(newmsg)
    if len(messages) == 0:
        messages = ['<span style="color:green">All datafields containing data in this dataset are mapped to Wikibase properties or set to be ignored.</span>']
    return messages

def check_language(zoterodata=[]):
    configdata = botconfig.load_mapping('config')
    iso3mapping = botconfig.load_mapping('iso-639-3')
    iso1mapping = botconfig.load_mapping('iso-639-1')
    language_literals = botconfig.load_mapping('language-literals')
    messages = {'nullitems':[], 'nomaps':{}, 'languages': set()}
    nomaps = {}
    for item in zoterodata:
        if 'language' not in item['data']:
            continue
        langval = item['data']['language']
        languageqid = False
        if len(langval) == 0:
            messages['nullitems'].append(f"<code><a href=\"{item['links']['alternate']['href']}/item-details\", target=\"_blank\">{item['key']}</a></code>")
        if len(langval) == 2:  # should be a ISO-639-1 code
            if langval.lower() in iso1mapping['mapping']:
                oldval = langval
                langval = iso1mapping['mapping'][langval.lower()]
                print(f"Language field: Found two-digit language code '{oldval}' and converted to three-letter code '{langval}'.")
        if len(langval) == 3:  # should be a ISO-639-3 code
            if langval.lower() in iso3mapping['mapping']:
                languageqid = iso3mapping['mapping'][langval.lower()]['wbqid']
                print('Language field: Found three-digit language code, mapped to ' +
                      iso3mapping['mapping'][langval.lower()]['enlabel'], languageqid)
                messages['languages'].add(iso3mapping['mapping'][langval.lower()]['enlabel'])
        if languageqid == False:  # Can't identify language using ISO 639-1 or 639-3
            if langval in language_literals['mapping']:
                iso3 = language_literals['mapping'][langval].lower()
                languageqid = iso3mapping['mapping'][iso3]['wbqid']
                print('Language field: Found stored language literal, mapped to ' +
                      iso3mapping['mapping'][iso3]['enlabel'] + ', ' + str(languageqid) + ' on wikibase.')
                action = batchedit_literal(fieldname='language', literal=langval, replace_value=iso3, zoterodata=zoterodata, remove_tag=None)
                messages['nomaps'][langval] = action['messages']
            elif len(langval) > 1:  # if there is a string that could be useful
                print(f"{langval}': This value could not be matched to any language.")
                if langval not in messages['nomaps']:
                    messages['nomaps'][langval] = []
                messages['nomaps'][langval].append(f"<code><a href=\"{item['links']['alternate']['href']}/item-details\" target=\"_blank\">{item['key']}</a></code>")
        if languageqid == None:  # Language item is still not on the wikibase (got 'None' from iso3mapping)
            languagewdqid = iso3mapping['mapping'][langval]['wdqid']
            print(
                f"No item defined for this language on your Wikibase. This language is {languagewdqid} on Wikidata. I'll import that and use it from now on.")
            languageqid = import_wikidata_entity(languagewdqid,
                                                 classqid=configdata['mapping']['class_language'][
                                                     'wikibase'], config=configdata)['id']
            iso3mapping['mapping'][langval]['wbqid'] = languageqid
            botconfig.dump_mapping(iso3mapping)
            print(f"Imported wd:{languagewdqid} to wb:{languageqid}.")
    messages['nullitemlen'] = len(messages['nullitems'])
    messages['nomapslen'] = len(messages['nomaps'])
    return messages

def batchedit_literal(fieldname="", literal=None, exact_length=None, replace_value="", zoterodata=None, remove_tag=None):
    print(f"Now batch editing '{fieldname}', value to write is '{replace_value}'. ...wait... tag to remove after edit: {str(remove_tag)}")
    messages = []
    if exact_length and len(replace_value) != exact_length or (fieldname == 'language' and re.search(r'[^a-zA-Z]', replace_value)):
        return {'messages':[f"Bad input: {replace_value}."], 'msgcolor':'background:orangered'}
    newdata = []
    for item in zoterodata:
        if remove_tag:
            index = 0
            while index < len(item['data']['tags']):
                if item['data']['tags'][index]['tag'] == remove_tag:
                    del item['data']['tags'][index]
                index += 1
                print(f"Removed tag '{remove_tag}' from item {item['key']}.")
        if fieldname in item['data']:
            if item['data'][fieldname].strip() == literal or literal == None:
                item['data'][fieldname] = replace_value
                print(f"Updated content in '{fieldname}' from '{literal}' to '{replace_value} in item {item['key']}.")
                messages.append(zoterobot.zotero_update_item(item))


        newdata.append(item)
    print(f"Zotero batch edit operation successful.")
    return {'messages': messages, 'msgcolor': 'background:limegreen', 'data': newdata}

def get_library_tags():
    return zoterobot.pyzot.tags()

def remove_tag(tag=None):
    rawitems = zoterobot.pyzot.items(tag=tag)
    print(f"Now batch editing {str(len(rawitems))}: Removing tag '{tag}'...wait...")
    if len(rawitems) > 50:
        itemlists = [rawitems[:50], rawitems[50:]]
    else:
        itemlists = [rawitems]
    for itemlist in itemlists:
        newlist = []
        for item in itemlist:
            index = 0
            while index < len(item['data']['tags']):
                if item['data']['tags'][index]['tag'] == tag:
                    del item['data']['tags'][index]
                index += 1
            newlist.append(item)
        zoterobot.pyzot.update_items(newlist)
    return {'messages': [f"Successfully batch edited {str(len(rawitems))} items: Removed tag '{tag}'."], 'msgcolor':'background:limegreen'}



def geteditbatch(tag=""):
    batchitems = zoterobot.getexport(tag=tag, save_to_file=True, file="zoteroeditbatch.json")
    if len(batchitems) == 0:
        return {'messages': [f"Error: Have got 0 items to batch edit. Repeat the operation."], 'msgcolor': 'background:orangered', 'batchitems': [], 'datafields':[]}
    datafields = set()
    fields_to_exclude = ['creators', 'relations', 'tags', 'itemType', 'key', 'accessDate', 'dateAdded']
    for item in batchitems:
        for fieldname in item['data']:
            if fieldname not in fields_to_exclude:
                datafields.add(fieldname)
    return {'messages': [f"Successfully ingested {str(len(batchitems))} records to batch edit."], 'msgcolor': 'background:limegreen', 'batchitems': batchitems, 'datafields':list(datafields)}

def lookup_doi():
    zoteromapping = botconfig.load_mapping(('zotero'))
    if not zoteromapping['mapping']['all_types']['fields']['DOI']['wbprop']:
        message = f"You have to configure a Wikibase property as mapped to the Zotero 'DOI' field for all types to use this function.</br>Do that <a href=\"./zoterofields/all_types\">here</a>."
        msgcolor = "background:orangered"
        print(message)
        return {'messages':[message], msgcolor:msgcolor}
    messages = []
    config = botconfig.load_mapping('config')
    doiwbprop = zoteromapping['mapping']['all_types']['fields']['DOI']['wbprop']
    query = """SELECT ?wbqid ?doi ?wdqid WHERE {
    ?wbqid xdp:"""+doiwbprop+""" ?doi. filter not exists {?wbqid xdp:"""+config['mapping']['prop_wikidata_entity']['wikibase']+""" ?wd.}
    bind(UCASE(?doi) as ?doi4wd)
    SERVICE <https://query.wikidata.org/sparql> {
    select ?wdqid ?doi4wd where {
    ?wdqid wdt:P356 ?doi4wd .} } } """
    bindings = xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])['results'][
        'bindings']
    message = 'Found on Wikidata: ' + str(len(bindings)) + ' DOI in bibitems with DIU still not linked to Wikidata.'
    print(message)
    messages.append(message)
    result = []
    for item in bindings:
        result.append({'wbqid':item['wbqid']['value'].replace(config['mapping']['wikibase_entity_ns'],''),
                        'doi': item['doi']['value'], 'wdqid': item['wdqid']['value'].replace('http://www.wikidata.org/entity/','')})
    count = 0
    for entry in result:
        count += 1
        statements = [{"prop_nr": config['mapping']['prop_wikidata_entity']['wikibase'], "type": "ExternalId",
                 "value": entry['wdqid'], 'action': 'replace'}]

        uploadqid = str(xwbi.itemwrite({'qid': entry['wbqid'], 'statements': statements}))
        checkurl = f"{config['mapping']['wikibase_url']}/wiki/Item:{uploadqid}#{config['mapping']['prop_wikidata_entity']['wikibase']}"
        message = f"Success [{str(count)}]: <a href=\"{checkurl}\" target=\"_blank\">{checkurl}</a>."
        print(message)
        messages.append(message)
    print('Finished DOI reconciliation.')
    return {'messages': messages, 'msgcolor':'background:limegreen'}

def lookup_issn():
    messages = []
    zoteromapping = botconfig.load_mapping(('zotero'))
    if not zoteromapping['mapping']['all_types']['fields']['ISSN']['wbprop']:
        message = f"You have to configure a Wikibase property as mapped to the Zotero 'ISSN' field for all types to use this function.</br>Do that <a href=\"./zoterofields/all_types\">here</a>."
        msgcolor = "background:orangered"
        print(message)
        return {'messages': [message], msgcolor: msgcolor}
    config = botconfig.load_mapping('config')
    issnwbprop = zoteromapping['mapping']['all_types']['fields']['ISSN']['wbprop']
    query = """SELECT ?wbqid ?issn ?issn_st ?wdqid WHERE {
        ?wbqid xp:""" + issnwbprop + """ ?issn_st.
         ?issn_st xps:""" + issnwbprop + """ ?issn.
         filter not exists {?issn_st xpq:""" + config['mapping']['prop_wikidata_entity']['wikibase'] + """ ?wd.}
        SERVICE <https://query.wikidata.org/sparql> {
    select ?wdqid ?issn where {
    ?wdqid wdt:P236 ?issn .} } } """
    bindings = \
    xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])['results'][
        'bindings']
    message = 'Found ' + str(len(bindings)) + ' issn without qualifier pointing to Wikidata to process.'
    print(message)
    messages.append(message)
    result = []
    for item in bindings:
        result.append({'wbqid': item['wbqid']['value'].replace(config['mapping']['wikibase_entity_ns'], ''),
                       'issn': item['issn']['value'],
                       'issn_st': item['issn_st']['value'],
                       'wdqid': item['wdqid']['value'].replace('http://www.wikidata.org/entity/', '')})
    count = 0
    for entry in result:
        count += 1
        statements = [{"prop_nr": issnwbprop, "type": "ExternalId",
                       "value": entry['issn'], 'action': 'replace',
                       'qualifiers':[{'prop_nr': config['mapping']['prop_wikidata_entity']['wikibase'], 'type':'ExternalId', 'value':entry['wdqid']}]}]

        uploadqid = str(xwbi.itemwrite({'qid': entry['wbqid'], 'statements': statements}))
        checkurl = f"{config['mapping']['wikibase_url']}/wiki/Item:{uploadqid}#{issnwbprop}"
        message = f"Success [{str(count)}]: <a href=\"{checkurl}\" target=\"_blank\">{checkurl}</a>."
        print(message)
        messages.append(message)
    print('Finished ISSN reconciliation.')
    return {'messages':messages, 'msgcolor':'background:limegreen'}

def link_chapters():
    zoteromapping = botconfig.load_mapping(('zotero'))
    for itemtype in ['bookSection', 'conferencePaper', 'book']:
        if not zoteromapping['mapping'][itemtype]['bibtypeqid']:
            message = f"You have to configure a Wikibase item as mapped to the Zotero '{itemtype}' item type.</br>Do that <a href=\"./zoterofields/{itemtype}\">here</a>."
            msgcolor = "background:orangered"
            print(message)
            return {'messages': [message], msgcolor: msgcolor}
    config = botconfig.load_mapping('config')
    messages = []
    query = "SELECT * WHERE { {"
    query += f"?chapter xdp:{config['mapping']['prop_itemtype']['wikibase']} xwb:{zoteromapping['mapping']['bookSection']['bibtypeqid']}. "
    query += '} union {'
    query += f"?chapter xdp:{config['mapping']['prop_itemtype']['wikibase']} xwb:{zoteromapping['mapping']['conferencePaper']['bibtypeqid']}. "+'} '
    query += f"?chapter xdp:{config['mapping']['prop_isbn_10']['wikibase']}|xdp:{config['mapping']['prop_isbn_13']['wikibase']} ?isbn. "
    query += f"?container xdp:{config['mapping']['prop_itemtype']['wikibase']} xwb:{zoteromapping['mapping']['book']['bibtypeqid']}; "
    query += f"xdp:{config['mapping']['prop_isbn_10']['wikibase']}|xdp:{config['mapping']['prop_isbn_13']['wikibase']} ?isbn. "
    query += """filter not exists {?chapter xdp:""" + config['mapping']['prop_published_in']['wikibase'] + """ ?container.} }"""
    print(query)
    bindings = \
        xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])[
            'results'][
            'bindings']
    message = 'Found ' + str(len(bindings)) + ' chapters to be linked to their containers (same ISBN).'
    print(message)
    messages.append(message)
    count = 0
    for item in bindings:
        count += 1
        statements = [{'prop_nr':config['mapping']['prop_published_in']['wikibase'], 'type':'Item', 'value':item['container']['value'].replace(config['mapping']['wikibase_entity_ns'],''), 'action':'replace'}]
        uploadqid = str(xwbi.itemwrite({'qid': item['chapter']['value'].replace(config['mapping']['wikibase_entity_ns'],''), 'statements': statements}))
        checkurl = f"{config['mapping']['wikibase_url']}/wiki/Item:{uploadqid}#{config['mapping']['prop_published_in']['wikibase']}"
        message = f"Success [{str(count)}]: <a href=\"{checkurl}\" target=\"_blank\">{checkurl}</a>."
        print(message)
        messages.append(message)
    print('Finished chapter linking.')
    return {'messages': messages, 'msgcolor': 'background:limegreen'}

def get_creators(qid=None):
    if not qid:
        return {}
    print(f"Getting existing creator statements for {qid}...")
    config = botconfig.load_mapping('config')
    query = """select ?prop (group_concat(distinct ?listpos;SEPARATOR=",") as ?list)
       
    where {bind (xwb:"""+qid+""" as ?item)
      ?prop xdp:"""+config['mapping']['prop_instanceof']['wikibase']+""" xwb:"""+config['mapping']['class_creator_role']['wikibase']+""" .      
      ?prop wikibase:claim ?prop_cl .
      ?item ?prop_cl [xpq:"""+config['mapping']['prop_series_ordinal']['wikibase']+""" ?listpos].
    } group by ?prop ?list
    """
    creators = {}
    bindings = xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])['results']['bindings']
    print('Found ' + str(len(bindings)) + ' creator roles on the existing wikibase item to process.\n')
    for item in bindings:
        creatorprop = item['prop']['value'].replace(config['mapping']['wikibase_entity_ns'],'')
        creators[creatorprop] = item['list']['value'].split(',')
    return creators

def wikibase_upload(data=[], onlynew=False):
    # iterate through zotero records and do wikibase upload
    config = botconfig.load_mapping('config')
    iso3mapping = botconfig.load_mapping('iso-639-3')
    iso1mapping = botconfig.load_mapping('iso-639-1')
    zoteromapping = botconfig.load_mapping('zotero')
    language_literals = botconfig.load_mapping('language-literals')
    messages = []
    msgcolor = 'background:limegreen'
    datalen = len(data)
    count = 0
    skipped_items = 0
    print('\nWill now upload the currently loaded dataset to Wikibase...')
    returndata = []
    for item in data:
        count += 1
        print(f"\n[{str(count)}] Now processing item '{item['links']['alternate']['href']}'...")
        qid = item['wikibase_entity'] # is False if zotero getexport function has not found an item URI in this wb entity namespace in 'extra'
        # instance of and bibItem type
        itemtype = item['data']['itemType']
        statements = [
            {'type': 'WikibaseItem', 'prop_nr': config['mapping']['prop_instanceof']['wikibase'],
             'value': config['mapping']['class_bibitem']['wikibase']},
             {'type': 'WikibaseItem', 'prop_nr': config['mapping']['prop_itemtype']['wikibase'],
              'value': zoteromapping['mapping'][itemtype]['bibtypeqid']}
        ]
        # fields with special meaning / special procedure
        ## Zotero ID and Fulltext PDF attachment(s)
        attqualis = []
        if item['meta']['numChildren'] > 0:
            children = zoterobot.getchildren(item['data']['key'])
            for child in children:
                if 'contentType' not in child['data']:  # these are notes attachments
                    continue
                if child['data']['contentType'] == "application/pdf":
                    attqualis.append(
                        {'prop_nr': config['mapping']['prop_zotero_PDF']['wikibase'], 'type': 'ExternalId',
                         'value': child['data']['key']})
                if child['data']['contentType'] == "" and child['data']['url'].startswith(config['mapping']['wikibase_entity_ns']):
                    qid = child['data']['url'].replace(config['mapping']['wikibase_entity_ns'], "")
                    print('Found link attachment: This item is linked to ' + config['mapping']['wikibase_entity_ns'] + qid)
        else:
            children = []
        if qid and onlynew == True:
            print(f"Item is already on wikibase as {qid}, skipped.")
            skipped_items += 1
            returndata.append(item)
            continue
        elif qid and not onlynew:
            existing_item = xwbi.wbi.item.get(entity_id=qid)
        statements.append({'prop_nr': config['mapping']['prop_zotero_item']['wikibase'], 'type': 'ExternalId',
                           'value': item['data']['key'],
                           'qualifiers': attqualis, 'action':'replace'})

        ## archiveLocation (special for items stemming from LexBib) TODO - delete for generic tool
        if 'archiveLocation' in item['data']:
            if item['data']['archiveLocation'].startswith('https://lexbib.elex.is/entity/'):
                statements.append({'type': 'externalid', 'prop_nr': 'P10',
                                   'value': item['data']['archiveLocation'].replace("https://lexbib.elex.is/entity/", "")})
            if item['data']['archiveLocation'].startswith('http://lexbib.elex.is/entity/'):
                statements.append({'type': 'externalid', 'prop_nr': 'P10',
                                   'value': item['data']['archiveLocation'].replace("http://lexbib.elex.is/entity/", "")})
            item['data']['archiveLocation'] = ""

        ## title to labels
        if 'title' in item['data']:
            labels = []
            for lang in config['mapping']['wikibase_label_languages']:
                labels.append({'lang': lang, 'value': item['data']['title']})

        ## language
        if 'language' in item['data']:
            langval = item['data']['language']
            languageqid = False
            if len(langval) == 2:  # should be a ISO-639-1 code
                if langval.lower() in iso1mapping['mapping']:
                    langval = iso1mapping['mapping'][langval.lower()]
                    languageqid = iso3mapping['mapping'][langval]['wbqid']
                    print('Language field: Found two-digit language code, mapped to ' +
                          iso3mapping['mapping'][langval.lower()]['enlabel'], languageqid)
            elif len(langval) == 3:  # should be a ISO-639-3 code
                if langval.lower() in iso3mapping['mapping']:
                    languageqid = iso3mapping['mapping'][langval.lower()]['wbqid']
                    print('Language field: Found three-digit language code, mapped to ' +
                          iso3mapping['mapping'][langval.lower()]['enlabel'], languageqid)
            if languageqid == False:  # Can't identify language using ISO 639-1 or 639-3
                if langval in language_literals['mapping']:
                    languageqid = iso3mapping['mapping'][language_literals['mapping'][langval]]['wbqid']
                    print('Language field: Found stored language literal, mapped to ' +
                          iso3mapping['mapping'][language_literals['mapping'][langval]]['enlabel'])
                elif len(langval) > 1:  # if there is a string that could be useful
                    print(f"Could not match the field content '{langval}' to any language.")
                    choice = None
                    choices = ["0", "1"]
                    while choice not in choices:
                        choice = input(
                            f"Do you want to store '{langval}' and associate that string to a language? '1' for yes, '0' for no.")
                    if choice == "1":
                        iso3 = None
                        while iso3 not in iso3mapping['mapping']:
                            iso3 = input(
                                f"Provide the ISO-639-3 three-letter code you want to associate to '{langval}':")
                        languageqid = iso3mapping['mapping'][iso3]['wbqid']
            if languageqid == None:  # Language item is still not on the wikibase (got 'None' from iso3mapping)
                languagewdqid = iso3mapping['mapping'][langval]['wdqid']
                print(
                    f"No item defined for this language on your Wikibase. This language is {languagewdqid} on Wikidata. I'll import that and use it from now on.")
                languageqid = zotwb_functions.import_wikidata_entity(languagewdqid,
                                                                   classqid=config['mapping']['class_language']['wikibase'])
                iso3mapping['mapping'][langval]['wbqid'] = languageqid
                botconfig.dump_mapping(iso3mapping)
            if languageqid and config['mapping']['prop_language']['wikibase']:
                statements.append(
                    {'prop_nr': config['mapping']['prop_language']['wikibase'], 'type': 'WikibaseItem',
                     'value': languageqid, 'action':'replace'})

        ## date (write parsedDate not date to prop foreseen for date in this itemtype)
        pubyear = ""
        if 'parsedDate' in item['meta'] and zoteromapping['mapping'][itemtype]['fields']['date']['wbprop']:
            year_regex = re.search(r'^[0-9]{4}', item['meta']['parsedDate'])
            month_regex = re.search(r'^[0-9]{4}\-([0-9]{2})', item['meta']['parsedDate'])
            day_regex = re.search(r'^[0-9]{4}\-[0-9]{2}\-([0-9]{2})', item['meta']['parsedDate'])

            if year_regex:
                pubyear = year_regex.group(0)
                timestr = f"+{pubyear}"
                precision = 9
                if month_regex:
                    timestr += f"-{month_regex.group(1)}"
                    precision = 10
                else:
                    timestr += "-01"
                if day_regex:
                    timestr += f"-{day_regex.group(1)}T00:00:00Z"
                    precision = 11
                else:
                    timestr += "-01T00:00:00Z"
                statements.append(
                    {'prop_nr': zoteromapping['mapping'][itemtype]['fields']['date']['wbprop'], 'type': 'Time', 'action':'replace',
                     'value': timestr, 'precision': precision})

        ## DOI
        if 'DOI' in item['data']:
            # normalize DOI
            regex = re.search(r'(10\.\d{4,}[^&]+)', item['data']['DOI'])
            if not regex:
                print('Could not get DOI by regex from DOI field content: '+item['data']['DOI'])
            else:
                item['data']['DOI'] = regex.group(1)
                print(f"Found DOI {item['data']['DOI']} in field 'DOI'.")
                        
        ## ISBN
        if 'ISBN' in item['data']:
            val = item['data']['ISBN'].replace("-", "")  # normalize ISBN
            valsearch = re.search(r'^\d+', val)  # only take the first block of digits (i.e., only the first ISBN listed)
            if valsearch:
                val = valsearch.group(0)
                if len(val) == 10:
                    statements.append(
                        {"prop_nr": config['mapping']['prop_isbn_10']['wikibase'], "type": "ExternalId", "value": val, 'action':'replace'})
                elif len(val) == 13:
                    statements.append(
                        {"prop_nr": config['mapping']['prop_isbn_13']['wikibase'], "type": "ExternalId", "value": val, 'action':'replace'})
                else:
                    print('Could not process ISBN field content: ' + item['data']['ISBN'])

        ## normalize ISSN (writing is in main field iteration below)
        if 'ISSN' in item['data']:
            if "-" not in item['data']['ISSN']:  # normalize ISSN, remove any secondary ISSN
                item['data']['ISSN'] = item['data']['ISSN'][0:4] + "-" + item['data']['ISSN'][4:9]
            else:
                item['data']['ISSN'] = item['data']['ISSN'][:9]

        ## Identifiers in EXTRA field
        if 'extra' in item['data']:
            # Qid of the Wikibase to use
            if config['mapping']['store_qid_in_extra'] and qid == False:  # if user has specified that Qid should be stored in EXTRA field (and it has not been found in a link attachment)
                qid_regex = re.search(config['mapping']['wikibase_entity_ns'] + r"(Q[0-9]+)", item['data']['extra'])
                if qid_regex:
                    qid = qid_regex.group(1)
                    print('This BibItem already exists on the wikibase as ' + qid)
                else:
                    qid = False  # a new BibItem will be created on the Wikibase
                    print('This BibItem still does not exist on the wikibase')
            # user-defined identifier patterns
            for pattern in config['mapping']['identifier_patterns']:
                try:
                    identifier_regex = re.search(rf"{pattern}", item['data']['extra'])
                    if identifier_regex:
                        print(f"Extra field: Found identifier {identifier_regex.group(0)}")
                        identifier = identifier_regex.group(1)
                        identifier_prop = config['mapping']['identifier_patterns'][pattern]
                        statements.append({'type': 'ExternalId', 'prop_nr': identifier_prop, 'value': identifier, 'action':'replace'})
                except Exception as ex:
                    print(f"Failed to do EXTRA identifier regex extraction: {str(ex)}")
                    print(f"Extra field content was: {item['data']['extra']}")

        ## special operations with Zotero tags, use-case specific
        if 'tags' in item['data']:
            for tag in item['data']['tags']:
                if tag["tag"].startswith(':type '):
                    type = tag["tag"].replace(":type ", "")
                    if type == "DictionaryDistribution":
                        statements.append({"prop_nr": "P5", "type": "item", "value": "Q12"})  # LCR distribution

        # creators
        existing_creators = get_creators(qid=qid)
        listpos = {}
        for creator in item['data']['creators']:
            if creator['creatorType'] not in listpos:
                listpos[creator['creatorType']] = 1
            else:
                listpos[creator['creatorType']] += 1
            if zoteromapping['mapping'][itemtype]['creatorTypes'][creator['creatorType']]['wbprop']:
                creatorprop = zoteromapping['mapping'][itemtype]['creatorTypes'][creator['creatorType']]['wbprop']
                if creatorprop in existing_creators:
                    if str(listpos[creator['creatorType']]) in existing_creators[creatorprop]:
                        print(f"{creator['creatorType']} ({creatorprop}) with listpos {str(listpos[creator['creatorType']])} is already present - Delete it manually on the Wikibase if you want to overwrite it.")
                        continue # do not process this creator

                # if "non-dropping-particle" in creator:
                #     creator["family"] = creator["non-dropping-particle"] + " " + creator["family"]
                # if creator["family"] == "Various":
                #     creator["given"] = "Various"
                ### TODO: non dropping particles / middle names

                creatorqualis = [{"prop_nr": config['mapping']['prop_series_ordinal']['wikibase'], "type": "string",
                                  "value": str(listpos[creator['creatorType']])}]
                if 'name' in creator:
                    creatorqualis.append(
                        {"prop_nr": config['mapping']['prop_source_literal']['wikibase'], "type": "string",
                         "value": creator['name']})
                elif 'firstName' in creator:
                    if creator['firstName'] != "":
                        creatorqualis += [
                            {"prop_nr": config['mapping']['prop_source_literal']['wikibase'], "type": "string",
                             "value": creator["firstName"] + " " + creator["lastName"]},
                            {"prop_nr": config['mapping']['prop_given_name_source_literal']['wikibase'], "type": "string",
                             "value": creator["firstName"]},
                            {"prop_nr": config['mapping']['prop_family_name_source_literal']['wikibase'], "type": "string",
                             "value": creator["lastName"]}]
                    else:
                        creatorqualis.append(
                            {"prop_nr": config['mapping']['prop_source_literal']['wikibase'], "type": "string",
                             "value": creator["lastName"]})
                else:
                    creatorqualis.append(
                        {"prop_nr": config['mapping']['prop_source_literal']['wikibase'], "type": "string",
                         "value": creator["lastName"]})
                statements.append({
                    "prop_nr": creatorprop,
                    "type": "item",
                    "value": False,  # this produces an "UNKNOWN VALUE" statement
                    "qualifiers": creatorqualis
                })

        # Other fields
        fields_processed_before = ['language', 'creators', 'ISBN', 'extra', 'abstractNote', 'date']
        for fieldname in item['data']:
            if fieldname in fields_processed_before or fieldname not in zoteromapping['mapping'][itemtype]['fields']:
                continue
            if item['data'][fieldname] == "":  # no empty strings
                continue
            if zoteromapping['mapping'][itemtype]['fields'][fieldname]['wbprop']:
                dtype = zoteromapping['mapping']['all_types']['fields'][fieldname]['dtype']
                wbprop = zoteromapping['mapping'][itemtype]['fields'][fieldname]['wbprop']
                string_like_datatypes = ['ExternalId', "String", "URL"]
                skip = False
                if dtype in string_like_datatypes: # this will just use the Zotero literal as value
                    if qid and existing_item:
                        if wbprop in existing_item.claims:
                            for claim in existing_item.claims.get(wbprop):
                                print(claim.mainsnak.datavalue['value'])
                                if claim.mainsnak.datavalue['value'] == item['data'][fieldname].strip(): # same literal already on wikibase, skip writing this (in order to preserve any qualifiers of the existing statement)
                                    skip = True
                    if not skip:
                        statements.append({
                            'prop_nr': wbprop,
                            'type': dtype,
                            'value': item['data'][fieldname].strip(),
                            'action': 'replace'
                        })
                # elif dtype == "WikibaseItem": # this will produce an 'unknown value' statement with 'source literal' qualifier
                #     statements.append({
                #         'prop_nr': zoteromapping['mapping'][itemtype]['fields'][fieldname]['wbprop'],
                #         'type': "WikibaseItem",
                #         'value': False,
                #         'action': 'replace',
                #         'qualifiers': [{'type': 'String', 'prop_nr': config['mapping']['prop_source_literal']['wikibase'],
                #                         'value': item['data'][fieldname].strip()}]
                #     })
                else:
                    print(f"Datatype '{dtype}' is currently not implemented. No statement will be written.")
                # TODO: datatype date fields other than pubdate
        # add description
        descriptions = []
        for lang in config['mapping']['wikibase_label_languages']:
            creatorsummary = item['meta']['creatorSummary'] if 'creatorSummary' in item['meta'] else ""
            descriptions.append({'lang': lang, 'value': f"{creatorsummary} {pubyear}"})

        itemdata = {'qid': qid, 'statements': statements, 'descriptions': descriptions, 'labels': labels}
        # # debug output
        # with open(f"parking/testout_{item['data']['key']}.json", 'w', encoding="utf-8") as file:
        #     json.dump({'zotero': item, 'output': itemdata}, file, indent=2)
        # do upload
        qid = xwbi.itemwrite(itemdata, clear=False)
        if qid:  # if writing was successful (if not, qid is still False)
            patch_attempt = zoterobot.patch_item(qid=qid, zotitem=item, children=children)
            if patch_attempt.startswith("Versioning Error"):
                messages.append(
                    f"Upload to Wikibase successful, but item <a href=\"{item['links']['alternate']['href']}\">{item['key']}</a> has been changed on Zotero since data ingest, and could not be patched. Update Zotero export data ingest.")
                msgcolor = 'background:orangered'
        else:
            messages.append(f"Upload unsuccessful: <a href=\"{item['links']['alternate']['href']}\">{item['key']}</a>.")
            msgcolor = 'background:orangered'
            datalen = datalen-1
        item['wikibase_entity'] = qid
        returndata.append(item)

    messages.append(f"Successfully uploaded {str(datalen-skipped_items)} (skipped {str(skipped_items)}) of {str(len(data))} items marked with the tag '{config['mapping']['zotero_export_tag']}'. These should now have the tag '{config['mapping']['zotero_on_wikibase_tag']}' instead.")
    print('\n'+str(messages))
    return {'data': returndata, 'messages': messages, 'msgcolor': msgcolor}

def export_creators(folder=""):
    print('Starting unreconciled creators export to CSV...')
    config = botconfig.load_mapping('config')
    query = """
    select ?bibItem ?creatorstatement ?propLabel ?listpos ?givenName ?lastName ?fullName 
    (?fullName as ?fullName_clusters) 
    (?fullName as ?fullName_recon_Wikidata)
    (?fullName as ?fullName_recon_Wikibase)
    where {
      ?prop xdp:"""+config['mapping']['prop_instanceof']['wikibase']+""" xwb:"""+config['mapping']['class_creator_role']['wikibase']+""";
            wikibase:directClaim ?prop_d;
            wikibase:claim ?prop_p;
            wikibase:statementProperty ?prop_ps.
        ?bibItem ?prop_p ?creatorstatement .
       ?creatorstatement ?prop_ps ?creatoritem. filter isBLANK(?creatoritem) # only unknown-value-statements
       ?creatorstatement xpq:""" + config['mapping']['prop_series_ordinal']['wikibase'] + """ ?listpos ;
                         xpq:""" + config['mapping']['prop_source_literal']['wikibase'] + """ ?fullName .
     optional {?creatorstatement xpq:""" + config['mapping']['prop_given_name_source_literal']['wikibase'] + """ ?givenName.}
     optional {?creatorstatement xpq:""" + config['mapping']['prop_family_name_source_literal']['wikibase'] + """ ?lastName .}
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
       } order by ?lastName ?givenName"""
    query_result = xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])
    data = pandas.DataFrame(columns=query_result['head']['vars'])
    for binding in query_result['results']['bindings']:
        pdrow = {}
        for key in binding:
            pdrow[key] = binding[key]['value']
        data.loc[len(data)] = pdrow
    if len(data) == 0:
        message = f"SPARQL Query for unreconciled creator statements returned 0 results."
    else:
        outfilename = f"{folder}wikibase_creators_{time.strftime('%Y%m%d_%H%M%S', time.localtime())}.csv"
        data.to_csv(outfilename, index=False)
        message = f"Successfully exported {str(len(data))} unreconciled creator statements to <code>{outfilename}</code>."
    print(message)
    return [message]

def get_recon_pd(folder=""):
    list_of_files = glob.glob(folder + '*.csv')  # * means all if need specific format then *.csv
    infile = max(list_of_files, key=os.path.getctime)
    print(f"Will get reconciled data from {infile}...")
    return {'data':pandas.read_csv(infile),'filename':infile}

def import_creators(data=None, infile=None, wikidata=False, wikibase=False, unrecon=False):
    from bots import xwb
    config = botconfig.load_mapping("config")
    messages = []
    # This expects a csv with the following colums:
    # bibItem [bibitem xwb Qid] / creatorstatement / listpos / fullName / Qid [reconciled person item xwb-qid] / givenName / lastName

    origfile = infile.replace('.csv', '.csv.copy')
    if not Path(origfile).is_file():
        shutil.copyfile(infile, origfile)
        messages.append(f"This CSV has not been processed before: Saved backup or original as <code>{origfile}</code>.")
    print('Starting reconciled creator import. This file will be processed: ' + infile)
    time.sleep(2)
    newitemjsonfile = infile.replace(".csv", "_newcreatorslog.json")
    if Path(newitemjsonfile).is_file():
        with open(newitemjsonfile, 'r', encoding='utf-8') as jsonfile:
            newcreators = json.load(jsonfile)
            messages.append('This CSV has been processed before; any new ...')
    else:
        newcreators = {}

    # select subset to process
    df = data
    rest = df.copy()
    if wikidata:
        df = df.dropna(subset=['Wikidata_Qid'])
        jobdesc = f"Wikidata-reconciled creators ({str(len(df))} creator statements)"
    elif not wikidata and wikibase:
        df = df.dropna(subset=['Wikibase_Qid'])
        jobdesc = f"Wikibase-reconciled creators ({str(len(df))} creator statements)"
    elif unrecon:
        df = df[df['Wikidata_Qid'].isnull() & df['Wikidata_Qid'].isnull()]
        jobdesc = f"Unreconciled creators ({str(len(df))} creator statements)"


    wikidatacreators = {}

    for rowindex, row in df.iterrows():
        newitem = False
        creatorwdqid = None
        creatorqid = False
        print('\nItem in CSV row [' + str(rowindex + 2) + ']:')
        bibItem = row['bibItem'].replace(config['mapping']['wikibase_entity_ns'], "")
        print('BibItem is ' + bibItem + '.')
        creatorstatement = re.search(r'statement/(Q.*)', row['creatorstatement']).group(1)
        print('CreatorStatement is ' + creatorstatement + '.')
        if 'Wikibase_Qid' in row and isinstance(row['Wikibase_Qid'], str) and re.search(r'^Q[0-9]+$',
                                                                                        str(row['Wikibase_Qid'])):
            print('Found Wikibase Qid, will use that.')
            creatorqid = row['Wikibase_Qid']
        elif 'Wikidata_Qid' in row and isinstance(row['Wikidata_Qid'], str) and re.search(r'^Q[0-9]+$',
                                                                                          str(row['Wikidata_Qid'])):
            creatorwdqid = row['Wikidata_Qid']
            if creatorwdqid not in wikidatacreators:
                # check whether this wikicreator is already on wikibase
                query = 'SELECT * WHERE { ?wikibase_entity xdp:' + config['mapping']['prop_wikidata_entity'][
                    'wikibase'] + ' "' + creatorwdqid + '" }'
                bindings = \
                xwbi.wbi_helpers.execute_sparql_query(query=query, prefix=config['mapping']['wikibase_sparql_prefixes'])[
                    'results']['bindings']
                if len(bindings) > 1:
                    print('Mapping error: More than one entity is linked to ' + creatorwdqid + ':\n' + str(bindings))
                    print('These entities should probably be merged to one.')
                    input('Press ENTER to continue and use the first in this list to process.')
                if len(bindings) > 0:
                    creatorqid = bindings[0]['wikibase_entity']['value'].replace(
                        config['mapping']['wikibase_entity_ns'], '')
                    print(
                        'Wikidata ' + creatorwdqid + ': This person was found via Sparql on Wikibase as ' + creatorqid + ', will use that.')
                if len(bindings) == 0:
                    print(f"Will create new person item for {row['fullName']}, Wikidata {creatorwdqid}")
                    creatorqid = xwbi.importitem(creatorwdqid, wbqid=False, process_claims=False,
                                                 classqid=config['mapping']['class_person']['wikibase'])
            else:
                creatorqid = wikidatacreators[creatorwdqid]
                print(
                    f"A person for {row['fullName']}, Wikidata {creatorwdqid} has been created in this run of the script: {creatorqid}")

        else:
            print('This row contains no Wikidata and no Wikibase Qid.')
            if (wikidata or wikibase) and not unrecon:
                continue # unreconciled items only when shown again to the user (after having processed the reconciled)
            if row['fullName_clusters'].strip() not in newcreators:
                print(
                    f"{row['fullName_clusters'].strip()} belongs to no known cluster. Will create a new creator item.")
                newitem = {"qid": False, "statements": [], "labels": [], "aliases": []}
                for language in config['mapping']['wikibase_label_languages']:
                    newitem['labels'].append({'lang': language, 'value': row['fullName']})
                    if isinstance(row['givenName'], str) and isinstance(row['lastName'], str):
                        newitem['aliases'].append(
                            {'lang': language, 'value': row['lastName'] + ', ' + row['givenName']})
                if isinstance(row['givenName'], str):
                	newitem['statements'].append(
                		{'type': 'String', 'prop_nr': config['mapping']['prop_pref_given_name']['wikibase'],
                		 'value': row['givenName'].strip()})
                if isinstance(row['lastName'], str):
                	newitem['statements'].append({'type': 'String',
                								  'prop_nr': config['mapping']['prop_pref_family_name'][
                									  'wikibase'], 'value': row['lastName'].strip()})
                newitemqid = xwbi.itemwrite(newitem)
                newcreators[row['fullName_clusters']] = {'creatorqid': newitemqid,
                                                         'fullName_variants': [row['fullName']]}
                xwb.setclaimvalue(creatorstatement, newitemqid, "item")
                rest = rest[
                    rest.creatorstatement != row['creatorstatement']]  # remove processed row from dataframe copy
                rest.to_csv(infile, index=False)  # save remaining rows for eventual restart of the script
                time.sleep(1)
            else:
                creatorqid = newcreators[row['fullName_clusters'].strip()]['creatorqid']
                if row['fullName'] not in newcreators[row['fullName_clusters'].strip()]['fullName_variants']:
                    newcreators[row['fullName_clusters']]['fullName_variants'].append(row['fullName'])

                print(
                    f"The full name {row['fullName_clusters']} belongs to a cluster the first member of which has been created just before as {creatorqid}. Will use that.")
            with open(newitemjsonfile, 'w', encoding='utf-8') as jsonfile:
                json.dump(newcreators, jsonfile, indent=2)

        if creatorqid and not newitem:
            # Write creator statement
            xwb.setclaimvalue(creatorstatement, creatorqid, "item")
            if creatorwdqid:
                wikidatacreators[creatorwdqid] = creatorqid
            rest = rest[rest.creatorstatement != row['creatorstatement']]  # remove processed row from dataframe copy
            rest.to_csv(infile, index=False)  # save remaining rows for eventual restart of the script
            # Compare labels, names, and write variants to Wikibase creator item
            creatoritem = xwbi.wbi.item.get(entity_id=creatorqid)
            itemchange = False
            for language in config['mapping']['wikibase_label_languages']:
                existing_preflabel = creatoritem.labels.get(language)
                existing_aliases = []
                if not existing_preflabel:
                    creatoritem.labels.set(language, row['fullName'])
                    itemchange = True
                    existing_preflabel = row['fullName']
                creatoraliases = creatoritem.aliases.get(language)
                if creatoraliases:
                    existing_aliases.append(alias.value for alias in creatoraliases)
                name_variants = [row['fullName']]
                if isinstance(row['givenName'], str) and isinstance(row['lastName'], str):
                    name_variants.append(row['lastName'] + ', ' + row['givenName'])
                for name_variant in name_variants:
                    if name_variant != existing_preflabel and name_variant not in existing_aliases:
                        print(language + ': This is a new name variant for ' + creatorqid + ': ' + name_variant)
                        creatoritem.aliases.set(language, name_variant)
                        itemchange = True
            if itemchange:
                creatoritem.write()
                print('Writing of new name variant(s) to ' + creatorqid + ' successful.')
            else:
                print(f"No new name variant found for {creatorqid}.")

            time.sleep(1)
    message = f"Successfully processed import CSV, modality was <b>{jobdesc}</b>.</br><a href=\"./openrefine\">Refresh this page</a> to see what is left for upload."
    print(message)
    messages.append(message)
    return messages

def export_anystring(profile=None, wbprop = None, restrict_class= None, split_char= None):
    print(f"Will initiate CSV export for {str(wbprop)} values, class-restr. {str(restrict_class)}, splitchar '{str(split_char)}'")
    config = botconfig.load_mapping("config")
    wikirefprop = config['mapping']['prop_wikidata_reference']['wikibase']
    query = "select ?item ?claimid ?itemLabel ?propval where { ?item "
    query+= f"xp:{wbprop} ?claimid. ?claimid xps:{wbprop} ?propval. "
    query+= "filter not exists {?claimid "+f"xpq:{wikirefprop} ?wikiref."+"}"
    if restrict_class:
        query += f"?item xdp:{config['mapping']['prop_instanceof']} xwb:{restrict_class}. "
    query += 'SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}'
    query_result = xwbi.wbi_helpers.execute_sparql_query(query=query,
                                                     prefix=config['mapping']['wikibase_sparql_prefixes'])
    columns = query_result['head']['vars']
    columns.remove('propval')
    columns.append(wbprop+'_literal')
    columns.append(wbprop+'_recon')
    data = pandas.DataFrame(columns=columns)
    for binding in query_result['results']['bindings']:
        pdrow = {}
        for key in binding:
            if key == "propval":
                continue
            pdrow[key] = binding[key]['value']
        if not split_char:
            values = [binding['propval']['value']]
        else: # split at any char in 'split_char' string
            stringval = binding['propval']['value']
            chars = split_char
            mainchar = chars[0]
            chars = chars.lstrip(mainchar)
            for char in chars:
                stringval = stringval.replace(char, mainchar)
            values = []
            for value in stringval.split(mainchar):
                values.append(value.strip())
            if len(values) > 1:
                print(f"Split '{stringval}' to {str(values)}")
        for value in values:
            pdrow[wbprop+'_literal'] = value
            pdrow[wbprop+'_recon'] = value
            data.loc[len(data)] = pdrow
    if len(data) == 0:
        message = f"SPARQL Query for {wbprop} statements, class-restr. {str(restrict_class)}, splitchar '{split_char}' returned 0 results."
    else:
        outfilename = f"profiles/{profile}/data/strings_unreconciled/{wbprop}_{time.strftime('%Y%m%d_%H%M%S', time.localtime())}.csv"
        data.to_csv(outfilename, index=False)
        message = f"Successfully exported {str(len(data))} unreconciled literals to <code>{outfilename}</code>'.</br>Query was: {wbprop} statements, class-restr. '{str(restrict_class)}', splitchar '{str(split_char)}'.</br>Open that file in Open Refine as new project."
    print(message)
    return [message]

def import_anystring(infile=None, wbprop=None, wikidata=True, wikibase=False):
    from bots import xwb
    config = botconfig.load_mapping("config")
    messages = []
    # This expects a csv with the following colums:
    # item [wikibase Qid] / claimid / {prop_nr}_Wikidata [reconciled wd Qid]

    df = pandas.read_csv(infile)

    for col in df.columns:
        print(str(col))
        colre = re.search(r"_wikidata", str(col).lower())
        if colre:
            # wbprop = colre.group(1)
            wd_reconcol = col
            print(f"Found column to get Wikidata ID: {col}. (Wikibase property {wbprop})")
    # if not wbprop:
    #     message = f"Could not find a column named 'P[0-9]+_Wikidata' in this CSV."
    #     print(message)
    #     messages.append(message)
    #     return messages
    if wikidata:
        df = df.dropna(subset=[wd_reconcol])
        jobdesc = f"Wikidata-reconciled literals, ({str(len(df))} {wbprop} statements)"
        for rowindex, row in df.iterrows():
            wbitem = row['item'].replace(config['mapping']['wikibase_entity_ns'], "")
            claimid = re.search(r'statement/(Q.*)', row['claimid']).group(1)
            print('WB qid is ' + wbitem + '. Claim ID is ' + claimid + '.')
            value = row[wd_reconcol]
            xwb.setqualifier(qid=wbitem, prop=wbprop, claimid=claimid, qualiprop=config['mapping']['prop_wikidata_reference']['wikibase'],
                             qualio=value, dtype="externalid",
                             replace=False)
    # elif wikibase:
    #     df = df.dropna(subset=['Wikibase_Qid'])
    #     jobdesc = f"Wikibase-reconciled literals ({str(len(df))} {wbprop} statements)"

    message = f"Successfully processed import CSV, modality was <b>{jobdesc}</b>."
    print('\n'+message)
    messages.append(message)
    return messages



print('zotwb functions imported.')
