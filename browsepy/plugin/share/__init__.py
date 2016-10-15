#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import browsepy, flask, magic, os.path, pprint

from .fileservice import FileService

def get_all_mimetypes():
    exceptions = [ "inode" ]
    excluded = []
    mimetypes = []
    f = open("/etc/mime.types")
    if f:
        for line in f.readlines():
            if "\t" in line:
                mimetypes.append(line.split("\t")[0])

    for mimetype in mimetypes:
        for exception in exceptions:
            if exception in mimetype:
                excluded.append(mimetype)
                break

    if excluded:
        print("All mimetypes can be shared except for these.")
        pprint.pprint(excluded)

    return [mimetype for mimetype in mimetypes if mimetype not in excluded]

__basedir__= os.path.dirname(os.path.abspath(__file__))

share_blueprint = flask.Blueprint('share', __name__,
    url_prefix='/share',
    template_folder=os.path.join(__basedir__, 'templates'),
    static_folder=os.path.join(__basedir__, 'static'),
    )

fileservice = FileService()
root_url = ""

@share_blueprint.route("/clear/<key>")
def clear(key):
    if key == "secretkey":
        fileservice.clear()
        return "Shared files cleared.", 200
    else:
        return "Not Authorized.", 403

@share_blueprint.route("/file/<path:path>")
def file(path):
    file = browsepy.File.from_urlpath(path)
    hash = fileservice.add_file(file.path)
    if hash:
        url = root_url + "/share/get/" + hash
        ret = "Access the file from the address <a href=\"" + url + "\">" + os.path.basename(file.path) + "</a>"
        return ret, 200
    else:
        return "File could not be shared.", 400

def register_plugin(manager):
    root_url = manager.app.config["root_url"]

    manager.register_blueprint(share_blueprint)

    style = manager.style_class('share.static', filename='css/browse.css')
    manager.register_widget(style)

    share_widget = manager.button_class(css='share')
    manager.register_action(
        "share.file",
        share_widget,
        mimetypes=get_all_mimetypes())

    @manager.app.route("/share/get/<hash>")
    def give(hash):
        file = fileservice.get_file(hash)

        if not file:
            return "Not found.", 404

        filepath = file["path"]
        if not os.path.exists(filepath):
            return "Not found.", 404

        response = flask.Response(
            fileservice.file_read_generator(file),
            mimetype=magic.from_file(filepath, mime=True))

        response.headers.add("Content-Disposition",
                             "attachment; filename=\"" + os.path.basename(filepath) + "\"");
        response.headers.add("Content-Length",
                             str(os.path.getsize(filepath)))
        return response
