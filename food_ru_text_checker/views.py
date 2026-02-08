from django.http import JsonResponse
from .seo_utils import write_article
from django.shortcuts import render, get_object_or_404
from .models import SEOText, Article
import json, os, re
from openai import OpenAI
from dotenv import load_dotenv
from django.views.decorators.csrf import csrf_exempt
from numpy import dot
from numpy.linalg import norm
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q

def home(request):
    if request.method == "POST":
        data = json.loads(request.body)
        original_text = data.get('original_text')
        key_points = data.get('key_points', [])

        if not original_text:
            return JsonResponse({"error": "Topic is required!"}, status=400)
        
        seo_text = SEOText.objects.create(original_text=original_text)
        article = write_article(seo_text.id, original_text, key_points)

        if article: 
            return JsonResponse({"rewritten_text": article})
        else:
            return JsonResponse({"error": "Failed to generate article."}, status=500)

    return render(request, "home.html")

# @require_POST
# def save_article(request):
#     data = json.loads(request.body)

#     title = data.get("title", "").strip()
#     content = data.get("content", "").strip()

#     if not title or not content:
#         return JsonResponse({"error": "Title and content are required."}, status=400)

#     try:
#         Article.objects.create(title=title, content=content)

#         return JsonResponse({"success": True})
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=500)

# @require_POST
# def save_article(request):
#     data = json.loads(request.body)
#     content = data.get("content", "").strip()

#     if not content:
#         return JsonResponse({"error": "Content is required."}, status=400)

#     first_line = content.split("\n")[0].strip()

#     if len(first_line) > 150:
#         title = first_line[:147] + "..."
#     else:
#         title = first_line or "Без названия"

#     try:
#         Article.objects.create(title=title, content=content)
        
#         return JsonResponse({"success": True, "title": title})
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=500)

def save_article(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    data = json.loads(request.body)
    content = data.get("content", "")
    title = data.get("title", "").strip()

    pattern = r"(?m)^\s{0,3}(?:\*\*)?\s*(#{1,3})\s*(.*?)\s*(?:\*\*)?\s*$"
    match = re.search(pattern, content)

    if match:
        title = match.group(2).strip()
        content = re.sub(pattern, "", content, count=1).lstrip()

    if not title:
        title = "Без названия"

    article = Article.objects.create(
        title=title,
        content=content
    )

    return JsonResponse({"success": True, "id": article.id})

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@csrf_exempt
def generate_keywords(request):
    if request.method == "POST":
        data = json.loads(request.body)
        topic = data.get("topic", "")

        if not topic.strip():
            return JsonResponse({"error": "No topic provided."}, status=400)

        prompt = f"Сгенерируй 10 релевантных ключевых слов на русском языке по теме: \"{topic}\", которые наиболее SEO релеватны для этой темы (только слова!)."

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты помогаешь с SEO и копирайтингом."},
                {"role": "user", "content": prompt}
            ]
        )

        keywords_raw = response.choices[0].message.content.strip()
        keywords = [kw.strip("•-–1234567890. ") for kw in keywords_raw.split("\n") if kw.strip()]
        
        return JsonResponse({"keywords": keywords[:10]})

    return JsonResponse({"error": "Only POST method allowed."}, status=405)

def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))

def generate_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )

    return response.data[0].embedding

@require_GET
def find_related_articles(request):
    topic = request.GET.get("topic", "").strip()
    keywords = request.GET.getlist("keywords[]", [])

    query = Q(title__icontains=topic) | Q(content__icontains=topic)

    for keyword in keywords:
        query |= Q(title__icontains=keyword) | Q(content__icontains=keyword)

    articles = Article.objects.filter(query)

    data = [{
        "id": article.id,
        "title": article.title,
        "snippet": article.content[:150] + "..."
    } for article in articles[:5]]

    return JsonResponse({"articles": data})

def get_article(request):
    article_id = request.GET.get("id")

    if not article_id:
        return JsonResponse({"error": "Article ID is missing."}, status=400)

    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        return JsonResponse({"error": "Article not found."}, status=404)

    content = article.content or ""

    content = re.sub(r'^\s*-{3,}\s*$', '', content, flags=re.MULTILINE)

    def bold_headings(line):
        return re.sub(r'^(#{2,4})\s*(.+)$', r'<strong>\2</strong>', line)

    
    def bold_markdown(text):
        return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    
    formatted_content = "\n".join(
        bold_markdown(bold_headings(line)) for line in content.splitlines()
    )

    return JsonResponse({
        "title": article.title,
        "content": formatted_content
    })

from django.db.models import Q

def recent_articles(request):
    topic = request.GET.get("topic", "").strip()

    if not topic:
        return JsonResponse({"error": "Missing topic"}, status=400)
    
    query = Q(title__icontains=topic)

    query |= Q(content__regex=rf'(?i)^#{1,6}\s*{re.escape(topic)}')
    query |= Q(content__icontains=topic)

    articles = Article.objects.filter(query).order_by('-created_at')[:2]

    return JsonResponse({
        "articles": [
            {"id": a.id, "title": a.title, "content": a.content}
            for a in articles
        ]
    })

@require_POST
def delete_article(request):
    import json
    
    data = json.loads(request.body)
    article_id = data.get("id")

    if not article_id:
        return JsonResponse({"error": "Missing article ID"}, status=400)

    try:
        Article.objects.filter(id=article_id).delete()

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)