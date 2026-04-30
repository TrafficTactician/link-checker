import streamlit as st
import requests
import pandas as pd
import time
import json
import os
import re

st.set_page_config(page_title="Link Checker Pro (API Edition)", layout="wide")

# --- СОХРАНЕНИЕ ТОКЕНА В ФАЙЛ ---
CONFIG_FILE = "api_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"api_token": ""}

def save_config(token):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"api_token": token}, f)

saved_data = load_config()

# --- ПАМЯТЬ СЕССИИ ---
if "api_token" not in st.session_state:
    st.session_state.api_token = saved_data.get("api_token", "")
if "results" not in st.session_state:
    st.session_state.results = []

def clean_domain(url):
    """Очищает домен от http://, www. и слэшей"""
    url = url.strip().lower()
    if not url: return ""
    url = re.sub(r'^https?://', '', url)
    url = url.split('/')[0]
    if url.startswith('www.'):
        url = url[4:]
    return url

# --- ИНТЕРФЕЙС ---
st.title("🕵️‍♂️ Link Checker Pro (Аутрич)")

with st.sidebar:
    st.header("🔑 Авторизация")
    st.markdown("Вставь официальный **API Token** из личного кабинета.")
    
    input_token = st.text_input("API Token:", value=st.session_state.api_token, type="password")
    
    if st.button("💾 Сохранить токен", use_container_width=True):
        clean_token = input_token.strip()
        st.session_state.api_token = clean_token
        save_config(clean_token)
        st.success("Токен сохранен!")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    
    if st.button("🗑️ Сбросить токен", use_container_width=True):
        st.session_state.api_token = ""
        save_config("")
        st.warning("Токен удален!")
        time.sleep(1)
        st.rerun()

if st.session_state.api_token:
    
    # Настройки для официального API
    headers = {
        "Authorization": f"Bearer {st.session_state.api_token}",
        "Content-Type": "application/json"
    }
    
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Уже купленные домены")
        bought_input = st.text_area("Вставь список:", height=150, key="old_txt")

    with col2:
        st.subheader("Новые домены для проверки")
        new_input = st.text_area("Вставь список:", height=150, key="new_txt")

    if st.button("🚀 Проверить домены", type="primary"):
        bought_domains = set([clean_domain(d) for d in bought_input.splitlines() if clean_domain(d)])
        new_domains = [clean_domain(d) for d in new_input.splitlines() if clean_domain(d)]
        new_domains = list(dict.fromkeys(new_domains)) # Удаляем дубликаты
        
        if not new_domains:
            st.warning("Введи домены для проверки.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.info(f"Связываемся с официальным API... Ищем {len(new_domains)} уникальных доменов.")
            
            all_api_results = {}
            chunk_size = 100 # API легко "проглотит" по 100 штук за раз
            
            for i in range(0, len(new_domains), chunk_size):
                chunk = new_domains[i:i + chunk_size]
                payload = {"domains": chunk}
                
                success = False
                for attempt in range(3):
                    try:
                        response = requests.post("https://linkdetective.pro/api/v1/domains", json=payload, headers=headers, timeout=20)
                        
                        if response.status_code == 200:
                            data = response.json()
                            results_dict = data.get('results', {})
                            all_api_results.update(results_dict)
                            success = True
                            break 
                            
                        elif response.status_code == 429:
                            status_text.warning(f"⏳ API просит паузу (429). Ждем 5 секунд... (Попытка {attempt+1}/3)")
                            time.sleep(5) 
                            continue
                            
                        elif response.status_code == 401:
                            st.error("Ошибка 401: Неверный или устаревший API Token. Проверь его в меню слева.")
                            st.stop()
                        elif response.status_code == 400:
                            st.error("Ошибка 400: Проблема с форматом данных. Возможно, слишком много доменов в одном запросе.")
                            st.stop()
                        else:
                            st.error(f"Неизвестная ошибка сервера: {response.status_code}")
                            st.stop()
                            
                    except Exception as e:
                        status_text.warning(f"Сбой сети. Повтор через 5 секунд... (Попытка {attempt+1}/3)")
                        time.sleep(5)
                
                if not success:
                    st.error("Не удалось пробиться к API после 3 попыток. Попробуй позже.")
                    st.stop()
                    
                time.sleep(0.5) # Маленькая пауза из вежливости к серверу
            
            total_items = len(new_domains)
            if not all_api_results:
                status_text.warning("Сайт не нашел данные ни по одному из указанных доменов.")
            else:
                results = []
                
                # Собираем данные в красивую таблицу
                for index, domain in enumerate(new_domains):
                    is_bought = "✅ Да" if domain in bought_domains else "❌ Нет"
                    
                    domain_data = all_api_results.get(domain)
                    
                    if domain_data:
                        results.append({
                            "Домен": domain,
                            "Уже покупали?": is_bought,
                            "Цена (от)": f"${domain_data.get('price', 0)}",
                            "Средняя цена": f"${domain_data.get('avg', 0)}",
                            "Медианная цена": f"${domain_data.get('median', 0)}"
                        })
                    else:
                        results.append({
                            "Домен": domain,
                            "Уже покупали?": is_bought,
                            "Цена (от)": "Нет в базе",
                            "Средняя цена": "-",
                            "Медианная цена": "-"
                        })
                        
                    progress_bar.progress((index + 1) / total_items)
                
                st.session_state.results = results
                status_text.success(f"✅ Проверка успешно завершена! Обработано доменов: {total_items}")

    # Отрисовка результатов
    if st.session_state.results:
        st.divider()
        st.subheader(f"📊 Результаты ({len(st.session_state.results)} шт.)")
        st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)

else:
    st.info("👈 Пожалуйста, сгенерируй API Token на сайте LinkDetective и вставь его в меню слева.")
