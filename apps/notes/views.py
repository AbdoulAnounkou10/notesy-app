import logging  # ADDED: replaces all print() statements with proper logging

# ADDED: creates a logger named after this module (apps.notes.views)
# this means log output shows exactly which file the message came from
logger = logging.getLogger(__name__)

# REMOVED: import time — was only used for time.sleep(8) which we deleted

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Note


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # CHANGED: print() -> logger.info()
            # print() has no timestamp, no log level, can't be filtered or alerted on
            logger.info("login_success user=%s", username)
            return redirect("note_list")
        # CHANGED: print() -> logger.warning()
        # failed logins are security-relevant, warning level is appropriate
        logger.warning("login_failed user=%s", username)
        return render(request, "notes/login.html", {"error": "Invalid credentials"})
    return render(request, "notes/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def note_list(request):
    notes = Note.objects.filter(owner=request.user)
    return render(request, "notes/list.html", {"notes": notes})


@login_required
def note_detail(request, pk):
    note = get_object_or_404(Note, pk=pk, owner=request.user)
    return render(request, "notes/_note_card.html", {"note": note})


@login_required
def note_create(request):
    if request.method == "POST":
        note = Note.objects.create(
            owner=request.user,
            title=request.POST.get("title", "Untitled"),
            body=request.POST.get("body", ""),
        )
        # CHANGED: print() -> logger.info()
        logger.info("note_created id=%s owner=%s", note.pk, request.user.username)
        return render(request, "notes/_note_card.html", {"note": note})
    return render(request, "notes/_editor.html", {"note": None})


@login_required
def note_edit(request, pk):
    note = get_object_or_404(Note, pk=pk, owner=request.user)
    if request.method == "POST":
        note.title = request.POST.get("title", note.title)
        note.body = request.POST.get("body", note.body)
        note.save()
        # CHANGED: print() -> logger.info()
        logger.info("note_saved id=%s", note.pk)
        return render(request, "notes/_note_card.html", {"note": note})
    return render(request, "notes/_editor.html", {"note": note})


@login_required
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk, owner=request.user)
    note.delete()
    # CHANGED: print() -> logger.info()
    logger.info("note_deleted id=%s", pk)
    return HttpResponse(status=204)


@login_required
def note_summarize(request, pk):
    """Generate a summary for a note.

    Calls out to the company's internal summarization service.
    Currently stubbed — returns a truncated version of the body.
    """
    note = get_object_or_404(Note, pk=pk, owner=request.user)

    # ADDED: try/except so a failure returns a graceful error instead of a 500
    try:
        # REMOVED: time.sleep(8)
        # This was blocking an entire gunicorn thread for 8 seconds per request
        # With 2 workers, 2 simultaneous summarize requests would starve all other traffic
        note.summary = (note.body or "")[:140] + ("..." if len(note.body or "") > 140 else "")
        note.save(update_fields=["summary"])
        # CHANGED: print() -> logger.info()
        logger.info("note_summarized id=%s", note.pk)
    except Exception:
        # ADDED: log the full exception traceback so we can debug failures
        # logger.exception() automatically includes the stack trace
        logger.exception("summarize_failed id=%s", note.pk)
        # ADDED: graceful fallback so the user sees something instead of a 500
        note.summary = "Summary unavailable — please try again."
        note.save(update_fields=["summary"])

    return render(request, "notes/_note_card.html", {"note": note})