import streamlit as st
import requests
import pandas as pd
import time
import json
import os
import re

st.set_page_config(page_title="Link Checker Pro (Аутрич)", layout="wide")

# --- СОХРАНЕНИЕ ТОКЕНА В ФАЙЛ ---
CONFIG_FILE = "jwt_token.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"jwt_token": ""}

def save_config(token):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"jwt_token": token}, f)

saved_data = load_config()

# --- ПАМЯТЬ СЕССИИ ---
if "jwt_token" not in st.session_state:
    st.session_state.jwt_token = saved_data.get("jwt_token", "")
if "results" not in st.session_state:
    st.session_state.results = []
if "sellers_details" not in st.session_state:
    st.session_state.sellers_details = {}

def clean_token_string(raw_str):
    """Очищает токен, если скопировали вместе со словом Bearer"""
    res = raw_str.strip()
    if res.lower().startswith("bearer "):
        res = res[7:].strip()
    return res

def clean_domain(url):
    """Очищает домен от мусора"""
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
    st.markdown("Вставь токен из вкладки Network (тот, что начинается на **eyJ...**)")
    
    input_token = st.text_input("JWT Token:", value=st.session_state.jwt_token, type="password")
    
    if st.button("💾 Сохранить токен", use_container_width=True):
        clean_token = clean_token_string(input_token)
        st.session_state.jwt_token = clean_token
        save_config(clean_token)
        st.success("Токен сохранен!")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    
    if st.button("🗑️ Сбросить токен", use_container_width=True):
        st.session_state.jwt_token = ""
        save_config("")
        st.warning("Токен удален!")
        time.sleep(1)
        st.rerun()

if st.session_state.jwt_token:
    
    # Настройки для нового внутреннего API
    headers = {
        "Authorization": f"Bearer {st.session_state.jwt_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
            status_text.info(f"Связываемся с базой... Ищем {len(new_domains)} уникальных доменов.")
            
            all_api_results = []
            chunk_size = 50 # Безопасная пачка для нового API
            
            for i in range(0, len(new_domains), chunk_size):
                chunk = new_domains[i:i + chunk_size]
                payload = {"domains": chunk}
                
                success = False
                for attempt in range(3):
                    try:
                        # Стучимся в новый секретный эндпоинт
                        response = requests.post("https://linkdetective.pro/api/domains/search", json=payload, headers=headers, timeout=20)
                        
                        if response.status_code == 200:
                            data = response.json()
                            results_list = data.get('results', [])
                            all_api_results.extend(results_list)
                            success = True
                            break 
                            
                        elif response.status_code == 429:
                            status_text.warning(f"⏳ Сервер просит паузу (429). Ждем 5 секунд... (Попытка {attempt+1}/3)")
                            time.sleep(5) 
                            continue
                            
                        elif response.status_code == 401:
                            st.error("Ошибка 401: Токен устарел. Скопируй свежий токен (eyJ...) из вкладки Network на сайте.")
                            st.stop()
                        else:
                            st.error(f"Ошибка сервера: {response.status_code}")
                            st.stop()
                            
                    except Exception as e:
                        status_text.warning(f"Сбой сети. Повтор через 5 секунд... (Попытка {attempt+1}/3)")
                        time.sleep(5)
                
                if not success:
                    st.error("Не удалось пробиться к серверу после 3 попыток. Попробуй позже.")
                    st.stop()
                    
                time.sleep(1) # Пауза между пачками
            
            if not all_api_results:
                status_text.warning("Сайт не нашел данные ни по одному из указанных доменов. (Или исчерпан лимит аккаунта).")
            else:
                results = []
                sellers_details = {}
                
                total_items = len(all_api_results)
                
                for index, item in enumerate(all_api_results):
                    domain = item.get('url', '').strip().lower()
                    if not domain: continue
                        
                    is_bought = "✅ Да" if domain in bought_domains else "❌ Нет"
                    
                    dr = item.get('dr', '')
                    traffic = item.get('traffic', '')
                    best_price = item.get('price', '')
                    
                    has_collaborator = "❌ Нет"
                    domain_sellers_clean = []
                    
                    # Парсим продавцов из нового JSON
                    raw_sellers = item.get('sellers', [])
                    for s in raw_sellers:
                        contact = str(s.get('contacts', 'Неизвестно'))
                        price = s.get('price', 0)
                        updated = str(s.get('updatedAt', ''))[:10] # Берем только дату YYYY-MM-DD
                        
                        if 'collaborator.pro' in contact.lower():
                            has_collaborator = "✅ Да"
                            
                        domain_sellers_clean.append({
                            "Продавец / Контакт": contact,
                            "Цена ($)": pd.to_numeric(price, errors='coerce'),
                            "Обновлено": updated
                        })
                        
                    sellers_details[domain] = domain_sellers_clean
                    
                    results.append({
                        "Домен": domain,
                        "Уже покупали?": is_bought,
                        "Есть на Collaborator?": has_collaborator,
                        "Цена (от)": best_price,
                        "DR": dr,
                        "Трафик": traffic
                    })
                    
                    progress_bar.progress((index + 1) / total_items)
                
                st.session_state.results = results
                st.session_state.sellers_details = sellers_details
                status_text.success(f"✅ Проверка успешно завершена! Найдено доменов: {len(results)}")

    # Отрисовка результатов
    if st.session_state.results:
        st.divider()
        filter_option = st.radio(
            "🎛️ Фильтр доменов:",
            ["Показать все", "Скрыть домены с Collaborator"],
            horizontal=True
        )
        
        filtered_results = []
        filtered_sellers = {}
        
        if filter_option == "Скрыть домены с Collaborator":
            filtered_results = [r for r in st.session_state.results if r["Есть на Collaborator?"] == "❌ Нет"]
            for r in filtered_results:
                domain = r["Домен"]
                filtered_sellers[domain] = st.session_state.sellers_details.get(domain, [])
        else:
            filtered_results = st.session_state.results
            filtered_sellers = st.session_state.sellers_details
        
        st.subheader(f"📊 Результаты ({len(filtered_results)} шт.)")
        st.dataframe(pd.DataFrame(filtered_results), use_container_width=True)
        
        st.subheader("📋 Продавцы по доменам")
        for domain, sellers in filtered_sellers.items():
            with st.expander(f"Контакты и цены: {domain}"):
                if sellers:
                    seller_df = pd.DataFrame(sellers)
                    if "Цена ($)" in seller_df.columns:
                        seller_df = seller_df.sort_values(by="Цена ($)", na_position="first").reset_index(drop=True)
                    
                    st.dataframe(
                        seller_df, 
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Цена ($)": st.column_config.NumberColumn(format="$%d")
                        }
                    )
                else:
                    st.info("Сайт не отдал данные о продавцах для этого домена.")
else:
    st.info("👈 Пожалуйста, скопируй токен (начинается на eyJ...) из панели Network и вставь слева.")
