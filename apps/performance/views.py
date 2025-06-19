from django.shortcuts import render, redirect
from .forms import PerformanceReviewForm
from django.contrib.auth.decorators import login_required

@login_required
def performance_review_view(request):
    if request.method == "POST":
        form = PerformanceReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.save()
            return redirect('performance_success')  # Redirige a la página de éxito
    else:
        form = PerformanceReviewForm()

    return render(request, 'performance/performance_form.html', {'form': form})

def performance_success_view(request):
    return render(request, 'performance/performance_success.html')
