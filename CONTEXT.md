# Wolter AMT — domen tili

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Wolter AMT pullik Meta reklamasini boshqaradi. Sotuv va ijara alohida biznes natijalari va imkoniyatlari bilan baholanadi. Bu fayl biznes atamalarining qisqa ta’riflari; texnik atamalar, holat lug‘ati va qisqartmalar — [GLOSSARY](10_Reference/GLOSSARY.md). Kanonik biznes semantikasi — [BUSINESS_CONTRACT](11_Production_Contracts/BUSINESS_CONTRACT.md).

## Biznes atamalari

**Qualified lead**: Call-center bog‘langan, kuryerligi va 30 kun ichida sotib olish yoki ijara niyati tasdiqlangan murojaat (Q16 ✅).
_Avoid_: Forma yuborilishi, har qanday lead.

**Shartnoma**: Sotuv yoki ijara majburiyatining tasdiqlangan kelishuvi. Shartnoma tuzilishi pul tushgani yoki mahsulot topshirilganini bildirmaydi.
_Avoid_: To‘lov, tushum.

**Tushgan pul**: Haqiqatan qabul qilingan mablag‘. Depozit, daromad va bo‘lib to‘lash majburiyati o‘z iqtisodiy ma’nosida alohida yuradi.
_Avoid_: Shartnoma summasi, hisoblangan daromad.

**Yangi ijara**: Yangi ijara munosabatining boshlanishi; mavjud ijarani uzaytirishdan ajratiladi.
_Avoid_: Barcha oylik tranzaksiyalar.

**Uzaytirish**: Mavjud ijara davrining davom ettirilishi. Yangi acquisition sifatida sanalmaydi.
_Avoid_: Yangi mijoz.

**Fizik park**: Muayyan vaqtdagi velosipedlar to‘plami. Tranzaksiya/oy bu to‘plamning soni emas.
_Avoid_: 600 oylik tranzaksiyani 600 velosiped deb olish.

**Ishga yaroqli park**: Ijarada, rezervda yoki topshirishga tayyor bo‘lgan velosipedlar; texnik xizmatdagilar alohida.
_Avoid_: Jami sotib olingan park.

**Amaldagi waitlist**: Takrordan tozalangan, hozirgi ijara niyati va mosligi tasdiqlangan kutayotgan talab. Haqiqat manbai ⧗ OD-07.
_Avoid_: Barcha tarixiy navbat yozuvlari.

**Capacity hold**: Bugungi yaroqli park ma’lumoti bo‘lmagan kuni oddiy ijara byudjeti o‘zgarmasligi. Protective controls bundan mustaqil ishlaydi.
_Avoid_: Avtomatik ads pauza, faqat oshirishni bloklash.

**Boshqariladigan obyekt**: Owner AMT boshqaruviga aniq topshirgan kampaniya, ad set yoki ad (`managed_entities`).
_Avoid_: Akkauntdagi barcha obyektlar.

**Takeover**: Insondan AMT’ga belgilangan obyektlar boshqaruvini o‘tkazish (`takeover_scope_change`, HG-F6-04).
_Avoid_: Landing trafik migratsiyasi.

**Human handback**: AMT yozishi yopilib, mas’ul inson reklama boshqaruvini qabul qilgani dalili bilan (`handback_acks`).
_Avoid_: Faqat Telegram alert yuborish.

**Faol offer revision**: Muayyan vaqtda amal qiladigan tasdiqlangan narx, shart va va’dalar nusxasi.
_Avoid_: O‘zgartiriladigan fayl nomining o‘zi.

**Yetilgan kogorta**: Tanlangan leadlar guruhining kelishilgan natija oynasi yetarlicha kuzatilgan qismi.
_Avoid_: Shunchaki ikki kalendar hafta.

## Boshqaruv atamalari

**Protective control**: Owner oldindan tasdiqlagan, faqat xavfni kamaytiradigan deterministik harakat (masalan, managed entity’larni pauza qilish). Ads Manager spending limit’ning o‘rnini bosmaydi.
_Avoid_: Kill switch, avtonom qaror.

**Workflow run**: Muayyan biznes yoki operatsion jarayonning bir ishga tushirilishi; holati workflow runtime’da saqlanadi.
_Avoid_: Paperclip issue holati.

**Handoff**: Bir qadam natijasini keyingi egaga topshirish; qabul qiluvchi uni tekshirib qabul qiladi yoki sabab bilan rad etadi.
_Avoid_: Issue’ni boshqa agentga biriktirish.

**Candidate**: Tizimni yaxshilash uchun sandbox’da tayyorlangan o‘zgarish; manifest digest’i bilan aniqlanadi.
_Avoid_: Branch nomi, "tayyor kod".

**Release tasdig‘i**: Owner’ning aniq manifest digest’iga bog‘langan qarori (`release_approvals`) va imzolangan `release-*` tag.
_Avoid_: Faqat tag yaratish, merge.
