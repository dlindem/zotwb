import requests, time, re, json
from bots import botconfig
from pyzotero import zotero

# load active profile
with open(f"profiles.json", 'r', encoding='utf-8') as file:
    profile = json.load(file)['last_profile']
    if profile == "":
        profile = "profile.template"

config = botconfig.load_mapping("config")

with open(f"profiles/{profile}/config_private.json", 'r', encoding="utf-8") as jsonfile:
    config_private = json.load(jsonfile)
try:
    pyzot = zotero.Zotero(int(config['mapping']['zotero_group_id']), 'group', config_private['zotero_api_key'])  # Zotero LexBib group
except Exception as ex:
    print("**** Zotero API key not configured in profile, zotero bot cannot be loaded. ****")
try:
    print(f"**** Zotero API key groups access: {str(pyzot.key_info()['access']['groups'])}. ****")
except Exception as ex:
    if 'Invalid Authorization' in str(ex):
        print('**** Zotero API key not accepted, zotero bot cannot be loaded. ****')

def getzotitem(zotitemid):
    pass


def getexport(tag=config['mapping']['zotero_export_tag'], save_to_file=False, file="zoteroexport.json"):
    rawitems = pyzot.everything(pyzot.items(tag=tag))
    exportitems = []
    for rawitem in rawitems:
        regex = re.search(rf"{config['mapping']['wikibase_entity_ns']}(Q[0-9]+)", rawitem['data']['extra'])
        if regex:
            rawitem['wikibase_entity'] = regex.group(1)
        else:
            rawitem['wikibase_entity'] = False
        exportitems.append(rawitem)
    if len(exportitems) > 0 and save_to_file:
        with open(f"profiles/{profile}/data/{file}", 'w', encoding='utf-8') as jsonfile:
            json.dump(exportitems, jsonfile, indent=2)
    return exportitems


def getchildren(zotitemid):
    children = pyzot.children(zotitemid)
    return children


def patch_item(qid=None, zotitem=None, children=[]):
    # communicate with Zotero, write Wikibase entity URI to "extra" and attach URI as link attachment
    needs_update = False
    if config['mapping']['store_qid_in_attachment']:
        attachment_present = False
        for child in children:
            if 'url' not in child['data']:
                continue
            if child['data']['url'].startswith(config['mapping']['wikibase_entity_ns']):
                if child['data']['url'].endswith(qid):
                    print('Correct link attachment already present.')
                    attachment_present = True
                else:
                    print('Fatal error: Zotero item was linked before to this other Q-id:\n'+child['data']['url'])
                    input('Press enter to continue or CTRL+C to abort.')
        if not attachment_present:
            attachment = [
                {
                    "itemType": "attachment",
                    "parentItem": zotitem['data']['key'],
                    "linkMode": "linked_url",
                    "title": config['mapping']['wikibase_name'],
                    "accessDate": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "url": config['mapping']['wikibase_entity_ns'] + qid,
                    "note": '<p>See this item as linked data at <a href="' + config['mapping']['wikibase_url'] + '/wiki/Item:' + qid + '">' + config['mapping']['wikibase_entity_ns'] + qid + '</a>',
                    "tags": [],
                    "collections": [],
                    "relations": {},
                    "contentType": "",
                    "charset": ""
                }
            ]
            r = requests.post('https://api.zotero.org/groups/' + config['mapping']['zotero_group_id'] + '/items',
                              headers={"Zotero-API-key": config_private['zotero_api_key'],
                                       "Content-Type": "application/json"}, json=attachment)
            if "200" in str(r):
                print(f"Link attachment successfully attached to Zotero item {zotitem['data']['key']}.")
                needs_update = True

    if config['mapping']['store_qid_in_extra']:
        if config['mapping']['wikibase_entity_ns']+qid in zotitem['data']['extra']:
            print('This item already has its Wikibase item URI stored in EXTRA.')
        else:
            zotitem['data']['extra'] = config['mapping']['wikibase_entity_ns'] + qid + "\n" + zotitem['data']['extra']
            print('Successfully written Wikibase item URI to EXTRA.')
            needs_update = True
    tagpresent = False
    tagpos = 0
    while tagpos < len(zotitem['data']['tags']):
        if zotitem['data']['tags'][tagpos]['tag'] == config['mapping']['zotero_on_wikibase_tag']:
            tagpresent = True
        # remove export tag
        if zotitem['data']['tags'][tagpos]['tag'] == config['mapping']['zotero_export_tag']:
            del zotitem['data']['tags'][tagpos]
            needs_update = True
        tagpos += 1
    if not tagpresent:
        zotitem['data']['tags'].append({'tag': config['mapping']['zotero_on_wikibase_tag']})
        needs_update = True
    if needs_update:
        return (zotero_update_item(zotitem))
    else:
        return f"Item {zotitem} successfully updated."

def zotero_update_item(zotitem):
    del zotitem['wikibase_entity']  # raises zotero api error if left in item
    try:
        pyzot.update_item(zotitem, last_modified=None)
        return f"Successfully updated Zotero item <code><a href=\"{zotitem['links']['alternate']['href']}\" target=\"_blank\">{zotitem['key']}</a></code>: Reload records to be exported from Zotero."
    except Exception as err:
        if "Item has been modified since specified version" in str(err):
            return f"Versioning Error (has been modified since) *** <code><a href=\"{zotitem['links']['alternate']['href']}\" target=\"_blank\">{zotitem['key']}</a></code>: Reload records to be exported from Zotero."
        else:
            return f"Unknown error updating *** <code><a href=\"{zotitem['links']['alternate']['href']}\" target=\"_blank\">{zotitem['key']}</a></code>: Reload records to be exported from Zotero."


# print('zoterobot load finished.')