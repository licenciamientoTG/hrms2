from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegisterForm
import urllib.request
import json

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

@login_required
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

@login_required
def home(request):
    # 🌤️ Clima (OpenWeather)
    weather_api_key = '61db0691e7a611b011ca511f90880719'
    city = 'Mexico City'
    weather_url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={weather_api_key}&units=metric&lang=es'

    weather_data = {}
    try:
        with urllib.request.urlopen(weather_url) as response:
            data = json.loads(response.read().decode())
            weather_data = {
                'temp': round(data['main']['temp']),
                'description': data['weather'][0]['description'].capitalize(),
                'city': data['name']
            }
    except Exception as e:
        print('Error clima:', e)
        weather_data = {'temp': 'N/A', 'description': 'No disponible', 'city': city}

    # 💵 Dólar (Fixer)
    fixer_api_key = 'df3820a247c7c2ff1865f1fe1fde5dcb'
    fixer_url = f'https://api.apilayer.com/fixer/latest?base=USD&symbols=MXN'
    req = urllib.request.Request(fixer_url)
    req.add_header('apikey', fixer_api_key)

    dollar_data = {}
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            dollar_data = {
                'mxn': round(data['rates']['MXN'], 2)
            }
    except Exception as e:
        print('Error dólar:', e)
        dollar_data = {'mxn': 'N/A'}

    return render(request, 'home.html', {
        'weather': weather_data,
        'dollar': dollar_data
    })
