from django.shortcuts import render, redirect
from .forms import VacationRequestForm
from django.contrib.auth.decorators import login_required

@login_required
def vacation_request_view(request):
    if request.method == "POST":
        form = VacationRequestForm(request.POST)
        if form.is_valid():
            vacation_request = form.save(commit=False)
            vacation_request.user = request.user
            vacation_request.save()
            return redirect('vacation_success')  # Redirige a la página de éxito
    else:
        form = VacationRequestForm()

    return render(request, 'vacations/vacation_form.html', {'form': form})

def vacation_success_view(request):
    return render(request, 'vacations/vacation_success.html')
