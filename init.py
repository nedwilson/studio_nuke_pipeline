#!/usr/bin/python

import nuke
import re
import os
import sys
import nukescripts.ViewerProcess

# makes a file path from a selected write node if it does not exist. bound to F8

def make_dir_path():
    file = ""
    # are we being called interactively, by the user hitting Ctrl+F8?
    if nuke.thisNode() == nuke.root():
        sel = None
        try:
            sel = nuke.selectedNodes()[0]
        except:
            print "WARNING: No nodes selected."
            return
        file = nuke.filename(sel)
    else:
        # nuke.filename(nuke.thisNode()) occasionally throws a RuntimeError exception when ran from the addBeforeRender() callback.
        # catch the exception and do not proceed when the exception is thrown.
        # added by Ned, 2016-01-27
        try:
            file = nuke.filename(nuke.thisNode())
        except RuntimeError as re:
            return
        except ValueError as ve:
            return
    dir = os.path.dirname(file)
    osdir = nuke.callbacks.filenameFilter(dir)
    if not os.path.exists(osdir):
        print "INFO: Creating directory at: %s" % osdir
        try:
            os.makedirs(osdir)
        except OSError as e:
            print "ERROR: os.makedirs() threw exception: %d" % e.errno
            print "ERROR: Filename: %s" % e.filename
            print "ERROR: Error String: %s" % e.strerror


# function attempts to determine show, sequence, and shot from the nuke script name.
# does nothing if the path does not produce a match to the shot regular expression
def init_shot_env():
    if not nuke.env['gui']:
        return
    script_path = os.path.normpath(nuke.root().name())
    script_path_lst = script_path.split(os.path.sep)
    path_idx = 0
    str_show_code = None
    str_shot = ""
    try:
        str_show_code = os.environ['IH_SHOW_CODE']
    except KeyError:
        print "WARNING: IH_SHOW_CODE environment variable not defined. Proceeding without environment."
        return

    b_path_pipeline_match = False
    
    for path_component in script_path_lst:
        path_idx += 1
        if path_component == str_show_code:
            b_path_pipeline_match = True
            break
    if not b_path_pipeline_match:
    	print "WARNING: Unable to match show code with Nuke script path. Skipping init_shot_env()."
    	return
    	
    str_show = script_path_lst[path_idx - 1]
    str_seq = script_path_lst[path_idx]
    str_shot = script_path_lst[path_idx + 1]
    str_show_path = os.path.sep.join(script_path_lst[0:path_idx])
    str_seq_path = os.path.sep.join(script_path_lst[0:path_idx + 1])
    str_shot_path = os.path.sep.join(script_path_lst[0:path_idx + 2])
    
    print "INFO: Located show %s, path %s"%(str_show, str_show_path)
    print "INFO: Located sequence %s, path %s"%(str_seq, str_seq_path)
    print "INFO: Located shot %s, path %s"%(str_shot, str_shot_path)

    os.environ['SHOW'] = str_show
    os.environ['SHOW_PATH'] = str_show_path
    os.environ['SEQ'] = str_seq
    os.environ['SEQ_PATH'] = str_seq_path
    os.environ['SHOT'] = str_shot
    os.environ['SHOT_PATH'] = str_shot_path

    # add knobs to root, if they don't exist already
    root_knobs_dict = nuke.root().knobs()
    k_ih_tab = None
    k_ih_show = None
    k_ih_show_path = None
    k_ih_seq = None
    k_ih_seq_path = None
    k_ih_shot = None
    k_ih_shot_path = None
    try:
        k_ih_tab = root_knobs_dict['tab_inhouse']
    except KeyError:
        k_ih_tab = nuke.Tab_Knob('tab_inhouse', 'In-House')
        nuke.root().addKnob(k_ih_tab)
    try:
        k_ih_show = root_knobs_dict['txt_ih_show']
    except KeyError:
        k_ih_show = nuke.String_Knob('txt_ih_show', 'show')
        nuke.root().addKnob(k_ih_show)
    try:
        k_ih_show_path = root_knobs_dict['txt_ih_show_path']
    except KeyError:
        k_ih_show_path = nuke.String_Knob('txt_ih_show_path', 'show path')
        nuke.root().addKnob(k_ih_show_path)
    try:
        k_ih_seq = root_knobs_dict['txt_ih_seq']
    except KeyError:
        k_ih_seq = nuke.String_Knob('txt_ih_seq', 'sequence')
        nuke.root().addKnob(k_ih_seq)
    try:
        k_ih_seq_path = root_knobs_dict['txt_ih_seq_path']
    except KeyError:
        k_ih_seq_path = nuke.String_Knob('txt_ih_seq_path', 'sequence path')
        nuke.root().addKnob(k_ih_seq_path)
    try:
        k_ih_shot = root_knobs_dict['txt_ih_shot']
    except KeyError:
        k_ih_shot = nuke.String_Knob('txt_ih_shot', 'shot')
        nuke.root().addKnob(k_ih_shot)
    try:
        k_ih_shot_path = root_knobs_dict['txt_ih_shot_path']
    except KeyError:
        k_ih_shot_path = nuke.String_Knob('txt_ih_shot_path', 'shot path')
        nuke.root().addKnob(k_ih_shot_path)
    k_ih_show.setValue(str_show)
    k_ih_show_path.setValue(str_show_path)
    k_ih_seq.setValue(str_seq)
    k_ih_seq_path.setValue(str_seq_path)
    k_ih_shot.setValue(str_shot)
    k_ih_shot_path.setValue(str_shot_path)
	

# custom formats
nuke.load("formats.tcl")

# attempt to populate environment variables

if nuke.env['gui']:
   nuke.addOnScriptLoad(init_shot_env)

if nuke.NUKE_VERSION_MAJOR > 8:
    nuke.knobDefault("Read.mov.mov64_decode_video_levels", "Video Range")

# add callback to auto-create directory path for write nodes
nuke.addBeforeRender(make_dir_path, nodeClass = 'Write')

