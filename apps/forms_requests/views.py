from django.shortcuts import render, redirect
from .forms import FormRequestForm
from django.contrib.auth.decorators import login_required

@login_required
def request_form_view(request):
    if request.method == "POST":
        form = FormRequestForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('form_success')  # Redirige a una página de éxito
    else:
        form = FormRequestForm()

    return render(request, 'forms_requests/request_form.html', {'form': form})

def form_success_view(request):
    return render(request, 'forms_requests/form_success.html')
