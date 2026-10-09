import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import plotly.express as px
import uuid

SHEET_ID = st.secrets["SHEET_ID"]
MAIN_SHEET = st.secrets.get("WORKSHEET_NAME", "Sayfa1")
META_SHEET = "Meta Leadler"

DURUMLAR = [
    "Aday",
    "Tekrar aranacak",
    "Atölye randevusu alınan",
    "Atölye randevusuna gelmeyen",
    "Atölye üyeliği yapılan"
]

@st.cache_resource
def get_gspread_client():
    service_account_info = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return gspread.authorize(creds)

def load_sheet(sheet_name):
    client = get_gspread_client()
    sh = client.open_by_key(SHEET_ID)
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df, worksheet
    except Exception:
        return pd.DataFrame(), None

def save_dataframe(df, worksheet):
    if worksheet is None:
        return
    worksheet.clear()
    df = df.fillna("")
    worksheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

st.set_page_config(page_title="Kilo Verme Programı Takip", page_icon="⚖️", layout="wide")
st.title("⚖️ Kilo Verme Programı Başvuru Takip Sistemi")

menu = st.sidebar.radio("Menü", [
    "📊 Dashboard",
    "📋 Liste",
    "➕ Yeni Kayıt / Düzenle",
    "🔍 Detay Görüntüle",
    "📥 Meta Leadler"
])

df, worksheet = load_sheet(MAIN_SHEET)

if menu == "📊 Dashboard":
    st.header("Dashboard")
    if df.empty:
        st.info("Henüz hiç kayıt yok.")
    else:
        counts = df["Durum"].value_counts()
        cols = st.columns(5)
        for i, durum in enumerate(DURUMLAR):
            with cols[i]:
                st.metric(durum, int(counts.get(durum, 0)))
        st.subheader("Durum Dağılımı")
        fig = px.pie(names=counts.index, values=counts.values, title="Başvuru Durumları",
                     color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Son Eklenen 10 Kişi")
        st.dataframe(df.tail(10), use_container_width=True)

elif menu == "📋 Liste":
    st.header("Başvuru Listesi")
    if df.empty:
        st.info("Henüz kayıt yok.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            durum_filtre = st.multiselect("Duruma göre filtrele", DURUMLAR, default=DURUMLAR)
        with col2:
            arama = st.text_input("İsim veya Soyisim ara")
        filtered = df[df["Durum"].isin(durum_filtre)]
        if arama:
            filtered = filtered[
                filtered["İsim"].astype(str).str.contains(arama, case=False, na=False) |
                filtered["Soyisim"].astype(str).str.contains(arama, case=False, na=False)
            ]
        st.dataframe(filtered, use_container_width=True, height=500)
        st.caption(f"Toplam **{len(filtered)}** kayıt gösteriliyor")

elif menu == "➕ Yeni Kayıt / Düzenle":
    st.header("Yeni Kayıt veya Mevcut Kaydı Düzenle")
    if not df.empty:
        secenekler = ["Yeni Kayıt"] + [f"{row['İsim']} {row['Soyisim']} (ID: {row['ID']})" for _, row in df.iterrows()]
        secim = st.selectbox("Kayıt seç (veya Yeni Kayıt)", secenekler)
    else:
        secim = "Yeni Kayıt"
    if secim == "Yeni Kayıt":
        mevcut = None
        id_val = str(uuid.uuid4())[:8].upper()
        kayit_tarihi = datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        id_val = secim.split("ID: ")[1].rstrip(")")
        mevcut = df[df["ID"] == id_val].iloc[0]
        kayit_tarihi = mevcut["Kayıt Tarihi"]
    with st.form("kayit_formu"):
        col1, col2 = st.columns(2)
        with col1:
            isim = st.text_input("İsim *", value=str(mevcut["İsim"]) if mevcut is not None else "")
            soyisim = st.text_input("Soyisim *", value=str(mevcut["Soyisim"]) if mevcut is not None else "")
            boy = st.number_input("Boy (cm)", min_value=0, max_value=250,
                                  value=int(mevcut["Boy"]) if mevcut is not None and str(mevcut["Boy"]).replace(".","").isdigit() else 0)
            yas = st.number_input("Yaş", min_value=0, max_value=100,
                                  value=int(mevcut["Yaş"]) if mevcut is not None and str(mevcut["Yaş"]).isdigit() else 0)
        with col2:
            kilo = st.number_input("Kilo (kg)", min_value=0.0, max_value=300.0, step=0.1,
                                   value=float(mevcut["Kilo"]) if mevcut is not None and str(mevcut["Kilo"]).replace(".","").isdigit() else 0.0)
            durum = st.selectbox("Durum", DURUMLAR, index=DURUMLAR.index(mevcut["Durum"]) if mevcut is not None else 0)
            notlar = st.text_area("Notlar", value=str(mevcut["Notlar"]) if mevcut is not None else "", height=140)
        submitted = st.form_submit_button("💾 Kaydet / Güncelle", use_container_width=True)
        if submitted:
            if not isim.strip() or not soyisim.strip():
                st.error("İsim ve Soyisim zorunludur!")
            else:
                yeni_kayit = {
                    "ID": id_val,
                    "İsim": isim.strip(),
                    "Soyisim": soyisim.strip(),
                    "Boy": boy if boy > 0 else "",
                    "Yaş": yas if yas > 0 else "",
                    "Kilo": kilo if kilo > 0 else "",
                    "Durum": durum,
                    "Notlar": notlar.strip(),
                    "Kayıt Tarihi": kayit_tarihi,
                    "Son Güncelleme": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                if mevcut is not None:
                    for key, value in yeni_kayit.items():
                        df.loc[df["ID"] == id_val, key] = value
                    st.success(f"✅ {isim} {soyisim} güncellendi.")
                else:
                    df = pd.concat([df, pd.DataFrame([yeni_kayit])], ignore_index=True)
                    st.success(f"✅ {isim} {soyisim} eklendi.")
                save_dataframe(df, worksheet)
                st.cache_resource.clear()
                st.rerun()

elif menu == "🔍 Detay Görüntüle":
    st.header("Kişi Detayı")
    if df.empty:
        st.info("Henüz kayıt yok.")
    else:
        secenekler = [f"{row['İsim']} {row['Soyisim']} (ID: {row['ID']})" for _, row in df.iterrows()]
        secim = st.selectbox("Kişi seç", secenekler)
        id_val = secim.split("ID: ")[1].rstrip(")")
        kisi = df[df["ID"] == id_val].iloc[0]
        st.subheader(f"{kisi['İsim']} {kisi['Soyisim']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Boy", f"{kisi['Boy']} cm" if kisi['Boy'] else "-")
        c2.metric("Yaş", kisi["Yaş"] if kisi["Yaş"] else "-")
        c3.metric("Kilo", f"{kisi['Kilo']} kg" if kisi['Kilo'] else "-")
        c4.metric("Durum", kisi["Durum"])
        st.write(f"**Kayıt Tarihi:** {kisi['Kayıt Tarihi']}")
        st.write(f"**Son Güncelleme:** {kisi['Son Güncelleme']}")
        st.markdown("### Notlar")
        st.info(kisi["Notlar"] if kisi["Notlar"] else "Not yok")

elif menu == "📥 Meta Leadler":
    st.header("Meta Leadler")
    meta_df, meta_ws = load_sheet(META_SHEET)
    if meta_df.empty:
        st.warning("Meta Leadler sayfası boş veya henüz lead gelmemiş.")
        st.info("Meta Business Suite → Instant Forms → CRM Setup → Google Sheets bağlantısını kontrol et.")
    else:
        st.success(f"Toplam **{len(meta_df)}** Meta lead bulundu.")
        st.dataframe(meta_df, use_container_width=True, height=400)
        st.markdown("---")
        st.subheader("Seçili Lead’i Aday Olarak Ekle")
        lead_options = [f"Satır {i+1} - {row.get('full_name', row.get('first_name', 'İsimsiz'))}" for i, row in meta_df.iterrows()]
        secilen = st.selectbox("Eklenecek lead’i seç", lead_options)
        secilen_index = lead_options.index(secilen)
        lead = meta_df.iloc[secilen_index]
        full_name = str(lead.get("full_name", lead.get("first_name", "")))
        isim_parts = full_name.strip().split(" ", 1)
        isim = isim_parts[0] if isim_parts else ""
        soyisim = isim_parts[1] if len(isim_parts) > 1 else ""
        not_listesi = []
        for col in meta_df.columns:
            val = lead.get(col, "")
            if val and col not in ["full_name", "first_name", "last_name"]:
                not_listesi.append(f"{col}: {val}")
        notlar_text = " | ".join(not_listesi)
        with st.form("meta_aktar"):
            st.write(f"**Seçilen:** {full_name}")
            yeni_isim = st.text_input("İsim", value=isim)
            yeni_soyisim = st.text_input("Soyisim", value=soyisim)
            yeni_notlar = st.text_area("Notlar (otomatik dolduruldu)", value=notlar_text, height=120)
            aktar = st.form_submit_button("✅ Aday Olarak Ana Listeye Ekle", use_container_width=True)
            if aktar:
                if not yeni_isim.strip():
                    st.error("İsim zorunludur!")
                else:
                    yeni_kayit = {
                        "ID": "META-" + str(uuid.uuid4())[:6].upper(),
                        "İsim": yeni_isim.strip(),
                        "Soyisim": yeni_soyisim.strip(),
                        "Boy": "",
                        "Yaş": "",
                        "Kilo": "",
                        "Durum": "Aday",
                        "Notlar": yeni_notlar.strip(),
                        "Kayıt Tarihi": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Son Güncelleme": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    df = pd.concat([df, pd.DataFrame([yeni_kayit])], ignore_index=True)
                    save_dataframe(df, worksheet)
                    st.success(f"✅ {yeni_isim} {yeni_soyisim} Aday olarak eklendi!")
                    st.cache_resource.clear()
                    st.rerun()