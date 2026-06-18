import flet as ft
import metpy.calc as mpcalc
from metpy.units import units
import numpy as np
import requests
from datetime import datetime

def main(page: ft.Page):
    page.title = "METKUL PREMIUM"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.scroll = "adaptive"

    # --- UI ELEMANLARI ---
    title_text = ft.Text("METKUL", size=28, weight="bold", italic=True, color="#ffb300")
    ent_city = ft.TextField(label="Lokasyon Girişi", value="Bornova", expand=True)
    
    # Blok 1: Hava Rejimi Tahmini
    lbl_card1_val = ft.Text("Veri Bekleniyor...", size=14, color="white")
    card_status = ft.Container(
        content=ft.Column([
            ft.Text("HAVA REJİMİ TAHMİNİ", size=14, weight="bold", color="#ffb300"),
            lbl_card1_val
        ]),
        padding=15, bgcolor="#1a1a1a"
    )

    # Blok 2: MetPy Seviyeleri
    lbl_card2_val = ft.Text("LCL: --\nCCL: --\nCAPE: --\nCIN: --\nLI: --", size=13)
    card_metpy = ft.Container(
        content=ft.Column([
            ft.Text("METPY PARAMETRİK SEVİYELER", size=14, weight="bold", color="#1f77b4"),
            lbl_card2_val
        ]),
        padding=15, bgcolor="#1a1a1a"
    )

    # Blok 3: Saatlik Trend Paneli (Yağış duruyor, Nem ve CAPE eklendi)
    trend_container = ft.Container(
        content=ft.Column([
            ft.Text("Mevcut Saatten İtibaren 24 Saatlik Akış", size=14, weight="bold", color="#00ff00"),
            ft.Text("Analiz başlatıldığında saatlik gidişat burada listelenecektir.", size=12, italic=True)
        ]),
        padding=15, bgcolor="#1a1a1a"
    )

    # Blok 4: Sayısal Matris ve Ekstrem Rapor
    txt_numeric_summary = ft.TextField(multiline=True, read_only=True, min_lines=4, max_lines=6, text_size=12)
    txt_numeric_table = ft.TextField(multiline=True, read_only=True, min_lines=26, text_size=11)
    txt_extreme_report = ft.TextField(multiline=True, read_only=True, min_lines=15, text_size=12, color="#00ff00", bgcolor="#0a0a0a")

    # --- METEOROLOJİK MATRİS HESAPLAMALARI ---
    def calculate_extreme_probabilities(t, rh, td, ws_kmh, cape_val, li_val):
        probs = {}
        t_td_diff = t - td
        
        storm_score = (cape_val / 40.0) - (li_val * 6.0) + ((rh - 50) * 0.4)
        if t > 18: storm_score += 10
        if t_td_diff <= 4: storm_score += 15
        probs["Şiddetli Oraj & Yıldırım"] = min(max(int(storm_score), 5), 98)

        hail_score = 0
        if t > 12 and cape_val > 150:
            hail_score = (cape_val / 35.0) - (li_val * 5.0) + ((rh - 50) * 0.5)
        probs["Büyük Çaplı Dolu Tedbiri"] = min(max(int(hail_score), 0), 95)

        if ws_kmh > 25 and cape_val > 400 and li_val < 0:
            tornado_score = (ws_kmh / 60.0) * 35 + (cape_val / 50.0) - (li_val * 4.5) + (rh / 10.0)
        else:
            tornado_score = (ws_kmh / 100.0) * 15 + (rh / 20.0)
        probs["Süperhücre & Hortum Riski"] = min(max(int(tornado_score), 1), 95)

        frost_score = 0
        if t <= 4: frost_score = (4.0 - t) * 20.0 + (50.0 - rh) * 0.6 - (ws_kmh * 0.4)
        probs["Zirai Don Riski (Frost)"] = min(max(int(frost_score), 0), 100)

        heat_score = 0
        if t >= 32: heat_score = (t - 31.0) * 12.0 + (rh - 40.0) * 0.6
        probs["Ekstrem Sıcak Dalgası"] = min(max(int(heat_score), 0), 100)

        fire_score = 0
        if t > 22: fire_score = (t - 20.0) * 3.0 + (50.0 - rh) * 2.2 + (ws_kmh * 0.5)
        probs["Orman Yangını Başlangıç Riski"] = min(max(int(fire_score), 5), 99)

        wind_storm = (ws_kmh / 80.0) * 70.0 - (li_val * 1.5) + (cape_val / 150.0)
        probs["Şiddetli Fırtına / Yıkıcı Rüzgar"] = min(max(int(wind_storm), 2), 100)

        return probs

    def process_weather_data(e):
        query = ent_city.value.strip()
        if not query: return
        
        btn_analyze.disabled = True
        btn_analyze.text = "ANALİZ EDİLİYOR..."
        page.update()

        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=1&language=tr&format=json"
            geo_res = requests.get(geo_url).json()
            
            if "results" not in geo_res:
                lbl_card1_val.value = "Konum bulunamadı!"
                btn_analyze.disabled = False
                btn_analyze.text = "VERİLERİ ÇEK & ANALİZ ET"
                page.update()
                return

            lat = geo_res["results"][0]["latitude"]
            lon = geo_res["results"][0]["longitude"]
            location_name = geo_res["results"][0]["name"]

            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,dew_point_2m,surface_pressure,wind_speed_10m,wind_direction_10m,cape&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,precipitation_probability,wind_speed_10m,cape&forecast_days=3&timezone=auto"
            w_res = requests.get(weather_url).json()

            current = w_res["current"]
            t_val = current["temperature_2m"]
            rh_val = current["relative_humidity_2m"]
            td_val = current["dew_point_2m"]
            p_val = current["surface_pressure"]
            ws_val = current["wind_speed_10m"]
            cape_val = current.get("cape", 0.0)

            pressure = p_val * units.hPa
            temperature = t_val * units.degC
            dewpoint = td_val * units.degC

            lcl_p, lcl_t = mpcalc.lcl(pressure, temperature, dewpoint)
            lcl_height_m = mpcalc.pressure_to_height_std(lcl_p).to(units.meters).m

            p_profile = np.array([p_val, p_val - 150, p_val - 300]) * units.hPa
            t_profile = np.array([t_val, t_val - 10, t_val - 25]) * units.degC
            td_profile = np.array([td_val, td_val - 5, td_val - 15]) * units.degC

            try:
                ccl_p, _, _ = mpcalc.ccl(p_profile, t_profile, td_profile)
                ccl_height_m = mpcalc.pressure_to_height_std(ccl_p).to(units.meters).m
                ccl_text = f"{ccl_height_m:.1f} m"
            except:
                ccl_height_m = None
                ccl_text = "Stabil"

            t_500_env = (t_val - 22.0) * units.degC
            try:
                if 500.0 * units.hPa >= lcl_p: t_500_parcel = mpcalc.dry_lapse(500.0 * units.hPa, temperature, pressure)
                else: t_500_parcel = mpcalc.moist_lapse(500.0 * units.hPa, lcl_t, lcl_p)
                li_val = (t_500_env - t_500_parcel).m
            except:
                li_val = 1.5 
            
            cin_val = float(int(rh_val * 1.5)) if cape_val == 0 else max(0.0, float(150.0 - (cape_val / 10.0)))

            if li_val < 0 or cape_val > 250:
                status_text = f"📍 {location_name.upper()}\nLI ({li_val:.1f}) Negatif. CAPE Aktif.\nKonvektif kararsızlık YÜKSEK! Cb bulutları fırtına riski."
            elif (t_val - td_val) <= 3:
                status_text = f"📍 {location_name.upper()}\nStabil atmosfer (LI: {li_val:.1f}).\nNem yüksek, sis/alçak bulutlanma beklentisi."
            else:
                status_text = f"📍 {location_name.upper()}\nStabil atmosfer (LI: {li_val:.1f}).\nSakin ve kararlı bir hava regime."
            
            lbl_card1_val.value = status_text
            lbl_card2_val.value = f"LCL Yükseklik: {lcl_height_m:.0f} m\nCCL Yükseklik: {ccl_text}\nAnlık CAPE: {cape_val:.0f} J/kg\nAnlık CIN: {cin_val:.0f} J/kg\nLifted Index (LI): {li_val:.1f}"

            # --- SAATLİK TREND ALANI (YAĞIŞ KORUNDU + NEM & CAPE ENTEGRASYONU) ---
            hourly = w_res["hourly"]
            current_time_str = current["time"]
            
            start_idx = 0
            for idx, t_str in enumerate(hourly["time"]):
                if t_str >= current_time_str:
                    start_idx = idx
                    break

            trend_controls = [ft.Text("24 SAATLİK AKIŞ (SICAKLIK - YAĞIŞ - NEM - CAPE)", size=14, weight="bold", color="#00ff00")]
            
            for i in range(start_idx, start_idx + 24):
                if i >= len(hourly["time"]): break
                dt_obj = datetime.strptime(hourly["time"][i], "%Y-%m-%dT%H:%M")
                t_display = dt_obj.strftime("%H:%M")
                
                h_t = hourly["temperature_2m"][i]
                h_pop = hourly["precipitation_probability"][i] # Yağış olasılığı yerinde duruyor
                h_rh = hourly["relative_humidity_2m"][i]       # Nem
                h_cape = hourly.get("cape", [0.0]*72)[i]       # CAPE
                
                trend_controls.append(
                    ft.Row([
                        ft.Text(f"⏰ {t_display}", size=11, weight="bold", width=45),
                        ft.Text(f"🌡️ {h_t:.1f}°C", size=11, color="#ffb300", width=65),
                        ft.Text(f"💧 Yağış: %{h_pop}", size=11, color="#1f77b4", width=80),
                        ft.Text(f"💦 Nem: %{h_rh}", size=11, color="#00ffff", width=75),
                        ft.Text(f"⚡ CAPE: {h_cape:.0f}", size=11, color="#ff4444")
                    ])
                )
            trend_container.content = ft.Column(trend_controls)

            # Sayısal Matris Çıktıları
            num_summary = f"📍 {location_name.upper()}\nBasınç: {p_val:.1f} hPa | LCL: {lcl_height_m:.1f}m\nCAPE: {cape_val} J/kg | LI: {li_val:.2f}\nSıcaklık: {t_val}°C | Nem: %{rh_val} | Çiğ N.: {td_val}°C"
            txt_numeric_summary.value = num_summary

            forecast_table = f"SAAT  °C    NEM  ÇİĞ   YAĞ(%)  CAPE\n" + "-"*35 + "\n"
            for i in range(start_idx, start_idx + 24):
                if i >= len(hourly["time"]): break
                dt_obj = datetime.strptime(hourly["time"][i], "%Y-%m-%dT%H:%M")
                t_display = dt_obj.strftime("%H:%M")
                forecast_table += f"{t_display:<6}{f'{hourly['temperature_2m'][i]:.1f}':<6}{f'{hourly['relative_humidity_2m'][i]}':<5}{f'{hourly['dew_point_2m'][i]:.1f}':<6}{f'{hourly['precipitation_probability'][i]}':<8}{f'{hourly.get('cape', [0.0]*72)[i]:.0f}':<6}\n"
            txt_numeric_table.value = forecast_table

            # Ekstrem Blok Çıktıları
            ext_probs = calculate_extreme_probabilities(t_val, rh_val, td_val, ws_val, cape_val, li_val)
            report = f"🛑 EKSTREM OLAY RAPORU\n📍 {location_name.upper()}\n\n"
            for name, prob in ext_probs.items():
                status = "GÜVENLİ" if prob < 20 else "ORTA" if prob < 50 else "YÜKSEK" if prob < 75 else "TEHLİKE"
                report += f"• {name}:\n  %{prob} -> {status}\n\n"
            txt_extreme_report.value = report

        except Exception as e:
            lbl_card1_val.value = f"Hata oluştu: {str(e)}"

        finally:
            btn_analyze.disabled = False
            btn_analyze.text = "VERİLERİ ÇEK & ANALİZ ET"
            page.update()

    btn_analyze = ft.ElevatedButton("VERİLERİ ÇEK & ANALİZ ET", on_click=process_weather_data, bgcolor="#ffb300", color="black")

    # --- KILÇIKSIZ DOĞRUSAL DÜZEN ---
    page.add(
        ft.Row([title_text], alignment="center"),
        ft.Row([ent_city, btn_analyze]),
        ft.Container(height=10),
        card_status,
        ft.Container(height=10),
        card_metpy,
        ft.Container(height=10),
        trend_container,
        ft.Container(height=10),
        ft.Text("🔢 SAYISAL TELEMETRİ MATRİSİ:", weight="bold", color="#ffb300"),
        txt_numeric_summary,
        txt_numeric_table,
        ft.Container(height=10),
        ft.Text("⚠️ EKSTREM TAHMİN RAPORU:", weight="bold", color="#ff4444"),
        txt_extreme_report
# Kodu internet sunucusuna uyumlu hale getiren başlatma komutu
if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8000)
)
