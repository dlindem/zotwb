import json
import os
# botpath = os.path.realpath('bots')
# load active profile
with open("profiles.json", 'r', encoding='utf-8') as file:
    profile = json.load(file)['last_profile']

# check if config_private exists for this profile
if not os.path.exists(f"profiles/{profile}/config_private.json"):
    with open(f"profiles/{profile}/config_private.json", 'w', encoding='utf-8') as file:
        json.dump({"wb_bot_user": None, "wb_bot_pwd": None, "zotero_api_key": None}, file)

def load_mapping(mappingname):
    # print(f"Will load mapping: {mappingname}.json")
    with open(f"profiles/{profile}/{mappingname}.json", 'r', encoding='utf-8') as jsonfile:
        return json.load(jsonfile)

def dump_mapping(mappingjson):
    print(f"Will dump mapping: {mappingjson['filename']}")
    with open(f"profiles/{profile}/{mappingjson['filename']}", 'w', encoding='utf-8') as jsonfile:
        json.dump(mappingjson, jsonfile, indent=2)

# This maps Wikibase datatype identifiers to WikibaseIntegrator datatype identifiers
# bot functions for the datatypes greyed out are not implemented
datatypes_mapping = {
    'ExternalId': 'external-id',
    'WikibaseForm': 'wikibase-form',
    #   'GeoShape' : 'geo-shape',
    'GlobeCoordinate': 'globe-coordinate',
    'WikibaseItem': 'wikibase-item',
    'WikibaseLexeme': 'wikibase-lexeme',
    #   'Math' : 'math',
    'Monolingualtext': 'monolingualtext',
    #   'MusicalNotation' : 'musical-notation',
    'WikibaseProperty': 'wikibase-property',
    #   'Quantity' : 'quantity',
    'WikibaseSense': 'wikibase-sense',
    'String': 'string',
    #   'TabularData' : 'tabular-data',
    'Time': 'time',
    'Url': 'url'
}
