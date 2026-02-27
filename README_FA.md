# GhostPayments — پردازشگر پرداخت کریپتو (سلف‌هاستد)

**[📖 English](README.md)**

GhostPayments یک پردازشگر پرداخت کریپتو سلف‌هاستد و غیرامانی برای زنجیره‌های BSC و Polygon است. این سیستم آدرس‌های واریز یکتا از منمونیک کیف‌پول شما می‌سازد، پرداخت‌های ورودی را از طریق RPC عمومی رصد می‌کند، و وجوه را به صورت خودکار به کیف‌پول اصلی شما منتقل می‌کند — با استفاده از یک کیف‌پول کارمزد جداگانه برای پوشش گس، بدون نیاز به دخالت دستی.

## ویژگی‌ها

* **بدون نیاز به نود کامل** — از RPC عمومی BSC و Polygon استفاده می‌کند
* **غیرامانی** — وجوه مستقیماً به کیف‌پول شما می‌رسند؛ سرور هیچ‌گاه آن‌ها را نگه نمی‌دارد
* **مشتق‌سازی HD کیف‌پول** — آدرس‌های فرزند BIP-44 از منمونیک؛ برای هر فاکتور یک آدرس یکتا
* **شارژ خودکار گس** — کیف‌پول کارمزد (BNB/POL) پیش از جاروب کردن توکن‌ها، گس لازم را ارسال می‌کند
* **چندزنجیره، چندتوکن** — USDT BEP-20، USDT Polygon، BNB، POL
* **وب‌هوک** — در هنگام تأیید پرداخت، POST به سرور شما ارسال می‌شود
* **مسیرهای URI مخفی** — پنل ادمین و صفحات پرداخت روی مسیرهای مخفی قرار دارند؛ سایر URLها خطای 404 خالی برمی‌گردانند
* **پنل تنظیمات ادمین** — مسیرها، کیف‌پول‌ها، RPC و کلیدهای API را مستقیماً از مرورگر تنظیم کنید
* **رابط پرداخت زیبا** — QR کد، تایمر شمارش معکوس زنده، انیمیشن‌های وضعیت
* **به‌روزرسانی خودکار** — در استارت‌آپ و در پس‌زمینه آخرین نسخه GitHub را بررسی می‌کند
* **نصب آسان** — اسکریپت تنظیم تک‌دستوری با راهنمای تعاملی
* **پشتیبانی از Docker** — با یک `docker-compose up` اجرا می‌شود

## نصب سریع

### مرحله ۱: نصب GhostPayments

```bash
wget https://raw.githubusercontent.com/FrenchToblerone54/ghostpayments/main/scripts/install.sh -O install.sh
chmod +x install.sh
sudo ./install.sh
```

نصاب به صورت خودکار:
- باینری از آخرین نسخه GitHub دانلود و hash SHA-256 آن تأیید می‌شود
- منمونیک کیف‌پول اصلی، کیف‌پول کارمزد، و آدرس مقصد را می‌پرسد
- URLهای RPC (یا مقادیر پیش‌فرض عمومی) را می‌پرسد
- `ADMIN_PATH` و `PAYMENT_PATH` مخفی را با `ghostpayments --generate-token` به صورت خودکار می‌سازد
- تنظیمات را در `/etc/ghostpayments/.env` ذخیره می‌کند
- سرویس systemd را نصب و راه‌اندازی می‌کند
- آدرس پنل ادمین را در یک کادر نمایش می‌دهد — آن را ذخیره کنید، دیگر نمایش داده نخواهد شد

### مرحله ۲: ورود به پنل ادمین

آدرس پنل ادمین در انتهای نصب نمایش داده می‌شود:

```
https://your-server/{ADMIN_PATH}/
```

از پنل ادمین می‌توانید:
- تمام فاکتورها و وضعیت آن‌ها را مشاهده کنید
- موجودی کیف‌پول کارمزد و اصلی را رصد کنید
- **کلیدهای API بسازید و باطل کنید**
- **مسیرها، کیف‌پول‌ها، و RPC را از صفحه تنظیمات تغییر دهید**

### مرحله ۳: ساخت فاکتور از طریق API

```bash
curl -X POST https://your-server/{PAYMENT_PATH}/api/invoice \
  -H "X-GhostPay-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "BSC",
    "token": "USDT",
    "amount_native": "10.00",
    "webhook_url": "https://yourapp.com/webhook/crypto",
    "metadata": {"order_id": "abc123"}
  }'
```

`payment_url` برگشتی را به مشتری ارسال کنید. GhostPayments بقیه کار را انجام می‌دهد.

## معماری

```
[مرورگر مشتری]
       │
       │  GET /{PAYMENT_PATH}/pay/<invoice_id>
       ▼
[سرور GhostPayments]
       │
       ├── آدرس واریز یکتا از MAIN_MNEMONIC مشتق می‌شود (BIP-44)
       │
       ├── APScheduler هر ۲۰ ثانیه RPC عمومی را بررسی می‌کند
       │
       │  پرداخت شناسایی شد ─────────────────────────────────────┐
       │                                                            │
       │  [کیف‌پول کارمزد] ─── تراکنش گس ──────►  [آدرس واریز]
       │                                                            │
       │                                              تراکنش جاروب │
       │                                                            ▼
       │                                              [کیف‌پول اصلی]
       │
       └── POST وب‌هوک → سرور شما
```

**جریان پرداخت:**

1. اپلیکیشن شما `POST /api/invoice` را با زنجیره، توکن، و مقدار فراخوانی می‌کند
2. GhostPayments یک آدرس فرزند HD یکتا مشتق می‌کند (ایندکس در DB ذخیره می‌شود)
3. مشتری کریپتو به آدرس واریز ارسال می‌کند
4. مانیتور تراکنش ورودی را روی بلاکچین شناسایی می‌کند
5. برای پرداخت‌های توکنی (USDT): کیف‌پول کارمزد ابتدا گس به آدرس واریز ارسال می‌کند
6. آدرس واریز موجودی کامل را به کیف‌پول اصلی جاروب می‌کند
7. فاکتور `completed` می‌شود، وب‌هوک به سرور شما ارسال می‌شود

**کلیدهای خصوصی فقط در حافظه و فقط در طول عملیات جاروب مشتق می‌شوند و هیچ‌گاه ذخیره نمی‌شوند.**

## تنظیمات

### فایل `.env`

```env
# ── کیف‌پول‌ها ──────────────────────────────────────────────────────────────
MAIN_MNEMONIC="word1 word2 word3 ... word12"

# کیف‌پول کارمزد: یکی از دو گزینه زیر را انتخاب کنید
# گزینه الف — منمونیک (ایندکس ۰ به عنوان کیف‌پول کارمزد استفاده می‌شود)
FEE_MNEMONIC="word1 word2 word3 ... word12"
# گزینه ب — کلید خصوصی مستقیم (اگر تنظیم شود، اولویت دارد)
FEE_PRIVATE_KEY=

# آدرس مقصد — اگر خالی باشد، از ایندکس ۰ منمونیک اصلی مشتق می‌شود
MAIN_WALLET_ADDRESS=

# ── RPC ────────────────────────────────────────────────────────────────────
BSC_RPC_URL=https://bsc-dataseed.binance.org
POLYGON_RPC_URL=https://polygon-rpc.com

# ── مسیرهای URI (مانند رمز عبور با آن‌ها رفتار کنید) ──────────────────────
# برای غیرفعال کردن امنیت مسیر، خالی بگذارید (سرویس از / ارائه می‌شود)
ADMIN_PATH=aBcDeFgHiJkLmNoPqRsT
PAYMENT_PATH=pQrStUvWxYzAbCdEfGhIj

# ── به‌روزرسانی خودکار ───────────────────────────────────────────────────
AUTO_UPDATE=true
UPDATE_CHECK_INTERVAL=300
UPDATE_CHECK_ON_STARTUP=true
UPDATE_HTTP_PROXY=
UPDATE_HTTPS_PROXY=

# ── تنظیمات دقیق (اختیاری) ────────────────────────────────────────────────
INVOICE_TTL_MINUTES=30
BSC_CONFIRMATIONS=3
POLYGON_CONFIRMATIONS=1
GAS_BUFFER_PERCENT=20
POLL_INTERVAL_SECONDS=20
PORT=5000
```

### دستورات CLI

```bash
ghostpayments                    # راه‌اندازی سرور
ghostpayments update             # به‌روزرسانی دستی
ghostpayments --version          # نمایش نسخه جاری
ghostpayments --generate-token   # تولید توکن nanoid(20) جدید
ghostpayments --help             # راهنما
```

## توکن‌های پشتیبانی‌شده

| توکن | زنجیره | قرارداد |
|---|---|---|
| USDT | BSC (BEP-20) | `0x55d398326f99059fF775485246999027B3197955` |
| USDT | Polygon | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` |
| BNB | BSC | نیتیو |
| POL | Polygon | نیتیو |

## مرجع API

تمام endpointها زیر پیشوند `/{PAYMENT_PATH}/api/` قرار دارند.

### `POST /{PAYMENT_PATH}/api/invoice` — ساخت فاکتور

هدر `X-GhostPay-Key` لازم است.

```json
{
  "chain": "BSC",
  "token": "USDT",
  "amount_native": "10.00",
  "amount_usd": 10.00,
  "webhook_url": "https://yourapp.com/webhook",
  "metadata": {"order_id": "abc123"}
}
```

پاسخ `201`:
```json
{
  "invoice_id": "V3mKpXq2nLwRtY8uZe5A",
  "deposit_address": "0x...",
  "payment_url": "https://yourhost/{PAYMENT_PATH}/pay/V3mKpXq2nLwRtY8uZe5A",
  "expires_at": "2025-01-01T12:30:00Z",
  "status": "pending"
}
```

### `GET /{PAYMENT_PATH}/api/invoice/<id>` — وضعیت فاکتور

بدون نیاز به احراز هویت. توسط صفحه پرداخت برای polling زنده استفاده می‌شود.

### `POST /{PAYMENT_PATH}/api/invoice/<id>/cancel` — لغو فاکتور

فاکتور `pending` را به `expired` تبدیل می‌کند. نیازمند کلید API.

### `GET /{PAYMENT_PATH}/api/invoices` — لیست فاکتورها

با فیلترهای `status`، `chain`، `token` و صفحه‌بندی. نیازمند کلید API.

### وب‌هوک

```json
{
  "invoice_id": "V3mKpXq2nLwRtY8uZe5A",
  "status": "completed"
}
```

## وضعیت‌های فاکتور

| وضعیت | توضیح |
|---|---|
| `pending` | در انتظار پرداخت مشتری |
| `confirming` | پرداخت شناسایی شد، در انتظار تأییدیه‌های بلاک |
| `sweeping` | گس شارژ شد، در حال انتقال به کیف‌پول اصلی |
| `completed` | وجوه منتقل شدند، وب‌هوک ارسال شد |
| `expired` | TTL فاکتور منقضی شد |
| `failed` | عملیات جاروب ناموفق بود |

## امنیت

1. **منمونیک‌ها ذخیره نمی‌شوند** — فقط در استارت‌آپ از `.env` خوانده می‌شوند
2. **کلیدهای خصوصی فقط در حافظه** — در هر عملیات جاروب مشتق می‌شوند و هیچ‌گاه ذخیره نمی‌شوند
3. **مشتق‌سازی HD** — هر فاکتور یک آدرس فرزند یکتا دارد
4. **هشینگ کلیدهای API** — کلیدها به صورت SHA-256 ذخیره می‌شوند؛ متن ساده فقط یک‌بار نمایش داده می‌شود
5. **امنیت مسیر URI** — پیشوندهای `nanoid(20)` مخفی؛ تمام مسیرهای دیگر خطای `404` خالی برمی‌گردانند
6. **فیلدهای منمونیک write-only در UI** — هیچ‌گاه در پاسخ HTML از پیش پر نمی‌شوند
7. **از HTTPS استفاده کنید** — همیشه پشت nginx با TLS اجرا کنید

## Docker

```bash
git clone https://github.com/FrenchToblerone54/ghostpayments
cd ghostpayments
cp .env.example .env
nano .env
docker-compose up -d
```

## مدیریت systemd

```bash
sudo systemctl start ghostpayments
sudo systemctl stop ghostpayments
sudo systemctl restart ghostpayments
sudo systemctl status ghostpayments
sudo journalctl -u ghostpayments -f
```

## ساخت از سورس

```bash
git clone https://github.com/FrenchToblerone54/ghostpayments
cd ghostpayments
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python3.13 init_db.py
python3.13 run.py
```

## لایسنس

MIT License

## کانال تلگرام

[@GhostSoftDev](https://t.me/GhostSoftDev)
