import os
import nuke



def check_script_version():
    script_write_nd_name= nuke.root()['timeline_write_node'].getValue()
    script_write_nd=nuke.toNode(script_write_nd_name)
    render_file=script_write_nd['file'].getValue()
    xml_file=render_file.split('.')[0]+".xml"
    if os.path.exists(xml_file):
        nuke.message("WARNING! It appears as if this script version has already been submitted for review. Please version up the script before you continue working.")



nuke.addOnScriptLoad(check_script_version)
