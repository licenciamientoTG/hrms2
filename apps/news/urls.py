from django.urls import path
from .views import news_view, admin_news_view, user_news_view, create_news

urlpatterns = [
    path('', news_view, name='news_view'),
    path('news/admin/', admin_news_view, name='admin_news'),
    path('news/user/', user_news_view, name='user_news'),
    path('news/create/', create_news, name='news_create'),
]
