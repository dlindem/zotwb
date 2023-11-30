from bots import botconfig, zotwb_functions
from flask import Flask, render_template, request
import os, re, json
from datetime import datetime

# load active profile
try:
    with open('profiles.json', 'r', encoding='utf-8') as file:
        profile = json.load(file)['last_profile']
except OSError:
    profile = "profile.template"
    with open('profiles.json', 'w', encoding='utf-8') as file:
        json.dump({'profiles_list':[],'last_profile':'profile.template'}, file)

# from flask_wtf import FlaskForm
app = Flask(__name__)

# wikibase_url = config_private.wikibase_url
# if configdata['mapping']['wikibase_url'] != wikibase_url:
#     print(f"Wikibase URL in config_private.py has changed to {wikibase_url}... Will update dependent configurations.")
#     configdata['mapping']['wikibase_url'] = wikibase_url
#     configdata = zotwb_functions.build_depconfig(configdata)

@app.route('/', methods= ['GET'])
def index_page():
    configdata = botconfig.load_mapping('config')
    zoteromapping = botconfig.load_mapping('zotero')
    config_check = zotwb_functions.check_config(configdata=configdata['mapping'])
    return render_template("index.html", profile=profile, wikibase_url=configdata['mapping']['wikibase_url'],
                           wikibase_name=configdata['mapping']['wikibase_name'],
                           zotero_name=configdata['mapping']['zotero_group_name'],
                           zotero_group_id=configdata['mapping']['zotero_group_id'],
                           zoteromapping=zoteromapping['mapping'],
                           config_check=config_check,
                           all_types = "all_types")

@app.route('/change_profile', methods= ['GET', 'POST'])
def change_profile():
    messages = []
    msgcolor = None
    with (open('profiles.json', 'r', encoding='utf-8') as file):
        profiles = json.load(file)
        print(f"Profile page: Active profiles are {str(profiles['profiles_list'])}")
        other_profiles = profiles['profiles_list']
        if profiles['last_profile'] in other_profiles:
            other_profiles.remove(profiles['last_profile'])

    if request.method == 'GET':
        return render_template("change_profile.html", other_profiles=other_profiles, profile=profiles['last_profile'],
                               messages=messages, msgcolor=msgcolor)

    elif request.method == 'POST':
        if request.form:
            for command in request.form:
                print(command)
                if command == 'create_new_profile':
                    newprofile = request.form.get(command)
                    action = zotwb_functions.create_profile(name=newprofile)
                    messages = action['messages']
                    msgcolor = action['msgcolor']
                else:
                    profile = request.form.get(command)
                    message = f"This profile will be activated: {profile}."
                    print(message)
                    with open('profiles.json', 'w', encoding='utf-8') as file:
                        json.dump({'last_profile':profile,'profiles_list':profiles['profiles_list']}, file, indent=2)
                    messages.append(message + ' Go to <a href="/">ZotWb start page</a>.')
                    msgcolor="background:limegreen"
            return render_template("change_profile.html", other_profiles=other_profiles, profile=profiles['last_profile'],
                               messages=messages, msgcolor=msgcolor)



@app.route('/zotero_export', methods= ['GET', 'POST'])
def zotero_export():
    configdata = botconfig.load_mapping('config')
    zoteromapping = botconfig.load_mapping('zotero')
    language_literals = botconfig.load_mapping('language-literals')
    with open(f"profiles/{profile}/data/zoteroexport.json", 'r', encoding='utf-8') as jsonfile:
        zoterodata = json.load(jsonfile)
        zotero_check_messages = zotwb_functions.check_export(zoterodata=zoterodata, zoteromapping=zoteromapping)
        language_check_messages = zotwb_functions.check_language(zoterodata=zoterodata)
    if request.method == 'GET':

        return render_template("zotero_export.html", wikibase_url=configdata['mapping']['wikibase_url'],
                               wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                               wikibase_name=configdata['mapping']['wikibase_name'],
                               zotero_name=configdata['mapping']['zotero_group_name'],
                               zotero_group_id=configdata['mapping']['zotero_group_id'],
                               zoterodata=zoterodata,
                               zotero_check_messages=zotero_check_messages,
                               language_check_messages=language_check_messages,
                               zotero_len=str(len(zoterodata)),
                               zotero_when=datetime.utcfromtimestamp(os.path.getmtime(
                                   f"profiles/{profile}/data/zoteroexport.json")).strftime(
            '%Y-%m-%d at %H:%M:%S UTC'),
                               export_tag=configdata['mapping']['zotero_export_tag'],
                               onwiki_tag=configdata['mapping']['zotero_on_wikibase_tag'],
                               messages=[]
                               )
    elif request.method == 'POST':
        if request.form:
            for command in request.form:
                if command == "get_export":
                    zoterodata = zotwb_functions.zoterobot.getexport(save_to_file=True)
                    messages = [f"Successfully ingested zotero data (set of {str(len(zoterodata))} records tagged '{configdata['mapping']['zotero_export_tag']}')."]
                    msgcolor = "background:limegreen"
                    zotero_check_messages = zotwb_functions.check_export(zoterodata=zoterodata,
                                                                         zoteromapping=zoteromapping)
                    language_check_messages = zotwb_functions.check_language(zoterodata=zoterodata)
                else:
                    if command == "delete_export_tag":
                        action = zotwb_functions.remove_tag(tag=configdata['mapping']['zotero_export_tag'])
                        action['data'] = []
                    elif command == "do_upload":
                        action = zotwb_functions.wikibase_upload(data=zoterodata)
                    elif command == "do_upload_new":
                        action = zotwb_functions.wikibase_upload(data=zoterodata, onlynew=True)
                    elif command == 'batchedit_empty':
                        action = zotwb_functions.batchedit_literal(fieldname='language', literal="", replace_value=request.form.get(command), exact_length=3, zoterodata=zoterodata)
                    elif command.startswith('litmap_'):
                        literal = command.replace('litmap_','')
                        action = zotwb_functions.batchedit_literal(fieldname='language', literal=literal, replace_value=request.form.get(command), exact_length=3, zoterodata=zoterodata)
                        language_literals['mapping'][literal] = request.form.get(command)
                        botconfig.dump_mapping(language_literals)
                    messages = action['messages']
                    msgcolor = action['msgcolor']
                    if 'data' in action:
                        zoterodata = action['data']
                        with open(f"profiles/{profile}/data/zoteroexport.json", 'w', encoding='utf-8') as jsonfile:
                            json.dump(zoterodata, jsonfile, indent=2)
        return render_template("zotero_export.html", wikibase_url=configdata['mapping']['wikibase_url'],
                               wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                               wikibase_name=configdata['mapping']['wikibase_name'],
                               zotero_name=configdata['mapping']['zotero_group_name'],
                               zotero_group_id=configdata['mapping']['zotero_group_id'],
                               zoterodata=zoterodata,
                               zotero_check_messages=zotero_check_messages,
                               language_check_messages=language_check_messages,
                               zotero_len=str(len(zoterodata)),
                               zotero_when=datetime.utcfromtimestamp(os.path.getmtime(
                                   f"profiles/{profile}/data/zoteroexport.json")).strftime(
                                '%Y-%m-%d at %H:%M:%S UTC'),
                               export_tag=configdata['mapping']['zotero_export_tag'],
                               onwiki_tag=configdata['mapping']['zotero_on_wikibase_tag'],
                               messages=messages, msgcolor=msgcolor
                               )




@app.route('/basic_config', methods= ['GET', 'POST'])
def basic_config():
    with open(f"profiles/{profile}/config_private.json", 'r', encoding="utf-8") as jsonfile:
        config_private = json.load(jsonfile)
        starpwd = ""
        if config_private['wb_bot_pwd']:
            while len(starpwd) < len(config_private['wb_bot_pwd']):
                starpwd += "*"
        starkey = ""
        if config_private['zotero_api_key']:
            while len(starkey) < len(config_private['zotero_api_key']):
                starkey += "*"
    configdata = botconfig.load_mapping('config')
    properties = botconfig.load_mapping('properties')
    if request.method == 'GET':
        return render_template("basic_config.html", profile=profile, wb_username=config_private['wb_bot_user'], wb_password=starpwd,
                               zotero_api_key=starkey,
                               configdata=configdata['mapping'], message = None, msgcolor = None)

    elif request.method == 'POST':
        if request.form:
            regexpattern = None
            regexprop = None
            for key in request.form:
                if key.startswith('private_'):
                    command = key.replace('private_', '')
                    config_private[command] = request.form.get(key)
                    with open(f"profiles/{profile}/config_private.json", 'w', encoding="utf-8") as jsonfile:
                        json.dump(config_private, jsonfile, indent=2)
                elif key == "wikimedia_languages":
                    configdata['mapping']['wikibase_label_languages'] = []
                    for lang in request.form.get(key).split(","):
                        configdata['mapping']['wikibase_label_languages'].append(lang.strip())
                    command = f"wikimedia languages {request.form.get(key).split(',')}"
                elif key.startswith('regexdelete_'):
                    pattern = key.replace('regexdelete_','')
                    del configdata['mapping']['identifier_patterns'][pattern]
                    command = f"delete pattern"
                elif key == 'regex_pattern':
                    regexpattern = request.form.get(key)
                elif key == 'regex_property':
                    regexprop = request.form.get(key)
                elif key.startswith('wikibase') or key.startswith('zotero'):
                    configdata['mapping'][key] = request.form.get(key)
                    if key == 'wikibase_url': # update configs that depend on the wikibase URL
                        configdata = zotwb_functions.build_depconfig(configdata)
                    command = 'Update '+key.replace('_',' ')
                elif key.startswith('prop') or key.startswith('class'):
                    command = key.replace('_', ' ')
                    if key.endswith('_redo'): # user has pressed 'import from wikidata to known wikibase entity' button
                        configitem = key.replace('_redo', '')
                        if configitem.startswith("class") and configitem != "class_ontology_class":
                            classqid = configdata['mapping']['class_ontology_class']['wikibase']
                        else:
                            classqid = None
                        zotwb_functions.import_wikidata_entity(
                            configdata['mapping'][configitem]['wikidata'], wbid=configdata['mapping'][configitem]['wikibase'], process_labels=True, process_aliases=True, process_descriptions=True, classqid=classqid, config=configdata, properties=properties)
                    elif key.endswith('_create'):  # user has pressed 'create new'
                        configitem = key.replace('_create','')
                        if configitem.startswith("class") and configitem != "class_ontology_class":
                            classqid = configdata['mapping']['class_ontology_class']['wikibase']
                        else:
                            classqid = None
                        if 'wikidata' in configdata['mapping'][configitem]:
                            newentity_id = zotwb_functions.import_wikidata_entity(configdata['mapping'][configitem]['wikidata'], wbid=False, classqid=classqid, config=configdata, properties=properties)

                        else:
                            if configitem.startswith("class"):
                                newitemdata = {'qid':False, 'labels':[{'lang':'en', 'value':configdata['mapping'][configitem]['name']}],
                                                'statements':[]}
                                if classqid:
                                    newitemdata['statements'].append({'type':'WikibaseItem','prop_nr':configdata['mapping']['prop_instanceof']['wikibase'],'value':classqid})
                                    newentity_id = zotwb_functions.xwbi.itemwrite(newitemdata)
                            elif configitem.startswith("prop"):
                                newprop = zotwb_functions.xwbi.wbi.property.new(datatype=configdata['mapping'][configitem]['type'])
                                newprop.labels.set('en', configdata['mapping'][configitem]['name'])
                                newprop.write()
                                newentity_id = newprop.id
                                properties['mapping'][newentity_id] = {
                                    "enlabel": configdata['mapping'][configitem]['name'],
                                    "type": configdata['mapping'][configitem]['type'],
                                    "wdprop": None
                                }
                                botconfig.dump_mapping(properties)
                        configdata['mapping'][configitem]['wikibase'] = newentity_id
                    else: # user has manually chosen a value
                        configdata['mapping'][key]['wikibase'] = request.form.get(key)
                        command = 'Update '+key.replace('_',' ')
                if regexpattern and regexprop:
                    configdata['mapping']['identifier_patterns'][regexpattern] = regexprop.strip()
                    command = f"Add regex pattern {regexpattern} - {regexprop}"
            message = f"Successfully performed operation: '{command}'."
            msgcolor = "background:limegreen"
        botconfig.dump_mapping(configdata)
        return render_template("basic_config.html", profile=profile, wb_username=config_private['wb_bot_user'], wb_password=star_pwd, zotero_api_key=starkey, configdata=configdata['mapping'], message=message, msgcolor=msgcolor)

@app.route('/zoterofields/<itemtype>', methods= ['GET', 'POST'])
def map_zoterofield(itemtype):
    properties = botconfig.load_mapping('properties')
    configdata = botconfig.load_mapping('config')
    zotero_types_wd = botconfig.load_mapping('zotero_types_wd')
    zoteromapping = botconfig.load_mapping('zotero')
    wikidata_suggestions = botconfig.load_mapping('zotero_fields_wd')
    for field in ['ISBN', 'extra', 'language', 'accessDate']: # these are defined in basic config, or not implemented for processing in this tool
        zoteromapping['mapping'][itemtype]['fields'].pop(field) if field in zoteromapping['mapping'][itemtype]['fields'] else True
    if request.method == 'GET':
        return render_template("zoterofields.html", itemtype=itemtype,
                           zoteromapping=zoteromapping['mapping'],
                           wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                           properties=properties['mapping'], wikidata_suggestions=wikidata_suggestions['mapping'],
                           zotero_types_wd=zotero_types_wd['mapping'],
                               messages=[])
    elif request.method == 'POST':
        if request.form:
            for key in request.form:
                messages = []
                msgcolor = "background:limegreen"
                if key.startswith('bibtypeqid'): # zotero itemtype > bibtypeqid mapping
                    if key.endswith('_redo'):  # user has pressed 'import from wikidata to known wikibase entity' button
                        fieldname = key.replace('_redo', '')
                        zotwb_functions.import_wikidata_entity(
                            zotero_types_wd['mapping'][itemtype], wbid=zoteromapping['mapping'][itemtype]['bibtypeqid'], classqid=configdata['mapping']['class_bibitem_type']['wikibase'], config=configdata, properties=properties)
                    elif key.endswith('_create'):  # user has pressed 'create new'
                        fieldname = key.replace('_create', '')
                        newentity_id = zotwb_functions.import_wikidata_entity(zotero_types_wd['mapping'][itemtype], wbid=False, classqid=configdata['mapping']['class_bibitem_type']['wikibase'], config=configdata, properties=properties)
                        zoteromapping['mapping'][itemtype]['bibtypeqid'] = newentity_id
                    else: # user has manually chosen a bibtypeqid value
                        zoteromapping['mapping'][itemtype]['bibtypeqid'] = request.form.get(key)
                    messages = [f"Successfully update BibType entity for {itemtype}."]
                else: # field or creatortype mappings
                    fieldtype = re.search(r'([a-zA-Z]+)@',key).group(1)
                    command = re.sub(r'[a-zA-Z]+@','',key)
                    if command.endswith('_redo'):  # user has pressed 'import from wikidata to known wikibase entity' button
                        fieldname = command.replace('_redo', '')
                        zotwb_functions.import_wikidata_entity(
                            properties['mapping'][zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop']]['wdprop'],
                            wbid=zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop'], config=configdata, properties=properties)
                        properties['mapping'][zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop']] = {
                            "enlabel": zoteromapping['mapping']['all_types'][fieldtype][fieldname]['name'],
                            "type": zoteromapping['mapping']['all_types'][fieldtype][fieldname]['dtype'],
                            "wdprop": properties['mapping'][zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop']]['wdprop']
                        }
                        botconfig.dump_mapping(properties)
                        messages = [f"Successfully imported {properties['mapping'][zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop']]['wdprop']} to {zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop']}."]
                    elif key.endswith('_create_from_wd'):  # user has pressed 'create new'
                        fieldname = command.replace('_create_from_wd', '')
                        newentity_id = zotwb_functions.import_wikidata_entity(
                            wikidata_suggestions[fieldname],
                            wbid=False, config=configdata, properties=properties)
                        properties['mapping'][newentity_id] = {
                            "enlabel": zoteromapping['mapping']['all_types'][fieldtype][fieldname]['name'],
                            "type": zoteromapping['mapping']['all_types'][fieldtype][fieldname]['dtype'],
                            "wdprop": wikidata_suggestions[fieldname]
                        }
                        botconfig.dump_mapping(properties)
                        zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop'] = newentity_id
                        messages = [
                            f"Successfully imported wd:{wikidata_suggestions[fieldname]} to the newly created wb:{newentity_id}."]
                        if itemtype == "all_types":
                            propagation = zotwb_functions.propagate_mapping(fieldtype=fieldtype, fieldname=fieldname,
                                                                            wbprop=newentity_id)
                            zoteromapping['mapping'] = propagation['mapping']
                            messages += propagation['messages']
                            messages.append(
                                f"...Successfully created and propagated property {newentity_id} for {fieldname} to all item types.")

                    elif command.endswith('_create'):  # user has pressed 'create new'
                        fieldname = command.replace('_create', '')
                        datatype = botconfig.datatypes_mapping[zoteromapping['mapping']['all_types'][fieldtype][fieldname]['dtype']]
                        newprop = zotwb_functions.xwbi.wbi.property.new(datatype=datatype)
                        newprop.labels.set('en', zoteromapping['mapping']['all_types'][fieldtype][fieldname]['name'])
                        newprop.descriptions.set('en', 'Property created for Zotero field '+fieldname)
                        if fieldtype == "creatorType":
                            propclass = configdata['mapping']['class_creator_role']['wikibase']
                        elif fieldtype == "fields":
                            propclass = configdata['mapping']['class_bibitem_type']['wikibase']
                        # tbd: propclss statement
                        print(str(newprop))
                        newprop.write()
                        newentity_id = newprop.id
                        properties['mapping'][newentity_id] = {
                            "enlabel": zoteromapping['mapping']['all_types'][fieldtype][fieldname]['name'],
                            "type": zoteromapping['mapping']['all_types'][fieldtype][fieldname]['dtype'],
                            "wdprop": None
                        }
                        botconfig.dump_mapping(properties)
                        zoteromapping['mapping'][itemtype][fieldtype][fieldname]['wbprop'] = newentity_id
                        messages = [
                            f"Successfully created {newentity_id} with datatype {zoteromapping['mapping']['all_types'][fieldtype][fieldname]['dtype']}."]
                        if itemtype == "all_types":
                            propagation = zotwb_functions.propagate_mapping(fieldtype=fieldtype, fieldname=fieldname, wbprop=newentity_id)
                            zoteromapping['mapping'] = propagation['mapping']
                            messages += propagation['messages']
                            messages.append(f"...Successfully created and propagated property {newentity_id} for {fieldname} to all item types.")

                    else: # user has manually entered a wikibase property ID or "False"

                        wbprop = zotwb_functions.check_prop_id(request.form.get(key))
                        zoteromapping['mapping'][itemtype][fieldtype][command]['wbprop'] = wbprop
                        if wbprop == None:
                            messages = ['Operation failed: Value bad format. Format must be e.g. "P123" or "False" or "X".']
                            msgcolor = "background:orangered"
                        elif itemtype == "all_types":
                            propagation = zotwb_functions.propagate_mapping(zoteromapping=zoteromapping['mapping'], fieldtype=fieldtype, fieldname=command, wbprop=wbprop)
                            zoteromapping['mapping'] = propagation['mapping']
                            messages += propagation['messages']
                            messages.append(f"<b>...Successfully propagated {'property '+wbprop if wbprop else 'FALSE (=ignore)'} for {command} to all item types.</b>")
                        else:
                            messages = [f"Successfully set property {wbprop} as mapped to {itemtype}-{command}."]

            botconfig.dump_mapping(zoteromapping)
            print(str(messages))
            return render_template("zoterofields.html", itemtype=itemtype,
                                   zoteromapping=zoteromapping['mapping'],
                                   wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                                   properties=properties['mapping'], wikidata_suggestions=wikidata_suggestions['mapping'],
                                   zotero_types_wd=zotero_types_wd['mapping'],
                                   messages=messages, msgcolor=msgcolor)

@app.route('/wikidata_alignment', methods= ['GET', 'POST'])
def wikidata_alignment():
    properties = botconfig.load_mapping('properties')
    configdata = botconfig.load_mapping('config')

    if request.method == 'GET':
        propcachedate = datetime.utcfromtimestamp(os.path.getmtime(f"profiles/{profile}/properties.json")).strftime(
            '%Y-%m-%d at %H:%M:%S UTC')
        return render_template("wikidata_alignment.html", wikibase_url=configdata['mapping']['wikibase_url'],
                               wikibase_name=configdata['mapping']['wikibase_name'],
                           wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                           properties=properties['mapping'],
                               propcachedate=propcachedate,
                           message=None)
    elif request.method == 'POST':
        propcachedate = datetime.utcfromtimestamp(os.path.getmtime(f"profiles/{profile}/properties.json")).strftime(
            '%Y-%m-%d at %H:%M:%S UTC')
        if request.form:
            for key in request.form:
                message = f"Operation sucessful. Operation name was '{key}'."
                msgcolor = "background:limegreen"
                if key == "update_cache":

                    zotwb_functions.rewrite_properties_mapping()
                    properties = botconfig.load_mapping('properties')
                    message = f"Properties data cache update sucessful."
            return render_template("wikidata_alignment.html", wikibase_url=configdata['mapping']['wikibase_url'],
                                   wikibase_name=configdata['mapping']['wikibase_name'],
                                   wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                                   properties=properties['mapping'],
                                   propcachedate=propcachedate,
                                   message=message, msgcolor=msgcolor)

@app.route('/openrefine_creators', methods= ['GET', 'POST'])
def openrefine_creators():
    configdata = botconfig.load_mapping('config')
    get_recon = zotwb_functions.get_recon_pd(folder=f"profiles/{profile}/data/creators_reconciled/")
    recon_df = get_recon['data']
    recon_df.set_index('creatorstatement')
    recon_wd = str(len(recon_df.dropna(subset=['Wikidata_Qid'])))
    recon_wb = str(len(recon_df.dropna(subset=['Wikibase_Qid'])))
    recon_all = str(len(recon_df))
    recon_unrecon = str(len(recon_df.loc[~recon_df.index.isin(recon_df.dropna(subset=['Wikibase_Qid', 'Wikidata_Qid']).index)]))
    if request.method == 'GET':

        return render_template("openrefine_creators.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               messages=[], msgcolor="background:limegreen", profile=profile,
                               recon_all =recon_all, recon_unrecon=recon_unrecon, recon_wd = recon_wd, recon_wb=recon_wb, filename = get_recon['filename'])
    elif request.method == 'POST':
        if request.form:
            for key in request.form:
                messages = [f"Operation sucessful. Operation name was '{key.replace('_',' ')}'."]
                msgcolor = "background:limegreen"
                if key == "export_unreconciled_creators":
                    messages = zotwb_functions.export_creators(folder=f"profiles/{profile}/data/creators_unreconciled/")
                    get_recon = zotwb_functions.get_recon_pd(folder=f"profiles/{profile}/data/creators_reconciled/")
                    recon_df = get_recon['data']
                    recon_df.set_index('creatorstatement')
                    recon_wd = str(len(recon_df.dropna(subset=['Wikidata_Qid'])))
                    recon_wb = str(len(recon_df.dropna(subset=['Wikibase_Qid'])))
                    recon_all = str(len(recon_df))
                    recon_unrecon = str(len(recon_df.loc[~recon_df.index.isin(recon_df.dropna(subset=['Wikibase_Qid', 'Wikidata_Qid']).index)]))

                if key == "import_reconciled_wikidata":
                    messages = zotwb_functions.import_creators(data=recon_df, infile=get_recon['filename'], wikidata=True)
                if key == "import_reconciled_wikibase":
                    messages = zotwb_functions.import_creators(data=recon_df, infile=get_recon['filename'], wikibase=True)
                if key == "import_unreconciled":
                    messages = zotwb_functions.import_creators(data=recon_df, infile=get_recon['filename'], unrecon=True)

        return render_template("openrefine_creators.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               messages=messages, msgcolor=msgcolor, profile=profile,
                               recon_all =recon_all, recon_unrecon=recon_unrecon, recon_wd = recon_wd, recon_wb = recon_wb, filename = get_recon['filename'])


source_prop = None
restrict_class = None
split_char = None
@app.route('/openrefine_anystring', methods= ['GET', 'POST'])
def openrefine_anystring():
    configdata = botconfig.load_mapping('config')
    # get_recon = zotwb_functions.get_recon_pd(folder=f"profiles/{profile}/data/creators_reconciled")
    # recon_df = get_recon['data']
    # recon_df.set_index('creatorstatement')
    # recon_wd = str(len(recon_df.dropna(subset=['Wikidata_Qid'])))
    # recon_wb = str(len(recon_df.dropna(subset=['Wikibase_Qid'])))
    # recon_all = str(len(recon_df))
    # recon_unrecon = str(len(recon_df.loc[~recon_df.index.isin(recon_df.dropna(subset=['Wikibase_Qid', 'Wikidata_Qid']).index)]))
    global source_prop
    global restrict_class
    global split_char
    recon_dir = f"profiles/{profile}/data/strings_reconciled/"
    recon_files = sorted(os.listdir(recon_dir), reverse=True)
    if request.method == 'GET':
        return render_template("openrefine_anystring.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               messages=[], msgcolor="background:limegreen", profile=profile, filenames = recon_files,
                               source_prop=source_prop, restrict_class=restrict_class, split_char=split_char)
    elif request.method == 'POST':
        if request.form:
            for key in request.form:
                messages = [f"Operation sucessful. Operation name was '{key.replace('_',' ')}'."]
                msgcolor = "background:limegreen"
                if key == "Specify_Source_Property":
                    source_prop = request.form.get(key).strip()
                    if not re.search('^P[0-9]+$', source_prop):
                        messages = [f"Invalid input: {source_prop}. Operation name was '{key.replace('_', ' ')}'."]
                        msgcolor = "background:orangered"
                        source_prop = None
                if source_prop and key == "Set_Class_Restriction":
                    restrict_class = request.form.get(key).strip()
                    if not re.search('^Q[0-9]+$', restrict_class):
                        messages = [f"Invalid input: {restrict_class}. Operation name was '{key.replace('_', ' ')}'."]
                        msgcolor = "background:orangered"
                        restrict_class = None
                if source_prop and key == "Set_Split_Characters":
                    split_char = request.form.get(key).strip()
                if source_prop and key == "Produce_CSV":
                    messages = zotwb_functions.export_anystring(profile=profile, wbprop = source_prop, restrict_class=restrict_class, split_char=split_char)
                if key.startswith('import_'):
                    filename=key.replace('import_','')
                    wbprop = re.search(r'^P[0-9]+', filename)
                    messages = zotwb_functions.import_anystring(infile=recon_dir+filename, wbprop=wbprop, wikidata=True)



                    # messages = zotwb_functions.export_creators()
                    # get_recon = zotwb_functions.get_recon_pd(folder=f"profiles/{profile}/data/creators_reconciled")
                    # recon_df = get_recon['data']
                    # recon_df.set_index('creatorstatement')
                    # recon_wd = str(len(recon_df.dropna(subset=['Wikidata_Qid'])))
                    # recon_wb = str(len(recon_df.dropna(subset=['Wikibase_Qid'])))
                    # recon_all = str(len(recon_df))
                    # recon_unrecon = str(len(recon_df.loc[~recon_df.index.isin(recon_df.dropna(subset=['Wikibase_Qid', 'Wikidata_Qid']).index)]))

                if key == "import_reconciled_wikidata":
                    messages = zotwb_functions.import_creators(data=recon_df, infile=get_recon['filename'], wikidata=True)
                if key == "import_reconciled_wikibase":
                    messages = zotwb_functions.import_creators(data=recon_df, infile=get_recon['filename'], wikibase=True)
                if key == "import_unreconciled":
                    messages = zotwb_functions.import_creators(data=recon_df, infile=get_recon['filename'], unrecon=True)

        return render_template("openrefine_anystring.html",
                               messages=messages, msgcolor=msgcolor, profile=profile, filenames = recon_files,
                               source_prop=source_prop, restrict_class=restrict_class, split_char=split_char)

@app.route('/little_helpers', methods= ['GET', 'POST'])
def little_helpers():
    configdata = botconfig.load_mapping('config')
    # zoteromapping = botconfig.load_mapping('zotero')
    messages = []
    batch_tag = ""
    datafields = None
    zoterodata = None
    batchlen = 0
    msgcolor = "background:limegreen"
    if request.method == 'GET':
        return render_template("little_helpers.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               zoterogrp_name=configdata['mapping']['zotero_group_name'], batch_tag=batch_tag,
                               datafields=datafields, batchlen=batchlen,
                               messages=messages, msgcolor=msgcolor)
    if request.method == "POST":
        if request.form:
            for key in request.form:
                if key == "specify_batch_tag":
                    batch_tag = request.form.get(key)
                    action = zotwb_functions.geteditbatch(tag=batch_tag)
                    datafields = action['datafields']
                    batchlen = str(len(action['batchitems']))
                elif key == "specify_remove_tag":
                    remove_tag = request.form.get(key)
                    action = zotwb_functions.remove_tag(tag=remove_tag)
                elif key.startswith("batchedit_"):
                    commandre = re.search(r'batchedit_([^_]+)_([^_]+)_(.*)', key)
                    tag_command = commandre.group(1)
                    tag = commandre.group(3)
                    fieldname = commandre.group(2)
                    with open(f"profiles/{profile}/data/zoteroeditbatch.json", 'r', encoding='utf-8') as jsonfile:
                        zoterodata = json.load(jsonfile)
                    if tag_command == "leavetag":
                        remove_tag = None
                    elif tag_command == "removetag":
                        remove_tag = tag
                    action = zotwb_functions.batchedit_literal(fieldname=fieldname, literal=None, replace_value=request.form.get(key), zoterodata=zoterodata, remove_tag=remove_tag)
                elif key == "doi_lookup":
                    action = zotwb_functions.lookup_doi()
                elif key == "issn_lookup":
                    action = zotwb_functions.lookup_issn()
                elif key == "link_chapters":
                    action = zotwb_functions.link_chapters()
                messages = action['messages']
                msgcolor = action['msgcolor']
        return render_template("little_helpers.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               zoterogrp_name=configdata['mapping']['zotero_group_name'], batch_tag=batch_tag,
                               datafields=datafields, batchlen=batchlen,
                               messages=messages, msgcolor=msgcolor)

@app.route('/wikidata_import', methods= ['GET', 'POST'])
def wikidata_import():
    configdata = botconfig.load_mapping('config')
    properties = botconfig.load_mapping('properties')
    allowed_datatypes = ['ExternalId', 'String', 'Url']
    # zoteromapping = botconfig.load_mapping('zotero')
    messages = []
    msgcolor = "background:limegreen"
    if request.method == 'GET':
        return render_template("wikidata_import.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                               instanceof=configdata['mapping']['prop_instanceof']['wikibase'],
                               messages=messages, msgcolor=msgcolor, properties=properties['mapping'], allowed_datatypes=allowed_datatypes)
    if request.method == "POST":
        if request.form:
            action = zotwb_functions.batchimport_wikidata(request.form, config=configdata, properties=properties)
            messages = action['messages']
            msgcolor = action['msgcolor']
        return render_template("wikidata_import.html", wikibase_name=configdata['mapping']['wikibase_name'],
                               wikibase_entity_ns=configdata['mapping']['wikibase_entity_ns'],
                               instanceof=configdata['mapping']['prop_instanceof']['wikibase'],
                               messages=messages, msgcolor=msgcolor, properties=properties['mapping'], allowed_datatypes=allowed_datatypes)


if __name__ == '__main__':
    app.run(debug=True)