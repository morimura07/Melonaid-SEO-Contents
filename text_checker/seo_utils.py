from dotenv import load_dotenv
from numpy import dot
from numpy.linalg import norm
from openai import OpenAI
from celery import shared_task
import os, random, requests
from uuid import uuid4
import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")

def search_web(query, key_points, num_results=10):
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        raise ValueError("Google API key or CSE ID not found in .env file.")

    full_query = f"{query} {key_points} для детей"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": full_query,
        "num": num_results,
        "hl": "ru"
    }

    try:
        response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])

        if not items:
            print("No items found in Google CSE response.")
        
        return [(item["title"], item.get("snippet", ""), item["link"]) for item in items]

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")

        return []

def shorten_url(url, max_length=49):
    if len(url) <= max_length:
        return url
    
    return url[:50] + "..." + url[-19:]

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in .env file.")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def format(key_points):
    if not key_points:
        return "с выводом и советом в конце статьи"

    text = ", уделяя особое внимание следующим аспектам: "

    if len(key_points) == 1:
        return text + key_points[0]

    if len(key_points) == 2:
        return text + " и ".join(key_points)

    return text + ", ".join(key_points[:-1]) + " и " + key_points[-1]

@shared_task
def write_article(id, technical_task, key_points):
    key_points = format(key_points)
    similar_articles = retrieve_similar_articles(technical_task, top_k=5, similarity_threshold=0.2)
    context = "\n\n".join(similar_articles)
    web_sources = search_web(technical_task, key_points)
    print(web_sources)
    urls = [url for _, _, url in web_sources]
    random.shuffle(urls)
    unique_marker = str(uuid4())[:8]

    if len(technical_task) < 300:
        if "https" in technical_task:
            prompt_templates = [
                "Напиши подробную, SEO-оптимизированную статью о \"{topic}\" на 11000-13000 символов, ориентированную на семей с детьми, с фокусом на: {points}. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале.",
                "Создай развернутую, SEO-оптимизированную статью по теме \"{topic}\" на 11000-13000 символов, ориентированную на семей с детьми, раскрыв аспекты: {points}. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале.",
                "Создай развернутую, SEO-оптимизированную статью по теме \"{topic}\" на 11000-13000 символов, ориентированную на семей с детьми, раскрыв аспекты: {points}. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале."
            ]
        else:
            prompt_templates = [
                "Напиши подробную, SEO-оптимизированную статью о \"{topic}\" на 11000-13000 символов, ориентированную на семей с детьми, с фокусом на: {points}. Убедись, что тема \"{topic}\" также включена в середине предложения в статье. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале.",
                "Создай развернутую, SEO-оптимизированную статью по теме \"{topic}\" на 11000-13000 символов, ориентированную на семей с детьми, раскрыв аспекты: {points}. Убедись, что тема \"{topic}\" также включена в середине предложения в статье. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале.",
                "Создай развернутую, SEO-оптимизированную статью по теме \"{topic}\" на 11000-13000 символов, ориентированную на семей с детьми, раскрыв аспекты: {points}. Убедись, что начало тема \"{topic}\" также включена в середине предложения в статье. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале."
            ]
    else:
        prompt_templates = [
            "Напиши подробную, SEO-оптимизированную статью на основе ствтьи ниже: \n{topic}\n на 11000-13000 символов, ориентированную на семей с детьми, с фокусом на: {points}, придерживаясь оригинального текста. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале.",
            "Создай развернутую, SEO-оптимизированную статью на основе ствтьи ниже: \n{topic}\n на 11000-13000 символов, ориентированную на семей с детьми, раскрыв аспекты: {points}, придерживаясь оригинального текста. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале.",
            "Составь SEO-оптимизированный текст на основе ствтьи ниже: \n{topic}\n на 11000-13000 символов с упором на: {points}, ориентированную на семей с детьми, придерживаясь оригинального текста. Используй информацию из {context} в тексте статьи. Добавь короткие title:, description: и keywords: в начале."
        ]
    
    prompt = random.choice(prompt_templates).format(topic=technical_task, points=key_points)
    prompt += f"\n\n# Сеанс генерации: {unique_marker}"
    
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are an expert technical writer specializing in creating clear, informative, unique, structured and SEO-optimized articles in Russian. Always meet the following requirements: Glvrd.ru ≥ 9.5 (макс 10), Advego - доля вхождения стоп-слов и предлогов ≤ 1.5%, доля вхождения остальных слов ≤ 2.4%, Text.ru - уникальность ≥ 90%, спамность ≤ 50%, водность ≤ 15%, SEO-оптимизация, читабельност ь, плотность ключевых слов, проверка на плагиат, Turgenev (Ashmanov): - ясность, последовательность, читаемость, SEO-принципы, ориентированные на русскоязычный текст - Общий балл не более 4. At the end of the article, include a block 'Оценки текста:' with results (rounded to 1-2 d. p. when needed) from 4 tools, each on new line."},
            {"role": "user", "content": prompt}
         ],
        temperature=0.8,
        top_p=0.9,
        frequency_penalty=0.4,
        presence_penalty=0.6,
    )

    rewritten_text = response.choices[0].message.content
    
    if urls:
        web_links_with_newlines = "\n\n".join(f"[{shorten_url(url)}]({url})" for url in urls)
        rewritten_text += "\n\nИсточники, использованные при подготовке статьи:\n\n" + web_links_with_newlines

    return rewritten_text

def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))

def generate_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def retrieve_similar_articles(query_text, top_k=5, similarity_threshold=0.2):
    from .models import Article

    query_embedding = generate_embedding(query_text)
    articles = Article.objects.exclude(embedding=None)
    ranked_articles = []

    for article in articles:
        sim = cosine_similarity(query_embedding, article.embedding)

        if sim > similarity_threshold:
            ranked_articles.append((sim, article))

    ranked_articles.sort(reverse=True, key=lambda x: x[0])

    return [a.content for _, a in ranked_articles[:top_k]]
