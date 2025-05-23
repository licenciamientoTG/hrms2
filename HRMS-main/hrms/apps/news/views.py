from django.shortcuts import render
from .models import News
from django.contrib.auth.decorators import login_required

@login_required
def news_list(request):
    news = News.objects.all().order_by('-published_at')
    return render(request, 'news/news_list.html', {'news': news})
