from django.shortcuts import render, redirect
from .models import News, NewsTag
from django.contrib.auth.decorators import login_required, user_passes_test

#esta vista solo nos separa la vista del usuario y del administrador por medio de su url
@login_required
def news_view(request):
    if request.user.is_superuser:
        return redirect('admin_news')
    else:
        return redirect('user_news')

#esta vista nos dirige a la plantilla de nuestro administrador
@user_passes_test(lambda u: u.is_superuser)
def admin_news_view(request):
    return render(request, 'news/admin/news_view_admin.html')

#esta vista nos dirige a la plantilla de nuestro usuario
@login_required
def user_news_view(request):
    return render(request, 'news/user/news_view_user.html')

#esta es la vista para la plantilla de crear noticias
@user_passes_test(lambda u: u.is_superuser)
def create_news(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        cover_image = request.FILES.get('cover_image')
        attachments = request.FILES.get('attachments')
        publish_at = request.POST.get('publish_at')
        notify_email = bool(request.POST.get('notify_email'))
        notify_push = bool(request.POST.get('notify_push'))
        audience = request.POST.get('audience')
        tag_ids = request.POST.getlist('tags')

        news = News.objects.create(
            title=title,
            content=content,
            cover_image=cover_image,
            attachments=attachments,
            publish_at=publish_at,
            notify_email=notify_email,
            notify_push=notify_push,
            audience=audience,
            author=request.user
        )
        if tag_ids:
            news.tags.set(tag_ids)

        return redirect('admin_news')

    tags = NewsTag.objects.all()
    return render(request, 'news/admin/create_news.html', {
        'available_tags': tags
    })