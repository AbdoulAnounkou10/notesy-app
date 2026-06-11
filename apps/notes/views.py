import time

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
            print(f"login ok user={username}")
            return redirect("note_list")
        print(f"login failed user={username}")
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
        print(f"note created id={note.pk} owner={request.user.username}")
        return render(request, "notes/_note_card.html", {"note": note})
    return render(request, "notes/_editor.html", {"note": None})


@login_required
def note_edit(request, pk):
    note = get_object_or_404(Note, pk=pk, owner=request.user)
    if request.method == "POST":
        note.title = request.POST.get("title", note.title)
        note.body = request.POST.get("body", note.body)
        note.save()
        print(f"note saved id={note.pk}")
        return render(request, "notes/_note_card.html", {"note": note})
    return render(request, "notes/_editor.html", {"note": note})


@login_required
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk, owner=request.user)
    note.delete()
    print(f"note deleted id={pk}")
    return HttpResponse(status=204)


@login_required
def note_summarize(request, pk):
    """Generate a 'summary' for a note.

    Calls out to the company's internal summarization service. In dev we
    just sleep to simulate the network round-trip.
    """
    note = get_object_or_404(Note, pk=pk, owner=request.user)
    time.sleep(8)
    note.summary = (note.body or "")[:140] + ("..." if len(note.body or "") > 140 else "")
    note.save(update_fields=["summary"])
    print(f"note summarized id={note.pk}")
    return render(request, "notes/_note_card.html", {"note": note})
