#!/usr/bin/python

import os
import nuke
import nukescripts
import glob
import subprocess
import datetime
import xml.etree.ElementTree as etree
import shutil
import xml.dom.minidom as minidom
import socket
import re
import threading
import math
import sys
import pwd
from operator import itemgetter
# from hiero.ui.nuke_bridge.nukestudio import frameServer

# def listConnectedWorkers():
#     l_workers = [worker.address for worker in frameServer.getStatus(1).workerStatus]
#     nuke.message('\n'.join(l_workers))

def quickLabel():
    sel = nuke.selectedNodes()[0]
    sel['label'].setValue(nuke.getInput('Enter Label Text'))


def getPixDir():
    script_name = nuke.root().knob('name').value()
    script_dir = os.path.dirname(script_name)
    pix = '/'.join(script_dir.split('/')[0:-1]) + "/pix/plates"
    return (pix)


def getRenderDir():
    script_name = nuke.root().knob('name').value()
    script_dir = os.path.dirname(script_name)
    pix = '/'.join(script_dir.split('/')[0:-1]) + "/pix/comp"
    return (pix)


def copyReadToShot():
    s = nuke.selectedNodes()
    for node in s:
        if node.Class() == "Read":

            file = node['file'].getValue()
            base = os.path.basename(file).split('.')[0] + "*" + os.path.splitext(file)[1]

            fileList = glob.glob(os.path.join(os.path.dirname(file), base))
            print fileList
            dest = os.path.join(getPixDir(), os.path.basename(file).split('.')[0])
            while os.path.exists(dest):
                dest += "_1"
                print dest
            os.mkdir(dest)
            print dest
            task = nuke.ProgressTask("Copying Read To Shot Tree")
            fileCount = len(fileList)

            for count, imgfile in enumerate(fileList):
                task.setMessage("copying file: %d of %d" % (count, fileCount))
                task.setProgress(int(100 * (count / float(fileCount))))
                shutil.copy(imgfile, dest)
            node['file'].setValue(os.path.join(dest, os.path.basename(file)))


def copyRenderToShot():
    s = nuke.selectedNodes()
    for node in s:
        if node.Class() == "Write":

            file = node['file'].getValue()
            base = os.path.basename(file).split('.')[0] + "*" + os.path.splitext(file)[1]

            fileList = glob.glob(os.path.join(os.path.dirname(file), base))

            dest = os.path.join(getRenderDir(), os.path.basename(file).split('.')[0])
            if not os.path.exists(dest):
                os.mkdir(dest)
            task = nuke.ProgressTask("Copying Files")

            for count, imgfile in enumerate(fileList):
                shutil.copy(imgfile, dest)
                task.setProgress(int(count / float(len(fileList)) * 100))
            node['file'].setValue(os.path.join(dest, os.path.basename(file)))
        else:
            nuke.message("Selected write nodes will copy to the delivery folder for the shot")


def setup_luts():
    nuke.root()['defaultViewerLUT'].setValue("OCIO LUTs")
    nuke.root()['OCIO_config'].setValue("custom")


def copyFiles(render_path, exr_dest_fulldir):
    task = nuke.ProgressTask("Copy Files")
    task.setMessage("Copying files")
    fileList = glob.glob(os.path.join(os.path.dirname(render_path), r'*.exr'))

    for count, exrfile in enumerate(fileList):
        shutil.copy(exrfile, exr_dest_fulldir)
        if task.isCancelled():
            nuke.executeInMainThread(nuke.message, args=("Copy Cancelled!"))
            break;
        task.setProgress(float(count) / float(len(fileList)))


show_luts = {'zmonolith': 'AlexaV3_K1S1_LogC2Video_EE_davinci3d_Profile_To_Rec709_2-4_G1_Og1_P1_Lum.cube',
             'gastown': 'AlexaV3_K1S1_LogC2Video_Rec709_EE_davinci3d.cube'}

## makeSad() tells you how many roto/paint layers you have.
def makeSad():
    count = 0
    for sel in nuke.allNodes():
        if sel.Class() in ("RotoPaint", "Roto"):
            rt = sel['curves'].rootLayer
            count += len(rt)

    nuke.message("You have used %d paint strokes for only %d frames! You should feel very proud." % (
    count, (nuke.root()['last_frame'].getValue() - nuke.root()['first_frame'].getValue())))

# returns the full name of the current user
def user_full_name(str_host_name=None):
    rval = "IH Artist"
    try:
        rval = pwd.getpwuid(os.getuid()).pw_gecos
    except:
        pass
    return rval


# overrides nukescripts.version_up(). will make a directory for versioned up write nodes
# if one does not exist.
def version_up_mkdir():
    nukescripts.version_up()
    n = nuke.selectedNodes()
    for i in n:
        _class = i.Class()
        if _class == "Write":
            _dirname = os.path.dirname(i.knob("file").value())
            if not os.path.exists(_dirname):
                print "INFO: Making directory %s." % _dirname
                os.makedirs(_dirname)


# creates a read node from a write node.

def read_from_write():
    sel = None
    file_path = ""
    start_frame = 1000
    end_frame = 1001
    node = None
    xpos = 0
    ypos = 0
    try:
        sel = nuke.selectedNodes()
    except:
        print "INFO: No nodes selected."
        return
    for nd in sel:
        if nd.Class() != "Write":
            continue
        file_path = nd.knob("file").value()
        file_type = nd.knob("file_type").value()
        read_node = nuke.createNode("Read", "file {" + file_path + "}", inpanel=True)
        if os.path.exists(os.path.dirname(file_path)):
            if not file_type == "mov":
                image_ar = sorted(glob.glob(file_path.replace('%04d', '*')))
                if (len(image_ar) == 0):
                    start_frame = int(nuke.root().knob("first_frame").value())
                    end_frame = int(nuke.root().knob("last_frame").value())
                else:
                    start_frame = int(image_ar[0].split('.')[1])
                    end_frame = int(image_ar[-1].split('.')[1])
            read_node.knob("first").setValue(start_frame)
            read_node.knob("origfirst").setValue(start_frame)
            read_node.knob("last").setValue(end_frame)
            read_node.knob("origlast").setValue(end_frame)
            read_node.knob("colorspace").setValue(re.search(r"(?:default \()?([\w\d]+)\)?",nd.knob("colorspace").value()).group(1))
            read_node.knob("raw").setValue(nd.knob("raw").value())
        xpos = nd.knob("xpos").value()
        ypos = nd.knob("ypos").value()
        read_node.knob("xpos").setValue(xpos)
        read_node.knob("ypos").setValue(ypos + 100)
        return read_node


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


# reveals the currently selected read or write node in the finder

def reveal_in_finder():
    sel = None
    try:
        sel = nuke.selectedNode()
    except:
        print "WARN: No nodes selected."
        return
    if not sel.Class() == "Write" and not sel.Class() == "Read":
        print "WARN: Please select either a read or a write node."
        return
    file_path = sel.knob("file").evaluate()
    reveal_path = os.path.dirname(file_path)
    if os.path.splitext(file_path)[1] == ".mov":
        reveal_path = file_path
    if sys.platform == "darwin":
        subprocess.Popen(["/usr/bin/open", "-R", reveal_path])
    elif sys.platform == "linux2":
        subprocess.Popen(["/usr/bin/nautilus", "--browser", reveal_path])
    else:
        subprocess.Popen(["C:/Windows/explorer.exe", reveal_path])

class TimeCode():
    # no drop frame supported yet
    fps = 24.0
    hours = 0
    minutes = 0
    seconds = 0
    frames = 0
    frameno = 0

    def __init__(self, inputvalue, inputfps=None):
        if not inputfps == None:
            self.fps = float(inputfps)
        # looks like we are a frame number
        if isinstance(inputvalue, int) or isinstance(inputvalue, float):
            floatinputvalue = float(inputvalue)
            self.hours = int(floatinputvalue / 3600 / self.fps)
            self.minutes = int((floatinputvalue - (self.hours * 3600 * self.fps)) / 60 / self.fps)
            self.seconds = int(
                (floatinputvalue - (self.hours * 3600 * self.fps) - (self.minutes * 60 * self.fps)) / self.fps)
            self.frames = int(floatinputvalue - (self.hours * 3600 * self.fps) - (self.minutes * 60 * self.fps) - (
            self.seconds * self.fps))
            self.frameno = int(floatinputvalue)
        else:
            if inputvalue == "" or inputvalue == None:
                raise ValueError("TimeCode: Error: Timecode provided to constructor may not be blank or null.")
            input_list = inputvalue.split(':')
            if len(input_list) > 4:
                raise ValueError("TimeCode: Error: Timecode provided to constructor must be of the format HH:MM:SS:FF.")
            elif len(input_list) == 4:
                if int(input_list[3]) >= self.fps or int(input_list[3]) < 0:
                    raise ValueError(
                        "TimeCode: Error: Frames provided must not be greater than FPS rate of %d or less than zero." % self.fps)
                if int(input_list[2]) > 59 or int(input_list[2]) < 0:
                    raise ValueError("TimeCode: Error: Seconds provided must not be greater than 59 or less than zero.")
                if int(input_list[1]) > 59 or int(input_list[1]) < 0:
                    raise ValueError("TimeCode: Error: Minutes provided must not be greater than 59 or less than zero.")
                if int(input_list[0]) > 23 or int(input_list[0]) < 0:
                    raise ValueError("TimeCode: Error: Hours provided must not be greater than 23 or less than zero.")
                self.hours = int(input_list[0])
                self.minutes = int(input_list[1])
                self.seconds = int(input_list[2])
                self.frames = int(input_list[3])
            elif len(input_list) == 3:
                if int(input_list[2]) >= self.fps or int(input_list[2]) < 0:
                    raise ValueError(
                        "TimeCode: Error: Frames provided must not be greater than FPS rate of %d or less than zero." % self.fps)
                if int(input_list[1]) > 59 or int(input_list[1]) < 0:
                    raise ValueError("TimeCode: Error: Seconds provided must not be greater than 59 or less than zero.")
                if int(input_list[0]) > 59 or int(input_list[0]) < 0:
                    raise ValueError("TimeCode: Error: Minutes provided must not be greater than 59 or less than zero.")
                self.minutes = int(input_list[0])
                self.seconds = int(input_list[1])
                self.frames = int(input_list[2])
            elif len(input_list) == 2:
                if int(input_list[1]) >= self.fps or int(input_list[1]) < 0:
                    raise ValueError(
                        "TimeCode: Error: Frames provided must not be greater than FPS rate of %d or less than zero." % self.fps)
                if int(input_list[0]) > 59 or int(input_list[0]) < 0:
                    raise ValueError("TimeCode: Error: Seconds provided must not be greater than 59 or less than zero.")
                self.seconds = int(input_list[0])
                self.frames = int(input_list[1])
            elif len(input_list) == 1:
                if int(input_list[0]) >= self.fps or int(input_list[0]) < 0:
                    raise ValueError(
                        "TimeCode: Error: Frames provided must not be greater than FPS rate of %d or less than zero." % self.fps)
                self.frames = int(input_list[0])
            self.frameno = (self.hours * 3600 * self.fps) + (self.minutes * 60 * self.fps) + (
            self.seconds * self.fps) + self.frames

    def __str__(self):
        return "%02d:%02d:%02d:%02d" % (self.hours, self.minutes, self.seconds, self.frames)

    def __repr__(self):
        return "TimeCode(\"%02d:%02d:%02d:%02d\", inputfps=%d)" % (
        self.hours, self.minutes, self.seconds, self.frames, self.fps)

    def frame_number(self):
        return self.frameno

    def time_code(self):
        return "%02d:%02d:%02d:%02d" % (self.hours, self.minutes, self.seconds, self.frames)

    def __add__(self, inputobject):
        inttco = None
        if isinstance(inputobject, TimeCode):
            inttco = inputobject
        else:
            inttco = TimeCode(inputobject)
        newframeno = self.frameno + inttco.frameno
        numdays = int(newframeno / (24 * 3600 * inttco.fps))
        if numdays > 0:
            newframeno = newframeno - (numdays * 24 * 3600 * inttco.fps)
        rettco = TimeCode(newframeno)
        return rettco

    def __sub__(self, inputobject):
        inttco = None
        if isinstance(inputobject, TimeCode):
            inttco = inputobject
        else:
            inttco = TimeCode(inputobject)
        newframeno = self.frameno - inttco.frameno
        numdays = abs(int(newframeno / (24 * 3600 * inttco.fps)))
        if numdays > 0:
            newframeno = newframeno + (numdays * 24 * 3600 * inttco.fps)
        if newframeno < 0:
            newframeno = newframeno + (24 * 3600 * inttco.fps)
        rettco = TimeCode(newframeno)
        return rettco


def shot_from_script():
    script_name = nuke.root().knob('name').value()
    script_base = os.path.basename(script_name)
    shot = '_'.join(script_base.split('_')[0:2])
    return (shot)


def shot_from_nuke_path(str_path):
    rval = ""
    lst_path = str_path.split('/')
    re_pattern = r'^[A-Z]{3}[0-9]{4}$'
    for path_component in lst_path:
        mo = re.search(re_pattern, path_component)
        if not mo == None:
            rval = path_component
    return rval


def cdl_file_from_nuke_path(str_path):
    rval = ""
    shot = shot_from_nuke_path(str_path)
    lst_path = str_path.split('/')
    re_pattern = r'^[A-Z]{2}[0-9]{4}$'
    path_idx = 0
    for path_component in lst_path:
        path_idx += 1
        mo = re.search(re_pattern, path_component)
        if not mo == None:
            break
    return_path_lst = lst_path[0:path_idx]
    return_path_lst.extend(['data', 'cdl', '%s.cdl' % shot])
    rval = '/'.join(return_path_lst)
    if sys.platform == "win32":
        if "/Volumes/raid_vol01" in rval:
            rval = rval.replace("/Volumes/raid_vol01", "Y:")
    return rval


def get_show_lut(str_path):
    rval = ""
    lst_path = str_path.split('/')
    re_pattern = r'^inhouse$'
    path_idx = 0
    for path_component in lst_path:
        path_idx += 1
        mo = re.search(re_pattern, path_component)
        if not mo == None:
            break
    return_path_lst = lst_path[0:path_idx]
    return_path_lst.extend([lst_path[path_idx], 'SHARED', 'lut', show_luts[lst_path[path_idx]]])
    rval = '/'.join(return_path_lst)
    if sys.platform == "win32":
        if "/Volumes/raid_vol01" in rval:
            rval = rval.replace("/Volumes/raid_vol01", "Y:")
    return rval


def get_delivery_directory(str_path):
    calc_folder = ""
    lst_path = str_path.split('/')
    re_pattern = r'^inhouse$'
    path_idx = 0
    for path_component in lst_path:
        path_idx += 1
        mo = re.search(re_pattern, path_component)
        if not mo == None:
            break
    return_path_lst = lst_path[0:path_idx]
    return_path_lst.extend([lst_path[path_idx], '..', 'from_inhouse'])
    delivery_folder = os.path.normpath(os.path.sep.join(return_path_lst))
    tday = datetime.date.today().strftime('%Y%m%d')
    matching_folders = glob.glob(os.path.join(delivery_folder, "%s_*" % tday))
    noxl = ""
    max_dir = 0
    if len(matching_folders) == 0:
        calc_folder = os.path.join(delivery_folder, "%s_1" % tday)
    else:
        for suspect_folder in matching_folders:
            csv_spreadsheet = glob.glob(os.path.join(suspect_folder, "*.csv"))
            excel_spreadsheet = glob.glob(os.path.join(suspect_folder, "*.xls*"))
            if len(excel_spreadsheet) == 0 and len(csv_spreadsheet) == 0:
                noxl = suspect_folder
            else:
                dir_number = int(os.path.basename(suspect_folder).split('_')[-1])
                if dir_number > max_dir:
                    max_dir = dir_number
        if noxl != "":
            calc_folder = noxl
        else:
            calc_folder = os.path.join(delivery_folder, "%s_%d" % (tday, max_dir + 1))
    if sys.platform == "win32":
        if "/Volumes/raid_vol01" in calc_folder:
            calc_folder = calc_folder.replace("/Volumes/raid_vol01", "Y:")
    return calc_folder


# def send_for_review(cc=True, current_version_notes=None, prev_version_number=None, prev_version_notes=None, method_hours=0.0, b_method_qt=True, b_method_dpx=False, b_method_exr=False):
#     oglist = []
# 
# 
#     for nd in nuke.selectedNodes():
#         nd.knob('selected').setValue(False)
#         oglist.append(nd)
# 
#     start_frame = nuke.root().knob('first_frame').value()
#     end_frame = nuke.root().knob('last_frame').value()
# 
#     for und in oglist:
#         created_list = []
#         write_list = []
#         render_path = ""
#         md_host_name = None
#         first_frame_tc_str = ""
#         last_frame_tc_str = ""
#         first_frame_tc = None
#         last_frame_tc = None
#         slate_frame_tc = None
# 
#         if und.Class() == "Read":
#             print "INFO: Located Read Node."
#             und.knob('selected').setValue(True)
#             render_path = und.knob('file').value()
#             start_frame = und.knob('first').value()
#             end_frame = und.knob('last').value()
#             md_host_name = und.metadata('exr/nuke/input/hostname')
#             startNode = und
#         elif und.Class() == "Write":
#             print "INFO: Located Write Node."
#             und.knob('selected').setValue(True)
#             new_read = read_from_write()
#             render_path = new_read.knob('file').value()
#             start_frame = new_read.knob('first').value()
#             end_frame = new_read.knob('last').value()
#             md_host_name = new_read.metadata('exr/nuke/input/hostname')
#             created_list.append(new_read)
#             startNode = new_read
#         else:
#             print "Please select either a Read or Write node"
#             break
#         if sys.platform == "win32":
#             if "/Volumes/raid_vol01" in render_path:
#                 render_path = render_path.replace("/Volumes/raid_vol01", "Y:")
#         # no longer uses timecode information from metadata. hardcoded from start frame.
#         # first_frame_tc_str = startNode.metadata("input/timecode", float(start_frame))
#         # last_frame_tc_str = startNode.metadata("input/timecode", float(end_frame))
#         first_frame_tc_str = str(TimeCode(start_frame))
#         last_frame_tc_str = str(TimeCode(end_frame))
#         if first_frame_tc_str == None:
#             first_frame_tc = TimeCode(start_frame)
#         else:
#             first_frame_tc = TimeCode(first_frame_tc_str)
#         slate_frame_tc = first_frame_tc - 1
#         if last_frame_tc_str == None:
#             last_frame_tc = TimeCode(end_frame) + 1
#         else:
#             last_frame_tc = TimeCode(last_frame_tc_str) + 1
#         artist_name = user_full_name(md_host_name)
# 
#         # create the panel to ask for notes
#         def_note_text = "For review"
#         path_dir_name = os.path.dirname(render_path)
#         version_int = int(path_dir_name.split("_v")[-1])
#         if version_int == 1:
#             def_note_text = "For temp, comp first look."
#         prev_version_list = []
#         for pv in range(1, version_int):
#             pv_path = "%s_v%03d" % ("_v".join(path_dir_name.split("_v")[0:-1]), pv)
#             if os.path.exists(pv_path):
#                 print "INFO: Located previous version: %s" % pv_path
#                 prev_version_list.append("v%03d" % pv)
# 
#         b_execute_overall = False
# 
#         if current_version_notes is not None:
#             cvn_txt = current_version_notes
#             pvns_txt = prev_version_number
#             pvns_notes_txt = prev_version_notes
#             exr_delivery = b_method_exr
#             dpx_delivery = b_method_dpx
#             qt_delivery = b_method_qt
#             hours = method_hours
#             b_execute_overall = True
#         else:
#             pnl = NotesPanel()
#             pnl.knobs()['cvn_'].setValue(def_note_text)
#             if len(prev_version_list) == 0:
#                 pnl.knobs()['pvns_'].setValues(['N/A'])
#                 pnl.knobs()['pvns_notes_'].setValue('N/A')
#             else:
#                 pnl.knobs()['pvns_'].setValues(prev_version_list)
#                 pnl.knobs()['pvns_notes_'].setValue('')
#             if pnl.showModalDialog():
#                 cvn_txt = pnl.knobs()['cvn_'].value()
#                 pvns_txt = pnl.knobs()['pvns_'].value()
#                 pvns_notes_txt = pnl.knobs()['pvns_notes_'].value()
#                 exr_delivery = pnl.knobs()['exr_'].value()
#                 dpx_delivery = pnl.knobs()['dpx_'].value()
#                 qt_delivery = pnl.knobs()['qt_'].value()
#                 hours = pnl.knobs()['hours_'].value()
#                 b_execute_overall = True
# 
#         if b_execute_overall:
# 
#             qtmov_filepath = '.'.join([os.path.splitext(render_path)[0].split('.')[0], "mov"])
#             xml_filepath = '.'.join([os.path.splitext(render_path)[0].split('.')[0], "xml"])
# 
#             suspected_shot = shot_from_nuke_path(render_path)
#             print "INFO: Located shot: %s" % suspected_shot
#             cdl_file_path = cdl_file_from_nuke_path(render_path)
# 
#             print "INFO: Likely CDL file for shot: %s" % cdl_file_path
# 
#             if qt_delivery:
#                 tc_nd = nuke.nodes.AddTimeCode()
#                 tc_nd.knob('startcode').setValue(str(slate_frame_tc))
#                 tc_nd.knob('metafps').setValue(False)
#                 tc_nd.knob('frame').setValue(int(start_frame - 1))
#                 tc_nd.knob('useFrame').setValue(True)
#                 created_list.append(tc_nd)
#                 tc_nd.connectInput(0,startNode)
# 
#                 slate_nd= nuke.nodes.ML_SlateOnly()
#                 slate_nd.knob('message_1').setValue(artist_name)
#                 slate_nd.knob('message').setValue(cvn_txt)
#                 slate_nd.knob('first_frame').setValue(start_frame)
#                 slate_nd.knob('last_frame').setValue(end_frame)
# 
#                 slate_nd.connectInput(0,tc_nd)
#                 created_list.append(slate_nd)
# 
#                 #create the transform nodes but dont connect them yet.
#                 xf_nd = nuke.nodes.Transform()
#                 xf_nd.knob('scale').setValue(.945)
#                 if not cc:
#                     xf_nd.knob('scale').setValue(1)
#                 xf_nd.knob('center').setValue(1078,0)
#                 xf_nd.knob('center').setValue(555,1)
#                 xf_nd.knob('filter').setValue('Lanczos4')
#                 created_list.append(xf_nd)
# 
#                 refhd_nd = nuke.nodes.Reformat()
#                 refhd_nd.knob('format').setValue('HD (.hd)')
#                 refhd_nd.knob('resize').setValue('none')
#                 refhd_nd.knob('filter').setValue('Lanczos4')
#                 created_list.append(refhd_nd)
#                 refhd_nd.connectInput(0,xf_nd)
# 
#                 crop_nd = nuke.nodes.Crop()
#                 crop_nd.knob('box').setX(0)
#                 crop_nd.knob('box').setY(138)
#                 crop_nd.knob('box').setR(1920)
#                 crop_nd.knob('box').setT(942)
#                 crop_nd.connectInput(0,refhd_nd)
#                 created_list.append(crop_nd)
# 
# 
#                 burn_nd= nuke.nodes.ML_Burnin()
#                 burn_nd.knob('message_1').setValue(artist_name)
#                 burn_nd.knob('message').setValue(cvn_txt)
#                 burn_nd.knob('first_frame').setValue(start_frame)
#                 burn_nd.knob('last_frame').setValue(end_frame)
#                 burn_nd.connectInput(0,crop_nd)
#                 created_list.append(burn_nd)
# 
# 
#     # now we go back to alexalog to do the transforms
#                 csp_nd = nuke.nodes.Colorspace()
#                 csp_nd.knob('colorspace_out').setValue("AlexaV3LogC")
#                 created_list.append(csp_nd)
#                 csp_nd.connectInput(0,slate_nd)
# 
#                 xf_nd.connectInput(0,csp_nd)
# 
# 
#                 if cc:
#                     if os.path.exists(cdl_file_path):
#                         ocio_cdl_nd = nuke.nodes.OCIOCDLTransform()
#                         ocio_cdl_nd.knob('read_from_file').setValue(True)
#                         ocio_cdl_nd.knob('file').setValue(cdl_file_path)
#                         ocio_cdl_nd.connectInput(0,burn_nd)
#                         created_list.append(ocio_cdl_nd)
#                     else:
#                         print "WARNING: Unable to locate CDL File: %s" % cdl_file_path
#                         nuke.message("Unable to locate CDL file.\nPipeline CDL File Path:\n%s" % cdl_file_path)
# 
#                     threedlut_path = get_show_lut(render_path)
#                     vfield_nd = nuke.nodes.Vectorfield()
#                     vfield_nd.knob('vfield_file').setValue(threedlut_path)
#                     vfield_nd.connectInput(0,ocio_cdl_nd)
#                     created_list.append(vfield_nd)
# 
# 
# 
#                     cspi_nd = nuke.nodes.Colorspace()
#                     cspi_nd.knob('colorspace_in').setValue("rec709")
#                     cspi_nd.connectInput(0,vfield_nd)
# 
#                     created_list.append(cspi_nd)
#                 else:
#                     cspi_nd = nuke.nodes.Colorspace()
#                     cspi_nd.knob('colorspace_in').setValue("AlexaV3LogC")
#                     cspi_nd.connectInput(0,burn_nd)
# 
#                     created_list.append(cspi_nd)
# 
# 
# 
# 
# 
#                 wri_nd = nuke.nodes.Write()
#                 wri_nd.connectInput(0,cspi_nd)
#                 wri_nd.knob('file').setValue(qtmov_filepath)
#                 wri_nd.knob('file_type').setValue('mov')
#                 wri_nd.knob('colorspace').setValue('rec709')
#                 wri_nd.knob('codec').setValue('AVdn')
#                 if nuke.NUKE_VERSION_MAJOR <= 8:
#                     wri_nd.knob('settings').setValue(
#                         '000000000000000000000000000001d27365616e000000010000000100000000000001be76696465000000010000000f00000000000000227370746c0000000100000000000000004156646e00000000002000000200000000207470726c000000010000000000000000000000000017fae100000000000000246472617400000001000000000000000000000000000000530000010000000100000000156d70736f00000001000000000000000000000000186d66726100000001000000000000000000000000000000187073667200000001000000000000000000000000000000156266726100000001000000000000000000000000166d70657300000001000000000000000000000000002868617264000000010000000000000000000000000000000000000000000000000000000000000016656e647300000001000000000000000000000000001663666c67000000010000000000000000004400000018636d66720000000100000000000000004156494400000014636c757400000001000000000000000000000038636465630000000100000000000000004156494400000001000000020000000000000010000000030000000000000000000000000000001c766572730000000100000000000000000003001c00010000')
#                     wri_nd.knob('Flatten').setValue(False)
#                     wri_nd.knob('ycbcr_matrix_type').setValue('Rec 709')
#                     wri_nd.knob('pixel_format').setValue(4)
#                     wri_nd.knob('write_nclc').setValue(False)
#                     wri_nd.knob('write_gamma').setValue(False)
#                     wri_nd.knob('writeTimeCode').setValue(True)
#                 else:
#                     # MUST use mov64 encoder on linux
#                     if sys.platform == "linux2":
#                         wri_nd.knob('mov64_format').setValue('mov (QuickTime / MOV)')
#                         wri_nd.knob('mov64_codec').setValue('AVdn')
#                         wri_nd.knob('mov64_dnxhd_codec_profile').setValue('DNxHD 422 8-bit 145Mbit')
#                         wri_nd.knob('mov64_fps').setValue(24)
#                         wri_nd.knob('mov64_write_timecode').setValue(True)
#                         wri_nd.knob('mov64_advanced').setValue(True)
#                         wri_nd.knob('mov64_dnxhd_encode_video_range').setValue("Video Range")
#                         wri_nd.knob('mov64_bitrate').setValue(20000)
#                         wri_nd.knob('mov64_bitrate_tolerance').setValue(40000000)
#                         wri_nd.knob('mov64_quality_min').setValue(2)
#                         wri_nd.knob('mov64_quality_max').setValue(31)
#                         wri_nd.knob('mov64_gop_size').setValue(12)
#                         wri_nd.knob('mov64_b_frames').setValue(0)
#                         wri_nd.knob('mov64_write_nclc').setValue(False)
#                     else:
#                         wri_nd.knob('meta_codec').setValue('AVdn')
#                         wri_nd.knob('meta_encoder').setValue('mov32')
#                         wri_nd.knob('mov32_codec').setValue('AVdn')
#                         wri_nd.knob('mov32_fps').setValue(24)
#                         wri_nd.knob('mov32_settings').setValue(
#                             '000000000000000000000000000001d27365616e000000010000000100000000000001be76696465000000010000000f00000000000000227370746c0000000100000000000000004156646e000000000020000003ff000000207470726c000000010000000000000000000000000017f9db00000000000000246472617400000001000000000000000000000000000000530000010000000100000000156d70736f00000001000000000000000000000000186d66726100000001000000000000000000000000000000187073667200000001000000000000000000000000000000156266726100000001000000000000000000000000166d70657300000001000000000000000000000000002868617264000000010000000000000000000000000000000000000000000000000000000000000016656e647300000001000000000000000000000000001663666c67000000010000000000000000004400000018636d66720000000100000000000000004156494400000014636c757400000001000000000000000000000038636465630000000100000000000000004156494400000001000000020000000000000010000000030000000000000000000000000000001c766572730000000100000000000000000003001c00010000')
#                         wri_nd.knob('mov32_flatten').setValue(False)
#                         wri_nd.knob('mov32_ycbcr_matrix_type').setValue('Rec 709')
#                         wri_nd.knob('mov32_pixel_format').setValue(4)
#                         wri_nd.knob('mov32_write_nclc').setValue(False)
#                         wri_nd.knob('mov32_write_gamma').setValue(False)
#                         wri_nd.knob('mov32_write_timecode').setValue(True)
#                         wri_nd.knob('mov64_codec').setValue('AVdn')
#                         wri_nd.knob('mov64_dnxhd_codec_profile').setValue('DNxHD 422 8-bit 145Mbit')
#                         wri_nd.knob('mov64_fps').setValue(24)
#                         wri_nd.knob('mov64_write_timecode').setValue(True)
#                         wri_nd.knob('mov64_advanced').setValue(True)
#                         wri_nd.knob('mov64_bitrate').setValue(20000)
#                         wri_nd.knob('mov64_bitrate_tolerance').setValue(40000000)
#                         wri_nd.knob('mov64_quality_min').setValue(2)
#                         wri_nd.knob('mov64_quality_max').setValue(31)
#                         wri_nd.knob('mov64_gop_size').setValue(12)
#                         wri_nd.knob('mov64_b_frames').setValue(0)
#                         wri_nd.knob('mov64_write_nclc').setValue(False)
# 
#                 print "INFO: Path for rendered Quicktime: %s" % qtmov_filepath
#                 created_list.append(wri_nd)
#                 write_list.append(wri_nd)
# 
#                 wri_vfx_nd = nuke.nodes.Write()
#                 wri_vfx_nd.connectInput(0,cspi_nd)
#                 wri_vfx_nd.knob('file').setValue(qtmov_filepath.replace(".mov", "_vfx.mov"))
#                 wri_vfx_nd.knob('file_type').setValue('mov')
#                 wri_vfx_nd.knob('colorspace').setValue('rec709')
#                 wri_vfx_nd.knob('codec').setValue('jpeg')
#                 if nuke.NUKE_VERSION_MAJOR <= 8:
#                     wri_vfx_nd.knob('settings').setValue(
#                         '0000000000000000000000000000019a7365616e0000000100000001000000000000018676696465000000010000000e00000000000000227370746c0000000100000000000000006a70656700000000001800000400000000207470726c000000010000000000000000000000000017f9db00000000000000246472617400000001000000000000000000000000000000530000010000000100000000156d70736f00000001000000000000000000000000186d66726100000001000000000000000000000000000000187073667200000001000000000000000000000000000000156266726100000001000000000000000000000000166d70657300000001000000000000000000000000002868617264000000010000000000000000000000000000000000000000000000000000000000000016656e647300000001000000000000000000000000001663666c67000000010000000000000000004400000018636d66720000000100000000000000006170706c00000014636c75740000000100000000000000000000001c766572730000000100000000000000000003001c00010000')
#                     wri_vfx_nd.knob('Flatten').setValue(False)
#                     wri_vfx_nd.knob('ycbcr_matrix_type').setValue('Rec 709')
#                     wri_vfx_nd.knob('pixel_format').setValue(4)
#                     wri_vfx_nd.knob('write_nclc').setValue(False)
#                     wri_vfx_nd.knob('write_gamma').setValue(False)
#                     wri_vfx_nd.knob('writeTimeCode').setValue(True)
#                     wri_vfx_nd.knob('quality').setValue('High')
#                 else:
#                     if sys.platform == "linux2":
#                         wri_vfx_nd.knob('mov64_format').setValue('mov (QuickTime / MOV)')
#                         wri_vfx_nd.knob('mov64_codec').setValue('ap4h')
#                         wri_vfx_nd.knob('mov64_fps').setValue(24)
#                         wri_vfx_nd.knob('mov64_write_timecode').setValue(True)
#                         wri_vfx_nd.knob('mov64_advanced').setValue(True)
#                         wri_vfx_nd.knob('mov64_bitrate').setValue(20000)
#                         wri_vfx_nd.knob('mov64_bitrate_tolerance').setValue(40000000)
#                         wri_vfx_nd.knob('mov64_quality_min').setValue(2)
#                         wri_vfx_nd.knob('mov64_quality_max').setValue(31)
#                         wri_vfx_nd.knob('mov64_gop_size').setValue(12)
#                         wri_vfx_nd.knob('mov64_b_frames').setValue(0)
#                         wri_vfx_nd.knob('mov64_write_nclc').setValue(False)
#                     else:
#                         wri_vfx_nd.knob('meta_codec').setValue('jpeg')
#                         wri_vfx_nd.knob('meta_encoder').setValue('mov32')
#                         wri_vfx_nd.knob('mov32_quality').setValue('High')
#                         wri_vfx_nd.knob('mov32_codec').setValue('jpeg')
#                         wri_vfx_nd.knob('mov32_fps').setValue(24)
#                         wri_vfx_nd.knob('mov32_settings').setValue(
#                             '0000000000000000000000000000019a7365616e0000000100000001000000000000018676696465000000010000000e00000000000000227370746c0000000100000000000000006a70656700000000001800000400000000207470726c000000010000000000000000000000000017f9db00000000000000246472617400000001000000000000000000000000000000530000010000000100000000156d70736f00000001000000000000000000000000186d66726100000001000000000000000000000000000000187073667200000001000000000000000000000000000000156266726100000001000000000000000000000000166d70657300000001000000000000000000000000002868617264000000010000000000000000000000000000000000000000000000000000000000000016656e647300000001000000000000000000000000001663666c67000000010000000000000000004400000018636d66720000000100000000000000006170706c00000014636c75740000000100000000000000000000001c766572730000000100000000000000000003001c00010000')
#                         wri_vfx_nd.knob('mov32_flatten').setValue(False)
#                         wri_vfx_nd.knob('mov32_ycbcr_matrix_type').setValue('Rec 709')
#                         wri_vfx_nd.knob('mov32_pixel_format').setValue(4)
#                         wri_vfx_nd.knob('mov32_write_nclc').setValue(False)
#                         wri_vfx_nd.knob('mov32_write_gamma').setValue(False)
#                         wri_vfx_nd.knob('mov32_write_timecode').setValue(True)
# 
# 
#                 created_list.append(wri_vfx_nd)
#                 write_list.append(wri_vfx_nd)
# 
# 
#             # create additional nodes for exr
#             exr_filepath = ""
# 
#             if True:
# 
#                 exr_write_nd = nuke.nodes.Write()
#                 created_list.append(exr_write_nd)
# 
# 
# 
# 
# 
#                 #reformat_exr_nd = nuke.nodes.Reformat()
#                 #reformat_exr_nd.knob('format').setValue("Alexa 3K Open Gate (.a3kog)")
# 
#                 #reformat_exr_nd.connectInput(0, slate_nd_exr)
#                 #created_list.append(reformat_exr_nd)
# 
#                 # exr file path
#                 exr_filepath = '.'.join([os.path.splitext(render_path)[0].split('.')[0], '%04d', 'exr'])
#                 exr_write_nd.knob('colorspace').setValue('linear')
#                 exr_write_nd.knob('file').setValue(exr_filepath)
# 
#                 exr_write_nd.connectInput(0, slate_nd)
#                 # are we working with an exr sequence? if so, only render the slate
#                 src_ext = os.path.splitext(render_path)[-1]
#                 if src_ext == '.exr':
#                     nuke.execute(exr_write_nd, start_frame - 1, start_frame - 1)
#                 else:
#                     write_list.append(exr_write_nd)
# 
#             # execute the mofo
# 
# 
#             nuke.execute(wri_nd, start_frame - 1, end_frame)
# 
#             xf_nd['disable'].setValue(True)
#             crop_nd['disable'].setValue(True)
#             refhd_nd['disable'].setValue(True)
# 
#             nuke.execute(wri_vfx_nd, start_frame - 1, end_frame)
# 
#             # destination file names
# 
#             dest_hires_root_dir = os.path.splitext(os.path.basename(qtmov_filepath))[0]
#             dest_dpx_dir = os.path.join(dest_hires_root_dir, "2276x1474_AlexaV3LogC_DPX")
#             dest_exr_dir = os.path.join(dest_hires_root_dir, "2156x1110_Linear_EXR")
# 
#             # generate the xml file
#             new_submission = etree.Element('DailiesSubmission')
#             sht_se = etree.SubElement(new_submission, 'Shot')
#             sht_se.text = suspected_shot
# 
#             fname_se = etree.SubElement(new_submission, 'FileName')
#             fname_se.text = os.path.basename(qtmov_filepath)
#             if dpx_delivery:
#                 dpx_fname_se = etree.SubElement(new_submission, 'DPXFileName')
#                 dpx_fname_se.text = os.path.basename(dpx_filepath)
#             if exr_delivery:
#                 exr_fname_se = etree.SubElement(new_submission, 'EXRFileName')
#                 exr_fname_se.text = os.path.basename(exr_filepath)
#             sframe_se = etree.SubElement(new_submission, 'StartFrame')
#             sframe_se.text = "%d" % (start_frame - 1)
#             eframe_se = etree.SubElement(new_submission, 'EndFrame')
#             eframe_se.text = "%d" % end_frame
#             stc_se = etree.SubElement(new_submission, 'StartTimeCode')
#             stc_se.text = "%s" % slate_frame_tc
#             etc_se = etree.SubElement(new_submission, 'EndTimeCode')
#             etc_se.text = "%s" % last_frame_tc
#             artist_se = etree.SubElement(new_submission, 'Artist')
#             artist_se.text = artist_name
#             notes_se = etree.SubElement(new_submission, 'SubmissionNotes')
#             notes_se.text = cvn_txt
#             pv_se = etree.SubElement(new_submission, 'PreviousVersion')
#             pv_se.text = pvns_txt
#             pvn_se = etree.SubElement(new_submission, 'PreviousVersionNotes')
#             pvn_se.text = pvns_notes_txt
# 
#             hours_se = etree.SubElement(new_submission,'Hours')
#             hours_se.text = str(hours)
# 
#             # write out xml file to disk
# 
#             prettyxml = minidom.parseString(etree.tostring(new_submission)).toprettyxml(indent="  ")
#             xml_ds = open(xml_filepath, 'w')
#             xml_ds.write(prettyxml)
#             xml_ds.close()
# 
#             # delete extra created nodes
#             for nd_del in created_list:
#                 nuke.delete(nd_del)
#             del created_list[:]
#             task = nuke.ProgressTask("Delivering Files")
# 
#             dest_delivery = get_delivery_directory(render_path)
#             print "INFO: Copying Quicktime and XML file to: %s" % dest_delivery
#             dest_delivery_avid = os.path.join(dest_delivery, "_avid")
#             dest_delivery_vfx = os.path.join(dest_delivery, "_vfx")
#             if not os.path.exists(dest_delivery_avid):
#                 os.makedirs(dest_delivery_avid)
#             if not os.path.exists(dest_delivery_vfx):
#                 os.makedirs(dest_delivery_vfx)
#             if qt_delivery:
#                 qt_avid_filepath=os.path.join(dest_delivery_avid, os.path.basename(qtmov_filepath))
#                 qt_vfx_filepath=os.path.join(dest_delivery_vfx, os.path.basename(qtmov_filepath.replace('.mov', "_vfx.mov")))
#                 if os.path.exists(qt_avid_filepath):
#                     os.remove(qt_avid_filepath)
#                 if os.path.exists(qt_vfx_filepath):
#                     os.remove(qt_vfx_filepath)
#                 task.setMessage('Copying Avid Quicktime...')
#                 task.setProgress(1)
#                 try:
#                     os.link(qtmov_filepath, qt_avid_filepath)
#                 except:
#                     nuke.critical(str(sys.exc_info()[1]))
#                     break
#                 task.setMessage('Copying VFX Quicktime...')
#                 task.setProgress(51)
#                 try:
#                     os.link(qtmov_filepath.replace(".mov", "_vfx.mov"), qt_vfx_filepath)
#                 except:
#                     nuke.critical(str(sys.exc_info()[1]))
#                     break
#                 task.setProgress(100)
# 
#             shutil.copyfile(xml_filepath, os.path.join(dest_delivery, os.path.basename(xml_filepath)))
# 
#             # Copy DPX frames, if necessary
#             if dpx_delivery:
#                 dpx_dest_fulldir = os.path.join(dest_delivery, dest_dpx_dir)
#                 if not os.path.exists(dpx_dest_fulldir):
#                     os.makedirs(dpx_dest_fulldir)
#                 print "INFO: Copying DPX Frames to: %s" % dpx_dest_fulldir
#                 dpxfiles = glob.glob(os.path.join(os.path.dirname(render_path), r'*.dpx'))
#                 task.setMessage("DPX frames")
#                 for count, dpxfile in enumerate(dpxfiles):
#                     shutil.copy(dpxfile, dpx_dest_fulldir)
# 
#                     task.setProgress(int((float(count) / float(len(dpxfiles)) * 100)))
# 
#             # Copy EXR frames, if necessary
#             if exr_delivery:
#                 exr_dest_fulldir = os.path.join(dest_delivery, dest_exr_dir)
#                 if os.path.exists(exr_dest_fulldir):
#                     shutil.rmtree(exr_dest_fulldir)
#                     os.makedirs(exr_dest_fulldir)
#                 else:
#                     os.makedirs(exr_dest_fulldir)
#                 print "INFO: Copying EXR Frames to: %s" % exr_dest_fulldir
#                 task.setMessage("EXR frames")
#                 # threading.Thread(None,copyFiles,args=(render_path,exr_dest_fulldir)).start()
#                 exrfiles = glob.glob(os.path.join(os.path.dirname(render_path), r'*.exr'))
#                 for count, exrfile in enumerate(exrfiles):
#                     try:
#                         os.link(exrfile, os.path.join(exr_dest_fulldir,os.path.basename(exrfile)))
#                         task.setProgress(int((float(count) / float(len(exrfiles)) * 100)))
#                     except:
#                         nuke.critical(str(sys.exc_info()[1]))
#                         break
# 
#         # delete the progress bar object
#         del task
# 
#         for all_nd in nuke.allNodes():
#             if all_nd in oglist:
#                 all_nd.knob('selected').setValue(True)
#             else:
#                 all_nd.knob('selected').setValue(False)


import subprocess


# function to execute package code from within a separate thread

def package_execute_threaded(s_nuke_script_path):
    # hard coded Nuke executable path, because we're classy like that
    progress_bar = nuke.ProgressTask("Packaging Script")
    progress_bar.setMessage("Initializing...")
    progress_bar.setProgress(0)

    
    s_nuke_exe_path = nuke.env['ExecutablePath']  # "/Applications/Nuke9.0v4/Nuke9.0v4.app/Contents/MacOS/Nuke9.0v4"
    s_pyscript = "/Volumes/monovfx/inhouse/zmonolith/SHARED/lib/nuke/nuke_pipeline/package_script.py"

    s_cmd = "%s -i -V 2 -t %s %s" % (s_nuke_exe_path, s_pyscript, s_nuke_script_path)
    s_err_ar = []
    f_progress = 0.0
    print "INFO: Beginning: %s" % s_cmd
    proc = subprocess.Popen(s_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    while proc.poll() is None:
        try:
            s_out = proc.stdout.readline()
            print s_out.rstrip()
            s_err_ar.append(s_out.rstrip())
            if not s_out.find("INFO: copying file") == -1:
                s_line_ar = s_out.split(" ")
                (f_frame_cur, f_frame_tot, f_source_cur, f_source_tot) = (
                float(s_line_ar[3]), float(s_line_ar[5]), float(s_line_ar[8]), float(s_line_ar[10]))
                f_progress = ((f_frame_cur / f_frame_tot) * (1 / f_source_tot)) + ((f_source_cur - 1) / f_source_tot)
                progress_bar.setMessage("Copying: %s" % s_line_ar[-1])
                progress_bar.setProgress(int(f_progress * 100))
        except IOError:
            print "IOError Caught!"
            var = traceback.format_exc()
            print var
    if proc.returncode != 0:
        s_errmsg = ""
        s_err = '\n'.join(s_err_ar)
        if s_err.find("FOUNDRY LICENSE ERROR REPORT") != -1:
            s_errmsg = "Unable to obtain a license for Nuke! Package execution fails, will not proceed!"
        else:
            s_errmsg = "An unknown error has occurred. Please check the STDERR log above for more information."
        nuke.critical(s_errmsg)
    else:
        print "INFO: Successfully completed script packaging."


# add this one to menu.py
def menu_package_script():
    nuke.scriptSave()
    s_script_name = "%s" % nuke.scriptName()
    threading.Thread(target=package_execute_threaded, args=[s_script_name]).start()


def hsvToRGB(h, s, v):
    """Convert HSV color space to RGB color space
    @param h: Hue
    @param s: Saturation
    @param v: Value
    return (r, g, b)
    """
    hi = math.floor(h / 60.0) % 6
    f = (h / 60.0) - math.floor(h / 60.0)
    p = v * (1.0 - s)
    q = v * (1.0 - (f * s))
    t = v * (1.0 - ((1.0 - f) * s))
    return {
        0: (v, t, p),
        1: (q, v, p),
        2: (p, v, t),
        3: (p, q, v),
        4: (t, p, v),
        5: (v, p, q),
    }[hi]


def rgbToHSV(r, g, b):
    """Convert RGB color space to HSV color space
    @param r: Red
    @param g: Green
    @param b: Blue
    return (h, s, v)
    """
    maxc = max(r, g, b)
    minc = min(r, g, b)
    colorMap = {
        id(r): 'r',
        id(g): 'g',
        id(b): 'b'
    }
    if colorMap[id(maxc)] == colorMap[id(minc)]:
        h = 0
    elif colorMap[id(maxc)] == 'r':
        h = 60.0 * ((g - b) / (maxc - minc)) % 360.0
    elif colorMap[id(maxc)] == 'g':
        h = 60.0 * ((b - r) / (maxc - minc)) + 120.0
    elif colorMap[id(maxc)] == 'b':
        h = 60.0 * ((r - g) / (maxc - minc)) + 240.0

    v = maxc
    if maxc == 0.0:
        s = 0.0
    else:
        s = 1.0 - (minc / maxc)
    return (h, s, v)


def backdropColorOCD():
    nd_ar = []

    for nd in nuke.allNodes("BackdropNode"):
        nd_ar.append({'ypos': nd.knob("ypos").value(), 'node': nd})
    nd_ar_sorted = sorted(nd_ar, key=itemgetter('ypos'))
    hue_inc = 1.0 / (float(len(nd_ar_sorted)))
    hue_start = 0.0

    for nd in nd_ar_sorted:
        (a, b, c) = hsvToRGB((hue_start * 255), .5, .7)
        hx = "%02x%02x%02x%02x" % (a * 255, b * 255, c * 255, 255)
        nd['node'].knob("tile_color").setValue(int(hx, 16))
        # nd['node'].knob("note_font_size").setValue(100)
        hue_start += hue_inc
        
def build_cc_nodes():
    show_root = "/Volumes/monovfx/inhouse/zmonolith"
    if sys.platform == "win32":
        show_root = "Y:\\zmonolith"
    show_lut = os.path.join(show_root, "SHARED", "lut", "AlexaV3_K1S1_LogC2Video_EE_davinci3d_Profile_To_Rec709_2-4_G1_Og1_P1_Lum.cube")
    shot_re = re.compile(r'[A-Za-z]{3}[0-9]{4}')
    seq_re = re.compile(r'[A-Za-z]{3}')
    active_node = nuke.selectedNode()
    if active_node == None:
        nuke.critical("Please select either a Read or a Write node.")
        return
    if not active_node.Class() in ['Read', 'Write']:
        nuke.critical("Please select either a Read or a Write node.")
        return
    io_path = active_node.knob('file').value()
    
    c_shot_match = shot_re.search(io_path)
    c_shot = None
    if c_shot_match:
        c_shot = c_shot_match.group(0)
    else:
        nuke.critical("Can not find a valid shot name in file path for selected node.")
        return
    c_seq = seq_re.search(c_shot).group(0)
    cdl_path = os.path.join(show_root, c_seq, c_shot, "data", "cdl", "%s.cdl"%c_shot)
    if not os.path.exists(cdl_path):
        nuke.critical("Can not find a CDL file at %s."%cdl_path)
        return

    # create cdl nodes
    nd_cs1 = nuke.nodes.OCIOColorSpace()
    nd_cs1.knob("out_colorspace").setValue("AlexaV3LogC")
    nd_cs1.connectInput(0, active_node)
    nd_cdl = nuke.nodes.OCIOCDLTransform()
    nd_cdl.knob("read_from_file").setValue(True)
    nd_cdl.knob("file").setValue("%s"%cdl_path)
    nd_cdl.connectInput(0, nd_cs1)
    nd_lut = nuke.nodes.OCIOFileTransform()
    nd_lut.knob("file").setValue("%s"%show_lut)
    nd_lut.connectInput(0, nd_cdl)
    nd_cs2 = nuke.nodes.OCIOColorSpace()
    nd_cs2.knob("in_colorspace").setValue("rec709")
    nd_cs2.connectInput(0, nd_lut)

