#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
import gc
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio, GObject
import os
import subprocess
import time
import logging
import xmi
import datetime
import sys
import pprint
from pathlib import Path
import tempfile
import re
import argparse
import threading
import multiprocessing

running_folder = Path(Path(__file__).parent)

UI_FILE = running_folder / "ui/xmission.glade"

__version__ = "1.0.0"
__author__ = 'Philip Young'
__license__ = "GPL"

# Create the Logger
logger = logging.getLogger(__name__)
#logger.setLevel()
logger_formatter = logging.Formatter('%(levelname)s :: %(funcName)s :: %(message)s')
# Log to stderr
ch = logging.StreamHandler()
ch.setFormatter(logger_formatter)
logger.addHandler(ch)

class XMIssion:
    def __init__(self, loglevel=logging.WARNING, filename=None):

        self.loglevel = loglevel
        self.tempfolder = None
        self.overwrite = False
        self.make_folder = False
        self.translate = 'mimetype'
        self.unnum = True
        self.codepage = 'cp1140'
        self.force = False
        self.translate = True
        self.binary = False
        self.modify = True
        logger.setLevel(self.loglevel)
        if filename is not None:
            logger.debug("XMIssion running with the following options: filename: {}".format(filename))
        else:
            logger.debug("XMIssion running")

        self.handlers = {
        "onDestroy": Gtk.main_quit,
        "open_xmi": self.open_file,
        "xmission_quit" : Gtk.main_quit,
        "show_xmi_message" : self.show_message,
        "close_xmi_message" : self.close_message,
        "file_properties" : self.show_info,
        "file_properties_close" : self.close_info,
        "file_info_clicked_cb" : self.file_info,
        "double_click_item" : self.double_click,
        "single_click_item" : self.single_click,
        "extract_files" : self.extract,
        "extract_overwrite_toggled" : self.set_overwrite,
        #"extract_create_folder_toggled" : self.set_folder,
        "right_click_menu" : self.right_click,
        "right_click_open" : self.right_click_open,
        "right_click_info" : self.right_click_info,
        "close_member_info" : self.close_file_info,
        "close_tape_file_info" : self.close_file_info,
        "right_click_extract" : self.right_click_extract,
        "unnum_toggled" : self.toggle_unnum,
        "modify_toggled" : self.toggle_modify,
        "change_radio_convert": self.change_radio_convert,
        "go_up" : self.go_home,
        "go_home" : self.go_home,
        "open_json" : self.open_json,
        "open_about" : self.show_about,
        "close_about" : self.close_about,
        #"loading_cancel_button_clicked_cb" : self.loading_cancelled
        "extract_window_quit_activate_cb" : Gtk.main_quit,
        "extract_window_show_activate_cb" : self.show_extract_folder,
        "extract_window_show_quit_activate_cb" : self.show_extract_folder_quit,
        "extract_window_close_activate_cb" : self.close_extract_window,
        }

        self.file_data = ""
        self.file_name = filename
        self.has_message = False
        self.selected_folder = None
        self.XMI = xmi.XMIT(loglevel=self.loglevel,
                unnum=self.unnum, encoding=self.codepage,
                force_convert=self.force, binary=self.binary
                )

        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE.resolve()))
        self.builder.connect_signals(self.handlers)
        self.main_window = self.builder.get_object('main window')
        self.err_window = self.builder.get_object('error message')
        self.right_click_menu = self.builder.get_object('popup_menu')
        self.main_window.connect('delete-event', lambda x,y: Gtk.main_quit())
        self.statusbar = self.builder.get_object("status_bar")
        self.context_id = self.statusbar.get_context_id("status")
        self.file_store_treeview = self.builder.get_object("file_list_store")

        self.msg_button = self.builder.get_object('xmi_view_message')


        self.make_codecs_submenu()
        self.main_window.show_all()

        if filename is not None:
            logger.debug("Reading file: {}".format(filename))
            with open(filename, 'rb') as x:
                self.file_data = x.read()
            logger.debug("Total bytes: {}".format(len(self.file_data)))
            self.loading_file()

        #self.show_files()

    def update_status(self, message):
        self.statusbar.pop(self.context_id)
        self.statusbar.push(self.context_id, message)

    def make_codecs_submenu(self):
        codecs = list(dict.fromkeys(sorted(self.XMI.get_codecs(), key=self.natural_key)))
        logger.debug("Current Codec: {} Total supported EBCDIC code pages: {}".format(self.XMI.get_codec(), len(codecs)))

        codec_menu = Gtk.Menu()
        for codec in codecs:
            codec_menu_item = Gtk.MenuItem(label=codec)

            if codec == self.XMI.get_codec():
                label = codec_menu_item.get_children()[0]
                codec = "<b>{}</b>".format(codec)
                label.set_markup(codec)
            codec_menu_item.connect("activate", self.change_codec, codec)
            codec_menu.append(codec_menu_item)
        self.builder.get_object("ebcdic_encoding").set_submenu(codec_menu)

    def change_codec(self, button, name):
        if "<b>" in name:
            name = name[3:-4]
        #self.XMI.set_codec(name)
        self.codepage = name
        self.update_status("Codepage changed to: {}".format(name))
        self.refresh_file()

    def set_unnum(self, button):
        if "<b>" in name:
            name = name[3:-4]
        #self.XMI.set_codec(name)
        self.codepage = name
        self.update_status("Codepage changed to: {}".format(name))
        self.refresh_file()

    def make_temp_folder(self):
        if not self.tempfolder:
            temp_prefix = GLib.get_user_cache_dir()
            logger.debug("Cache folder: {}".format(temp_prefix))
            self.tempfolder = tempfile.TemporaryDirectory(prefix="{}/".format(temp_prefix))
        return self.tempfolder.name

    def open_json(self, button):
        file_location = "{}/{}".format(self.make_temp_folder() , "file.json")
        json_exec = self.mime_exec("text/plain")
        json_app_name = self.mime_app_name("text/plain")
        logger.debug("Opening {} with {} ({})".format("JSON", json_exec, json_app_name))
        giotype = Gio.content_type_from_mime_type("text/plain")
        #default_app = Gio.app_info_get_all_for_type("text/plain")[0]
        logger.debug("Extracting temp file to: {}".format(file_location))
        json = self.XMI.get_xmit_json()

        with open(file_location, 'w') as json_temp_file:
                json_temp_file.write(json)

        member_gfile = Gio.File.new_for_path(file_location)
        uri = member_gfile.get_uri()
        timestamp = Gtk.get_current_event_time()
        Gtk.show_uri_on_window(None, uri, timestamp)

        #open_app = default_app.launch([member_gfile], None)


    # def show_files(self):
    #     logger.debug("Generating Files list")

    #     img = Gtk.IconTheme.get_default().load_icon("folder", 32, Gtk.IconLookupFlags.FORCE_SIZE)


    #     for i in range(0,10):
    #         self.file_store_treeview.append([img, '@FILE561.{:>03}'.format(i), '960 bytes', 'Text', '10/23/21 11:26:54', 'SGOLOB', Gtk.IconSize.LARGE_TOOLBAR])

    def show_message(self, button):
        logger.debug("Displaying XMI message")
        #self.XMI.pprint()
        self.message_window = self.builder.get_object('xmi_message_window')
        self.message_text_buffer = self.builder.get_object('xmi_message_buffer')
        self.message_text_buffer.set_text(self.XMI.get_message(), len(self.XMI.get_message()))
        self.message_window.set_transient_for(self.main_window)
        self.message_window.show()
        self.message_window.run()

    def close_message(self, button):
        logger.debug("Closing Message Window")
        self.message_window.hide()

    def show_info(self, button):
        logger.debug("Displaying XMI Info")
        #self.XMI.pprint()
        if self.XMI.has_xmi():
            self.info_window = self.builder.get_object('xmi_info_window')
        else:
            self.info_window = self.builder.get_object('tape_info_window')
        self.info_window.set_transient_for(self.main_window)
        self.info_window.show()
        self.info_window.run()

    def file_info(self, button):
        selected = self.get_selected()
        logger.debug("Selected: {}".format(selected))
        if len(selected) == 0:
            self.show_info(None)
        else:
            self.right_click_info(None)

    def close_info(self, button):
        logger.debug("Closing Info Window")
        self.info_window.hide()

    def show_about(self, button):
        logger.debug("Displaying About window")
        self.about_window = self.builder.get_object('about_xmission')
        self.about_window.set_transient_for(self.main_window)
        self.about_window.show()
        self.about_window.run()

    def close_about(self, button, w):
        logger.debug("Closing About Window")
        self.about_window.hide()

    def single_click(self, treeview):
        objects_selected = 0
        size = 0

        msg = "{} objects ({})".format(
            self.XMI.get_num_files(),
            self.sizeof_fmt(self.XMI.get_total_size())
            )
        selected = ", {total} selected ({size})"

        for files in self.get_selected():

            filename = files[0]
            pds = files[1]

            if not pds:
                logger.debug("{} Selected".format(filename))
                if self.XMI.is_sequential(filename):
                    size += self.XMI.get_dataset_size(filename)
                objects_selected += 1
            else:
                logger.debug("{} Selected ({})".format(filename, pds))
                size += self.XMI.get_member_size(pds, filename.split('.')[0])
                objects_selected += 1

        if objects_selected > 0:
            self.update_status(msg + selected.format(total=objects_selected,size=self.sizeof_fmt(size)))
        else:
            self.update_status(msg)

    def show_extract_folder(self, button):
        if not self.selected_folder:
            return
        logger.debug("Opening extract folder {}".format(self.selected_folder))
        member_gfile = Gio.File.new_for_path(self.selected_folder)
        uri = member_gfile.get_uri()
        timestamp = Gtk.get_current_event_time()
        Gtk.show_uri_on_window(None, uri, timestamp)
        self.close_extract_window(None)

    def show_extract_folder_quit(self, button):
        self.show_extract_folder(None)
        Gtk.main_quit()


    def close_extract_window(self, button):
        logger.debug("Closing extract window")
        self.extract_window.hide()



    def double_click(self, widget, row, col):
        model = widget.get_model()
        logger.debug("Opening: {} Type: {}".format(model[row][1], model[row][3]))
        self.update_location(location="/{}/".format(model[row][1]))
        filename = model[row][6]
        parent = model[row][7]

        if not parent and self.XMI.is_pds(filename):
            logger.debug("Opening PDS {}".format(filename))
            self.file_store_treeview.clear()
            for m in self.XMI.get_members(filename):
                info = self.XMI.get_member_info(filename, m)
                self.list_store_append(m, info, parent=filename)
        else:
            self.extract_and_open(filename, parent)


    def list_store_append(self, filename, info, parent=None):
        info_log = "member: {} ".format(filename)
        for i in info:
            info_log += " | {}: {}".format(i, info[i])
        logger.debug(info_log)
        img = self.mime_icon(info['mimetype'])
        desc = self.mime_desc(info['mimetype'])
        if 'modified' in info and info['modified']:
            file_last_modified = datetime.datetime.fromisoformat(info['modified']).strftime("%-d %B %Y, %H:%S")
        else:
            file_last_modified = ''
        if 'owner' in info:
            owner = info['owner']
        else:
            owner = ''

        if info['extension']:
            file_name_w_ext = "{}{}".format(filename, info['extension'])
        else:
            file_name_w_ext = filename

        if "alias" in info:
            file_name_w_ext += "*"

        self.file_store_treeview.append([img,  # file_icon
                                        file_name_w_ext,  # file_name
                                        self.sizeof_fmt(info['size']),  # file_size
                                        desc,  # file_type
                                        file_last_modified,  # file_modify
                                        owner,  # file_owner
                                        filename,  # actual_name
                                        parent])  # parent_name


    def mime_desc(self,mime_type):
        giotype = Gio.content_type_from_mime_type(mime_type)
        if 'directory' in mime_type:
            giotype = Gio.content_type_from_mime_type("folder")
        return Gio.content_type_get_description(giotype)

    def mime_icon(self, mime_type, size=32):
        if 'directory' in mime_type:
            mime_type = "folder"
        gicon = Gio.content_type_get_icon(mime_type)
        gmimetypes = gicon.get_names()
        try:
            img = Gtk.IconTheme.get_default().load_icon(gmimetypes[0], size, Gtk.IconLookupFlags.FORCE_SIZE)
        except gi.repository.GLib.Error:
            img = Gtk.IconTheme.get_default().load_icon(gmimetypes[1], size, Gtk.IconLookupFlags.FORCE_SIZE)
        return img

    def mime_exec(self, mime_type):
        giotype = Gio.content_type_from_mime_type(mime_type)
        app_infos = Gio.app_info_get_all_for_type(giotype)
        return app_infos[0].get_executable()

    def mime_app_name(self, mime_type):
        giotype = Gio.content_type_from_mime_type(mime_type)
        app_infos = Gio.app_info_get_all_for_type(giotype)
        return app_infos[0].get_name()

    def open_file(self, button):
        logger.debug("Open File Button Pressed")
        dialog = Gtk.FileChooserDialog(
            title="Please choose a file",
            action=Gtk.FileChooserAction.OPEN,
        )

        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            "Select",
            Gtk.ResponseType.OK)

        file_filter = Gtk.FileFilter()
        file_filter.set_name("XMI Files")
        file_filter.add_pattern("*.xmi")
        file_filter.add_pattern("*.bin")
        file_filter.add_pattern("*.xmit")
        file_filter.add_pattern("*.XMI")
        file_filter.add_pattern("*.XMIT")
        dialog.add_filter(file_filter)
        file_filter = Gtk.FileFilter()
        file_filter.set_name("AWS/HET Virtual Tape")
        file_filter.add_pattern("*.aws")
        file_filter.add_pattern("*.het")
        file_filter.add_pattern("*.AWS")
        file_filter.add_pattern("*.HET")
        dialog.add_filter(file_filter)
        file_filter = Gtk.FileFilter()
        file_filter.set_name("All Files")
        file_filter.add_pattern("*")
        dialog.add_filter(file_filter)
        # not only local files can be selected in the file selector
        dialog.set_local_only(False)
        # dialog always on top of the textview window
        dialog.set_modal(True)
        # connect the dialog with the callback function open_response_cb()
        dialog.connect("response", self.open_response)
        # show the dialog
        dialog.show()

    def change_radio_convert(self, button):
        convert_widget = self._resolve_radio(self.builder.get_object("convert_guess"))
        convert_type = button.get_label()
        logger.debug("Convert type changed to: {}".format(convert_type))
        unnum = self.builder.get_object("unnum")
        print(button.get_active())
        if not button.get_active():
            return
        print("HOW ARE WE HERE?", button.get_label())

        if convert_type == "Convert":
            self.translate = True
            self.force = False
            self.binary = False
            unnum.set_sensitive(True)
            self.update_status("Converting based on mimetype")
            self.builder.get_object("ebcdic_encoding").set_sensitive(True)
            self.refresh_file()
        elif convert_type == "Do not convert":
            self.translate = False
            self.binary = True
            self.force = False
            self.unnum = False
            self.update_status("File conversion disabled")
            unnum.set_sensitive(False)
            self.builder.get_object("ebcdic_encoding").set_sensitive(False)
            # No need to refresh, unnum will do it
            if unnum.get_active():
                unnum.set_active(False)
        elif convert_type == "Convert all to UTF-8":
            self.binary = False
            self.force = True
            self.translate = False
            unnum.set_sensitive(True)
            self.update_status("Converting all file to UTF-8")
            self.builder.get_object("ebcdic_encoding").set_sensitive(True)
            self.refresh_file()

    def extract(self, button):
        selected_items = self.get_selected()
        extract_radio = self.builder.get_object("extract_selected")
        if len(selected_items) == 0:
            extract_radio.set_sensitive(False)
            #self.builder.get_object("extract_create_dir").set_sensitive(False)
        else:
            extract_radio.set_sensitive(True)
            extract_radio.set_active(True)
            #self.builder.get_object("extract_create_dir").set_sensitive(True)

        dialog = self.builder.get_object("dialog_extract")
        dialog.set_transient_for(self.main_window)

        dialog.set_local_only(False)
        dialog.set_modal(True)
        response_id = dialog.run()
        if response_id == Gtk.ResponseType.OK:
            selected_folder = dialog.get_filename()
            logger.debug("Extract to folder name: {}".format(selected_folder))
        elif response_id == Gtk.ResponseType.CANCEL:
            logger.debug("File open cancelled")
            dialog.hide()
            return
        else:
            logger.debug("File open error?")
            dialog.hide()
            return

        files_or_all = self._resolve_radio(self.builder.get_object("extract_all")).get_name()
        dialog.hide()
        self.selected_folder = selected_folder
        self.XMI.set_overwrite(self.overwrite)
        self.XMI.set_quiet()
        self.XMI.set_output_folder(selected_folder)

        extract_window = self.builder.get_object("extract_window")
        self.builder.get_object("extract_window_from_label").set_label("Extracting files from \"{}\"".format(Path(self.file_name).name))
        extract_text = "Extracting {} to {}"
        pulse_bar = self.builder.get_object("extract_window_progress_bar")

        button_quit = self.builder.get_object("extract_window_quit")
        button_show = self.builder.get_object("extract_window_show")
        button_show_quit = self.builder.get_object("extract_window_show_quit")
        button_close = self.builder.get_object("extract_window_close")
        button_quit.set_sensitive(False)
        button_show.set_sensitive(False)
        button_show_quit.set_sensitive(False)
        button_close.set_sensitive(False)
        extract_to_label = self.builder.get_object("extract_window_to_label")
        extract_to_label.set_label("")
        pulse_bar.set_fraction(0.0)

        if files_or_all == "extract_all":
            logger.debug("Extracting all contents to {}".format(selected_folder))
            extract_text = extract_text.format(Path(self.file_name).name, selected_folder)

            extract_to_label.set_label(extract_text)
            pulse_bar.set_fraction(0.1)
            extract_window.show_all()

            self.XMI.unload_files()
            pulse_bar.set_fraction(1.0)
            extract_to_label.set_label("Extraction completed successfully")
            button_quit.set_sensitive(True)
            button_show.set_sensitive(True)
            button_show_quit.set_sensitive(True)
            button_close.set_sensitive(True)
            extract_window.show_all()

            self.update_status("{} files extracted ({})".format(
                self.XMI.get_num_files(),
                self.sizeof_fmt(self.XMI.get_total_size())
                )
            )

        else:
            total = 0
            total_selected = len(selected_items)
            total_files = 1

            extract_window.show_all()

            for selected in selected_items:
                filename = selected[0]
                parent = selected[1]

                extract_text = extract_text.format(filename, selected_folder)
                extract_to_label.set_label(extract_text)
                pulse_bar.set_fraction(total_selected/total_files)
                extract_window.show_all()
                if not parent:
                    self.XMI.unload_pds(filename)
                    num_extracted = len(self.XMI.get_members(filename)) if len(self.XMI.get_members(filename)) > 0 else 1
                    extracted = "{} files extracted ({})".format(total, self.sizeof_fmt(self.XMI.get_dataset_size(filename)))
                    total += num_extracted
                    logger.debug(extracted)
                    total_files += 1
                else:
                    total += 1
                    self.XMI.unload_file(parent, filename)
                    plural = 'files' if total > 1 else 'file'
                    extracted = "{} {} extracted ({})".format(total, plural, self.sizeof_fmt(self.XMI.get_member_size(parent, filename)))
                    logger.debug(extracted)
                    total_files += 1

            self.update_status(extracted)
            extract_to_label.set_label("Extraction completed successfully")
            button_quit.set_sensitive(True)
            button_show.set_sensitive(True)
            button_show_quit.set_sensitive(True)
            button_close.set_sensitive(True)
            extract_window.show_all()
        self.extract_window = extract_window

    def extract_and_open(self, member, pds):
        logger.debug("Opening {}".format(member))
        if pds:
            info = self.XMI.get_member_info(pds, member)
            file_data = self.XMI.get_member_decoded(pds, member)

        else:
            info = self.XMI.get_file_info_simple(member)
            file_data = self.XMI.get_seq_decoded(member)

        #member_exec = self.mime_exec(info['mimetype'])
        logger.debug("Opening {} with default app".format(member))
        giotype = Gio.content_type_from_mime_type(info['mimetype'])
        #default_app = Gio.app_info_get_all_for_type(info['mimetype'])[0]
        extract_folder = self.make_temp_folder()
        target = "{}/{}{}".format(extract_folder, member ,info['extension'])

        logger.debug("Extracting temp file to: {}".format(target))

        with open(target, 'wb') as extract_member:
            if isinstance(file_data, str):
                extract_member.write(file_data.encode('utf-8'))
            else:
                extract_member.write(file_data)

        member_gfile = Gio.File.new_for_path(target)
        uri = member_gfile.get_uri()
        timestamp = Gtk.get_current_event_time()
        Gtk.show_uri_on_window(None, uri, timestamp)
        #open_app = default_app.launch([member_gfile], None)

    def set_overwrite(self, toggle):
        if self.overwrite:
            self.overwrite = False
        else:
            self.overwrite = True
        logger.debug("Overwrite set to {}".format(self.overwrite))

    def toggle_unnum(self, toggle):
        if self.unnum:
            self.unnum = False
            self.update_status("UnNum disabled")
        else:
            self.unnum = True
            self.update_status("UnNum enabled")
        logger.debug("UnNum set to {}".format(self.unnum))
        self.refresh_file()

    def toggle_modify(self, toggle):
        if self.modify:
            self.modify = False
            self.update_status("Modify Date disabled")
        else:
            self.modify = True
            self.update_status("Modify Date enabled")
        logger.debug("Modify Date set to {}".format(self.modify))
        self.XMI.set_modify(self.modify)

    def set_folder(self, toggle):
        if self.make_folder:
            self.make_folder = False
        else:
            self.make_folder = True
        logger.debug("Make folder set to {}".format(self.make_folder))

    def _resolve_radio(self, master_radio):
        active = next((
            radio for radio in
            master_radio.get_group()
            if radio.get_active()
        ))
        return active

    def get_selected(self):
        (model, pathlist) = self.builder.get_object('file_selection').get_selected_rows()
        selected = []
        for path in pathlist :
            tree_iter = model.get_iter(path)
            filename = model.get_value(tree_iter,6)
            pds = model.get_value(tree_iter,7)
            selected.append((filename, pds))
        return(selected)

    # callback function for the dialog open_dialog
    def open_response(self, dialog, response_id):
        open_dialog = dialog
        # if response is "ACCEPT" (the button "Open" has been clicked)
        if response_id == Gtk.ResponseType.OK:
            selected_file = open_dialog.get_file()
            try:
                [success, self.file_data, etags] = selected_file.load_contents(None)
            except GObject.GError as e:
                logger.error("Error: " + e.message)
            # set the content as the text into the buffer
            self.file_name = open_dialog.get_filename()
            logger.debug("File opened: " + self.file_name)
            dialog.destroy()
            try:
                #self.load_file()
                self.loading_file()
            except Exception as err:
                logger.debug(err)
                message = "Error Opening {}"
                self.err_window.set_property("text",message.format(Path(self.file_name).name))
                self.err_window.set_property("secondary_text","Error: {}".format(err))
                self.err_window.set_transient_for(self.main_window)
                self.err_window.show()
                self.err_window.run()
                self.err_window.hide()


        # if response is "CANCEL" (the button "Cancel" has been clicked)
        elif response_id == Gtk.ResponseType.CANCEL:
            logger.debug("File open cancelled")
        # destroy the FileChooserDialog
            dialog.destroy()

    def right_click(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            logger.debug("Showing right click menu")
            self.right_click_menu.popup(None, None, None, None, event.button, event.time)

    def right_click_open(self, button):
        for selected in self.get_selected():
            logger.debug("Opening {}".format(selected))

            filename = selected[0]
            parent = selected[1]
            self.extract_and_open(filename, parent)

    def right_click_info(self, button):
        logger.debug("Right Click Info")
        for selected in self.get_selected():
            filename = selected[0]
            parent = selected[1]
            logger.debug("Filename: {} Parent: {}".format(filename, parent))

            if not parent:
                # Show file info
                if self.XMI.has_xmi():
                    self.show_info(None)
                    continue
                info = self.XMI.get_file_info_detailed(filename)
                img = self.mime_icon(info['mimetype'], size=64)
                desc = self.mime_desc(info['mimetype'])
                self.member_window = self.builder.get_object('tape_file_info_window')
                self.builder.get_object("tape_file_icon").set_from_pixbuf(img)
                if info['extension']:
                    self.builder.get_object("tape_file_info_name").set_text("{}{}".format(filename, info['extension']))
                else:
                    self.builder.get_object("tape_file_info_name").set_text(filename)
                self.builder.get_object("tape_file_info_type").set_text(desc)
                self.builder.get_object("tape_file_info_created").set_text(info['created'])
                self.builder.get_object("tape_file_info_expires").set_text(info['expires'])
                self.builder.get_object("tape_file_info_system_code").set_text(info['syscode'])
                self.builder.get_object("tape_file_info_job_id").set_text(info['jobid'])
                self.builder.get_object("tape_file_info_size").set_text(self.sizeof_fmt(info['size']))
                total = len(self.XMI.get_members(filename))
                if total > 0:
                    self.builder.get_object("tape_file_info_num_files").set_text(str(total))
                else:
                    self.builder.get_object("tape_file_info_num_files").set_text("1")
                self.builder.get_object("tape_file_info_lrecl").set_text(str(info['LRECL']))
                self.builder.get_object("tape_file_info_recfm").set_text(info['RECFM'])
                self.builder.get_object("tape_file_info_owner").set_text(info['owner'])
                self.builder.get_object("tape_file_info_user_label").set_text(self.XMI.get_user_label())
            else:

                self.member_window = self.builder.get_object('member_info_window')
                member = filename
                info = self.XMI.get_member_info(parent, member)
                img = self.mime_icon(info['mimetype'], size=64)
                desc = self.mime_desc(info['mimetype'])

                if 'alias' in info:
                    self.builder.get_object("member_alias").set_text(info['alias'])
                else:
                    self.builder.get_object("member_alias").set_text("N/A")

                self.builder.get_object("member_icon").set_from_pixbuf(img)
                self.builder.get_object("member_info").set_text(member)
                self.builder.get_object("member_recfm").set_text(info['RECFM'])
                self.builder.get_object("member_lrecl").set_text(str(info['LRECL']))
                self.builder.get_object("member_type").set_text(desc)
                self.builder.get_object("member_siz").set_text(self.sizeof_fmt(info['size']))


                if 'modified' in info:
                    modified = datetime.datetime.fromisoformat(info['modified']).strftime("%-d %B %Y, %H:%S")
                    created = datetime.datetime.fromisoformat(info['created']).strftime("%-d %B %Y, %H:%S")
                    self.builder.get_object("member_modified").set_text(modified)
                    self.builder.get_object("member_owner").set_text(info['owner'])
                    self.builder.get_object("member_created").set_text(created)
                    self.builder.get_object("member_version").set_text(info['version'])
                else:
                    self.builder.get_object("member_modified").set_text('N/A')
                    self.builder.get_object("member_owner").set_text('N/A')
                    self.builder.get_object("member_created").set_text('N/A')
                    self.builder.get_object("member_version").set_text('N/A')


            self.member_window.set_transient_for(self.main_window)
            self.member_window.show()
            self.member_window.run()

    def close_file_info(self, button):
        logger.debug("Closing Member Window")
        self.member_window.hide()

    def right_click_extract(self, button):
        logger.debug("Right Click Extract")
        self.builder.get_object("extract_selected").set_active(True)
        self.extract(button)

    def refresh_file(self):
        # this function gets called if someone changes the settings
        # - disabled UnNum
        # - changes code-page
        if self.file_data:
            logger.debug("Reloading data")
            self.loading_file()
        else:
            logger.debug("No data to refresh")

    def load_tape_file(self, update_status=True):
        logger.debug("Parsing Virtual Tape file {}".format(self.file_name))
        self.file_store_treeview.clear()


    def load_file(self, update_status=True):
        logger.debug("Parsing XMI file {}".format(self.file_name))
        self.file_store_treeview.clear()

        # Get a new object
        self.XMI = xmi.XMIT(loglevel=self.loglevel,
                unnum=self.unnum, encoding=self.codepage,
                binary=self.binary, force_convert=self.force
                )

        self.XMI.set_filename(self.file_name)
        self.XMI.set_file_object(self.file_data)
        try:
            self.XMI.open()
        except Exception as err:
            logger.debug(err)
            message = "Error opening \"{}\""
            self.err_window.set_property("text",message.format(Path(self.file_name).name))
            self.err_window.set_property("secondary_text","{}".format(err))
            self.err_window.set_transient_for(self.main_window)
            self.err_window.show()
            self.err_window.run()
            self.err_window.hide()
            self.stop_progress(None)
            return

        for f in self.XMI.get_files():
            info = self.XMI.get_file_info_simple(f)
            self.list_store_append(f, info)

        self.fill_info_window()

        if self.XMI.has_message():
            logger.debug("{} has message".format(self.file_name))
            self.msg_button.set_sensitive(True)
            self.builder.get_object("file_message_menu").set_sensitive(True)
            self.builder.get_object("info_messages").set_text("Yes")
        else:
            self.msg_button.set_sensitive(False)
            self.builder.get_object("file_message_menu").set_sensitive(True)
            self.builder.get_object("info_messages").set_text("No")

        self.builder.get_object("file_extract").set_sensitive(True)
        self.update_location()

        self.main_window.set_title(Path(self.file_name).name)

        self.builder.get_object("file_info").set_sensitive(True)
        self.builder.get_object("file_info_menu").set_sensitive(True)

        self.builder.get_object("location_go_up").set_sensitive(True)
        self.builder.get_object("location_go_home").set_sensitive(True)

        if update_status:
            self.update_status("{} objects ({})".format(self.XMI.get_num_files(), self.sizeof_fmt(self.XMI.get_total_size())))

    def fill_info_window(self):

        if self.XMI.has_xmi():
            filename = self.XMI.get_file()
            info = self.XMI.get_file_info_simple(filename)
            node_info = self.XMI.get_xmi_node_user()

            self.builder.get_object("info_filename").set_text(Path(self.file_name).name)
            self.builder.get_object("info_location").set_text(str(Path(self.file_name).parent.absolute()))
            self.builder.get_object("info_created").set_text(info['modified'])
            self.builder.get_object("info_pds").set_text(self.XMI.get_files()[0])
            self.builder.get_object("info_size").set_text(self.sizeof_fmt(len(self.file_data)))
            self.builder.get_object("info_num_files").set_text(str(self.XMI.get_num_files()))
            self.builder.get_object("info_from_node").set_text(node_info[0])
            self.builder.get_object("info_from_user").set_text(node_info[1])
            self.builder.get_object("info_to_node").set_text(node_info[2])
            self.builder.get_object("info_to_user").set_text(node_info[3])
            if self.XMI.is_pds(self.XMI.get_files()[0]):
                self.builder.get_object("info_type").set_text("PDS")
            else:
                self.builder.get_object("info_type").set_text("Sequential")
        else:
            self.builder.get_object("tape_info_filename").set_text(Path(self.file_name).name)
            self.builder.get_object("tape_info_location").set_text(str(Path(self.file_name).parent.absolute()))
            self.builder.get_object("tape_info_size").set_text(self.sizeof_fmt(len(self.file_data)))
            if "AWS" in Path(self.file_name).name.upper():
                self.builder.get_object("tape_info_type").set_text("AWS Virtual Tape")
            if "HET" in Path(self.file_name).name.upper():
                self.builder.get_object("tape_info_type").set_text("HET Virtual Tape")
            self.builder.get_object("tape_info_num_files").set_text(str(self.XMI.get_num_files()))
            self.builder.get_object("tape_info_owner").set_text(self.XMI.get_owner())
            self.builder.get_object("tape_info_volume").set_text(self.XMI.get_volser())
            created = datetime.datetime.fromtimestamp(Path(self.file_name).lstat().st_mtime).isoformat()
            self.builder.get_object("tape_info_created").set_text(created)


    def go_home(self, button):
        self.file_store_treeview.clear()
        for f in self.XMI.get_files():
            info = self.XMI.get_file_info_simple(f)
            self.list_store_append(f, info)
        self.update_location()
        self.update_status("{} objects ({})".format(self.XMI.get_num_files(), self.sizeof_fmt(self.XMI.get_total_size())))


    def update_location(self, location="/"):
        location_box = self.builder.get_object("location_bar")
        location_box.set_text(location)

    def sizeof_fmt(self, num):
        for unit in ['bytes','kB','MB','GB','TB','PB','EB','ZB']:
            if abs(num) < 1024.0:
                return "{:3.1f} {}".format(num, unit)
            num /= 1024.0
        return "{:.1f}{}".format(num, 'YB')

    def natural_key(self, string_):
        """See https://blog.codinghorror.com/sorting-for-humans-natural-sort-order/"""
        return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]

    #THREADS >:(

    def loading_file(self):
        self.working_window = self.builder.get_object("loading_file_window")
        self.builder.get_object("loading_file_label").set_text("Loading: {}".format(Path(self.file_name).name))
        self.builder.get_object("loading_file_size").set_text("File Size: {}".format(self.sizeof_fmt(len(self.file_data))))
        self.progress_bar = self.builder.get_object("loading_file_bar")
        self.update_status("Loading... {} ({})".format(self.file_name, self.sizeof_fmt(len(self.file_data))))
        self.working_window.show_all()
        self.working_window.set_keep_above(True)
        self.work_thread = threading.Thread(target=self.run_thread)
        self.running = True
        GLib.timeout_add(200, self.update_progress)
        self.work_thread.daemon = True
        self.work_thread.start()

    def update_progress(self):
        if self.running:
            self.progress_bar.pulse()
        return self.running

    # this will get run in a separate thread
    def run_thread(self):

        self.load_file()

        GLib.idle_add(self.stop_progress)

    # this will get run in the GUI thread when the worker thread is done
    def stop_progress(self):
        self.running = False
        self.work_thread.join()
        self.working_window.hide()


logger.setLevel(logging.WARNING)

desc = 'XMIssion: XMI and Virtual Tape (AWS/HET) File Manager'
arg_parser = argparse.ArgumentParser(description=desc)
arg_parser.add_argument('-d', '--debug', help="Print debugging statements", action="store_const", dest="loglevel", const=logging.DEBUG, default=logging.WARNING)
arg_parser.add_argument("filename", help="xmi/het/aws to extract", nargs="?", default=None)
args = arg_parser.parse_args()

app = XMIssion(loglevel=args.loglevel, filename=args.filename)
Gtk.main()