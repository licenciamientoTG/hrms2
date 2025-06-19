from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegisterForm

def login_view(request):
    if request.method == "POST":
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")

    else:
        form = LoginForm()
    
    return render(request, "authapp/login.html", {"form": form})


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Error al registrar usuario")
    else:
        form = RegisterForm()

    return render(request, "authapp/register.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")
