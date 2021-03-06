
"""
This contains a simple view for rendering the webclient
page and serve it eventual static content.

"""
from __future__ import print_function

import tempfile, time, json, re
from django import http
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from evennia.server.sessionhandler import SESSIONS
from evennia.utils import logger
from muddery.utils import exporter
from muddery.utils import importer
from muddery.utils.builder import build_all
from muddery.utils.localized_strings_handler import LS
from muddery.utils.game_settings import CLIENT_SETTINGS
from muddery.worlddata.editor import form_view, page_view, relative_view


relative_forms = {
    "world_exits": {"CLASS_LOCKED_EXIT": "exit_locks"},
    "world_objects": {"CLASS_OBJECT_CREATOR": "object_creators"}
}

@staff_member_required
def worldeditor(request):
    """
    World Editor page template loading.
    """
    if "export" in request.GET:
        return export_file(request)
    elif "import" in request.FILES:
        return import_file(request)
    elif "apply" in request.POST:
        return apply_changes(request)

    return render(request, 'worldeditor.html')


@staff_member_required
def export_file(request):
    """
    Export game world files.
    """
    def file_iterator(file, chunk_size=512):
        while True:
            c = file.read(chunk_size)
            if c:
                yield c
            else:
                # remove temp file
                file.close()
                break

    response = http.HttpResponseNotModified()

    # get data's zip
    try:
        zipfile = tempfile.TemporaryFile()
        exporter.export_zip_all(zipfile)
        zipfile.seek(0)

        filename = time.strftime("worlddata_%Y%m%d_%H%M%S.zip", time.localtime())
        response = http.StreamingHttpResponse(file_iterator(zipfile))
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = 'attachment;filename="%s"' % filename
    except Exception, e:
        zipfile.close()
        message = "Can't export world: %s" % e
        logger.log_tracemsg(message)
        return render(request, 'fail.html', {"message": message})

    return response


@staff_member_required
def import_file(request):
    """
    Import the game world from an uploaded zip file.
    """
    response = http.HttpResponseNotModified()
    file_obj = request.FILES.get("import", None)

    if file_obj:
        zipfile = tempfile.TemporaryFile()
        try:
            for chunk in file_obj.chunks():
                zipfile.write(chunk)
            importer.import_zip_all(zipfile)
        except Exception, e:
            zipfile.close()
            logger.log_tracemsg("Cannot import world: %s" % e)
            return render(request, 'fail.html', {"message": str(e)})

        zipfile.close()

    return render(request, 'success.html', {"message": "Data imported!"})

@staff_member_required
def apply_changes(request):
    """
    Apply the game world's data.
    """
    try:
        # rebuild the world
        build_all()

        # send client settings
        CLIENT_SETTINGS.reset()
        text = json.dumps({"settings": CLIENT_SETTINGS.all_values()})
        SESSIONS.announce_all(text)

        # reload
        SESSIONS.announce_all(" Server restarting ...")
        SESSIONS.server.shutdown(mode='reload')
    except Exception, e:
        message = "Can't build world: %s" % e
        logger.log_tracemsg(message)
        return render(request, 'fail.html', {"message": message})

    return render(request, 'success.html', {"message": LS("Data applied! The server is reloading.")})


@staff_member_required
def editor(request):
    """
    World Editor page template loading.
    """
    try:
        name = re.sub(r"^/worlddata/editor/", "", request.path)
        return render(request, name, {"self": request.get_full_path()})
    except Exception, e:
        logger.log_tracemsg(e)
        raise http.Http404


@staff_member_required
def list_view(request):
    try:
        if "_back" in request.POST:
            return page_view.quit_list(request)
        else:
            return page_view.view_list(request)
    except Exception, e:
        logger.log_tracemsg("Invalid view request: %s" % e)

    raise http.Http404


@staff_member_required
def view_form(request):
    try:
        path_list = request.path.split("/")
        form_name = path_list[-2]
    except Exception, e:
        logger.log_errmsg("Invalid form.")
        raise http.Http404

    try:
        if form_name in relative_forms:
            return relative_view.view_form(request, form_name, "relative_form.html",
                                           relative_forms[form_name])
        else:
            return form_view.view_form(form_name, request)
    except Exception, e:
        logger.log_tracemsg("Invalid view request: %s" % e)
        
    raise http.Http404


@staff_member_required
def submit_form(request):
    """
    Edit worlddata.

    Args:
        request:

    Returns:
        None.
    """
    try:
        path_list = request.path.split("/")
        form_name = path_list[-2]
    except Exception, e:
        logger.log_errmsg("Invalid form.")
        raise http.Http404

    try:
        if "_back" in request.POST:
            return form_view.quit_form(form_name, request)
        elif "_delete" in request.POST:
            if form_name in relative_forms:
                return relative_view.delete_form(request, form_name, relative_forms[form_name])
            else:
                return form_view.delete_form(form_name, request)
        else:
            if form_name in relative_forms:
                return relative_view.submit_form(request, form_name, "relative_form.html",
                                                 relative_forms[form_name])
            else:
                return form_view.submit_form(form_name, request)
    except Exception, e:
        logger.log_tracemsg("Invalide edit request: %s" % e)
        
    raise http.Http404
