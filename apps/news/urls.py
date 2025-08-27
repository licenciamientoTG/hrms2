from django.urls import path
from .views import news_view, admin_news_view, user_news_view, create_news, news_detail_admin, news_detail_user, news_delete

urlpatterns = [
    path('', news_view, name='news_view'),
    path('news/admin/', admin_news_view, name='admin_news'),
    path('news/user/', user_news_view, name='user_news'),
    path('news/create/', create_news, name='news_create'),
    path('news/admin/<int:pk>/', news_detail_admin, name='news_detail_admin'),
    path('news/user/<int:pk>/', news_detail_user, name='news_detail_user'),
    path('news/admin/<int:pk>/delete/', news_delete, name='news_delete'),
]
