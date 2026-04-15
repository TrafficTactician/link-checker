import streamlit as st
import requests
import pandas as pd
import time
import json
import ast
import os
import re
import urllib.parse

st.set_page_config(page_title="Link Checker Pro", layout="wide")

# --- СОХРАНЕНИЕ КУК В ФАЙЛ ---
CONFIG_FILE = "cookies.json"

def load_cookies():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"csrf_token": "", "xsrf_token": "", "session_cookie": ""}

def save_cookies(csrf, xsrf, session):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"csrf_token": csrf, "xsrf_token": xsrf, "session_cookie": session}, f)

saved_data = load_cookies()

# --- ПАМЯТЬ СЕССИИ ---
if "csrf_token" not in st.session_state:
    st.session_state.csrf_token = saved_data.get("csrf_token", "")
if "xsrf_token" not in st.session_state:
    st.session_state.xsrf_token = saved_data.get("xsrf_token", "")
if "session_cookie" not in st.session_state:
    st.session_state.session_cookie = saved_data.get("session_cookie", "")
if "results" not in st.session_state:
    st.session_state.results = []
if "sellers_details" not in st.session_state:
    st.session_state.sellers_details = {}

def clean_cookie_string(raw_str, prefix=None):
    res = raw_str.strip()
    if prefix and res.startswith(prefix + "="):
        res = res.replace(prefix + "=", "", 1)
    res = res.split(';')[0].strip()
    return res

def clean_domain(url):
    url = url.strip().lower()
    if not url: return ""
    url = re.sub(r'^https?://', '', url)
    url = url.split('/')[0]
    if url.startswith('www.'):
        url = url[4:]
    return url

def get_sellers_for_domain(domain, headers, cookies, csrf_token):
    url = "https://linkdetective.pro/api/domains"
    payload = {
        "draw": 1, "start": 0, "length": 10,
        "_token": csrf_token, "domains": [domain],
        "price": "min", "blacklist": [2, 8]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, cookies=cookies, timeout=15)
        if response.status_code == 200:
            data = response.json()
            sellers = data.get('sellers', {})
            if isinstance(sellers, dict):
                for k, v in sellers.items():
                    if domain in k.lower():
                        return v
            elif isinstance(sellers, list):
                return sellers
    except Exception:
        pass
    return []

def extract_dicts(data):
    extracted = []
    if isinstance(data, str):
        data = data.strip()
        try:
            parsed = json.loads(data)
            return extract_dicts(parsed)
        except Exception:
            try:
                parsed = ast.literal_eval(data)
                return extract_dicts(parsed)
            except Exception:
                pass
                
    if isinstance(data, dict):
        extracted.append(data)
    elif isinstance(data, list):
        for item in data:
            extracted.extend(extract_dicts(item))
    return extracted

def clean_sellers_data(raw_data):
    cleaned_list = []
    dicts = extract_dicts(raw_data)
    
    for d in dicts:
        seller_name = d.get("contacts", d.get("seller", d.get("Seller", "Неизвестно")))
        price = d.get("price", d.get("Price", 0))
        date = d.get("date", d.get("update", d.get("Update", "")))
        
        cleaned_list.append({
            "Продавец / Контакт": str(seller_name),
            "Цена ($)": pd.to_numeric(price, errors='coerce'), 
            "Обновлено": str(date)
        })
    return cleaned_list

# --- ИНТЕРФЕЙС ---
st.title("🕵️‍♂️ Link Checker Pro (Аутрич)")

with st.sidebar:
    st.header("🔑 Авторизация")
    st.markdown("Вставь 3 ключа из **одной активной сессии**.")
    
    input_csrf = st.text_input("1. CSRF-TOKEN (из кода):", value=st.session_state.csrf_token, type="password")
    input_xsrf = st.text_input("2. XSRF-TOKEN (из Cookies):", value=st.session_state.xsrf_token, type="password")
    input_session = st.text_input("3. linkdetective_session:", value=st.session_state.session_cookie, type="password")
    
    if st.button("💾 Сохранить доступы", use_container_width=True):
        clean_csrf = clean_cookie_string(input_csrf)
        clean_xsrf = clean_cookie_string(input_xsrf, "XSRF-TOKEN")
        clean_session = clean_cookie_string(input_session, "linkdetective_session")
        
        st.session_state.csrf_token = clean_csrf
        st.session_state.xsrf_token = clean_xsrf
        st.session_state.session_cookie = clean_session
        save_cookies(clean_csrf, clean_xsrf, clean_session)
        
        st.success("Все 3 ключа сохранены!")
        time.sleep(1)
        st.rerun()
        
    st.divider()
    
    # НОВАЯ КНОПКА ДЛЯ СБРОСА ЗАЛИПШИХ КЛЮЧЕЙ
    if st.button("🗑️ Сбросить старые ключи", use_container_width=True):
        st.session_state.csrf_token = ""
        st.session_state.xsrf_token = ""
        st.session_state.session_cookie = ""
        save_cookies("", "", "")
        st.warning("Ключи удалены! Вставь новые.")
        time.sleep(1)
        st.rerun()

if st.session_state.csrf_token and st.session_state.xsrf_token and st.session_state.session_cookie:
    
    raw_xsrf = urllib.parse.unquote(st.session_state.xsrf_token)
    cookies = {
        "XSRF-TOKEN": st.session_state.xsrf_token,
        "linkdetective_session": st.session_state.session_cookie
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-CSRF-TOKEN": st.session_state.csrf_token, 
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://linkdetective.pro/"
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
        new_domains = list(dict.fromkeys(new_domains))
        
        if not new_domains:
            st.warning("Введи домены для проверки.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.info(f"Связываемся с базой... Ищем {len(new_domains)} уникальных доменов.")
            
            all_items = []
            all_sellers_data_initial = {}
            chunk_size = 20 
            
            for i in range(0, len(new_domains), chunk_size):
                chunk = new_domains[i:i + chunk_size]
                
                payload = {
                    "draw": 1, "start": 0, "length": 100, 
                    "_token": st.session_state.csrf_token, "domains": chunk,
                    "price": "min", "blacklist": [2, 8]
                }
                
                success = False
                for attempt in range(3):
                    try:
                        response = requests.post("https://linkdetective.pro/api/domains", json=payload, headers=headers, cookies=cookies, timeout=20)
                        
                        if response.status_code == 200:
                            data = response.json()
                            chunk_items = data.get('data', [])
                            if chunk_items:
                                all_items.extend(chunk_items)
                            chunk_sellers = data.get('sellers', {})
                            if isinstance(chunk_sellers, dict):
                                all_sellers_data_initial.update(chunk_sellers)
                            success = True
                            break 
                            
                        elif response.status_code == 429:
                            status_text.warning(f"⏳ Сервер просит притормозить (Ошибка 429). Ждем 10 секунд... (Попытка {attempt+1}/3)")
                            time.sleep(10) 
                            continue
                            
                        elif response.status_code == 419:
                            st.error("Ошибка 419: Токен отторгается. Нажми 'Сбросить старые ключи' слева и вставь свежие из окна Инкогнито.")
                            st.stop()
                        else:
                            st.error(f"Ошибка сервера: {response.status_code}")
                            st.stop()
                            
                    except Exception as e:
                        status_text.warning(f"Сбой сети. Повтор через 5 секунд... (Попытка {attempt+1}/3)")
                        time.sleep(5)
                
                if not success:
                    st.error("Не удалось пробиться через защиту сервера после 3 попыток. Попробуй позже.")
                    st.stop()
                    
                time.sleep(1.5)
            
            total_items = len(all_items)
            if total_items == 0:
                status_text.warning("Сайт не нашел данные ни по одному из указанных доменов. Возможно, сработал лимит аккаунта.")
            else:
                results = []
                sellers_details = {} 
                
                for index, item in enumerate(all_items):
                    if not isinstance(item, dict): continue
                        
                    domain = str(item.get('Domain', '')).strip().lower()
                    status_text.info(f"Сбор контактов ({index + 1} из {total_items}): {domain}")
                    is_bought = "✅ Да" if domain in bought_domains else "❌ Нет"
                    
                    domain_sellers_raw = []
                    if isinstance(all_sellers_data_initial, dict):
                        for k, v in all_sellers_data_initial.items():
                            if domain in k.lower():
                                domain_sellers_raw = v
                                break
                    
                    if not domain_sellers_raw:
                        domain_sellers_raw = get_sellers_for_domain(domain, headers, cookies, st.session_state.csrf_token)
                        time.sleep(0.5) 
                    
                    domain_sellers_clean = clean_sellers_data(domain_sellers_raw)
                    sellers_details[domain] = domain_sellers_clean
                    
                    has_collaborator = "❌ Нет"
                    raw_string = str(domain_sellers_raw).lower()
                    if 'collaborator.pro' in raw_string:
                        has_collaborator = "✅ Да"
                    
                    results.append({
                        "Домен": domain,
                        "Уже покупали?": is_bought,
                        "Есть на Collaborator?": has_collaborator,
                        "Цена (от)": item.get('Price', ''),
                        "DR": item.get('DR', ''),
                        "Трафик": item.get('Traffic', '')
                    })
                    progress_bar.progress((index + 1) / total_items)
                
                st.session_state.results = results
                st.session_state.sellers_details = sellers_details
                status_text.success(f"✅ Проверка успешно завершена! Обработано доменов: {total_items}")

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
                filtered_sellers[domain] = st.session_state.sellers_details[domain]
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
                        seller_df = seller_df.sort_values(by="Цена ($)", na_position="last").reset_index(drop=True)
                    
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
    st.info("👈 Пожалуйста, введи 3 ключа доступа в левом меню, чтобы начать работу.")
